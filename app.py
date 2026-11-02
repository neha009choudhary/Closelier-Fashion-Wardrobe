from flask import Flask, render_template, request, redirect, flash, session
from dotenv import load_dotenv
import sqlite3
import os
import requests
import re
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
from datetime import datetime

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

app = Flask(__name__)
app.secret_key = "ai-fashion-wardrobe-secret"


# ================================
# FILE UPLOAD SETTINGS
# ================================

UPLOAD_FOLDER = "static/uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ================================
# DATABASE
# ================================

def get_db_connection():

    connection = sqlite3.connect("wardrobe.db")

    connection.row_factory = sqlite3.Row

    return connection


def create_database():

    connection = get_db_connection()

    # Wardrobe table

    connection.execute("""
        CREATE TABLE IF NOT EXISTS wardrobe_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            color TEXT NOT NULL,
            occasion TEXT NOT NULL,
            image TEXT
        )
    """)

    # Saved Outfits table

    connection.execute("""
        CREATE TABLE IF NOT EXISTS saved_outfits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            outfit_data TEXT NOT NULL
        )
    """)

    # Profile table

    connection.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            style TEXT NOT NULL,
            favorite_color TEXT NOT NULL
        )
    """)

    # Users table

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)
    # Add user_id to existing tables for multi-user support

    try:
        connection.execute(
            "ALTER TABLE wardrobe_items ADD COLUMN user_id INTEGER"
        )
    except sqlite3.OperationalError:
        pass

    try:
        connection.execute(
            "ALTER TABLE saved_outfits ADD COLUMN user_id INTEGER"
        )
    except sqlite3.OperationalError:
        pass

    try:
        connection.execute(
            "ALTER TABLE profile ADD COLUMN user_id INTEGER"
        )
    except sqlite3.OperationalError:
        pass

    connection.commit()

    connection.close()


# ================================
# HOME PAGE
# ================================

@app.route("/")
def home():

    return render_template("index.html")

# ================================
# REGISTER
# ================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = (request.form.get("name") or "").strip()
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not re.fullmatch(r"[A-Za-z ]+", name):
            flash("Please enter a valid name using letters only.")
            return redirect("/register")

        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect("/register")

        connection = get_db_connection()

        existing_user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:
            connection.close()
            flash("An account with this email already exists.")
            return redirect("/register")

        hashed_password = generate_password_hash(password)

        connection.execute(
            """
            INSERT INTO users (name, email, password)
            VALUES (?, ?, ?)
            """,
            (name, email, hashed_password)
        )

        connection.commit()
        connection.close()

        flash("Account created successfully. Please login.")
        return redirect("/login")

    return render_template("register.html")

    

# ================================
# LOGIN
# ================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        connection = get_db_connection()

        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(user["password"], password):
           
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            flash("Login successful. Welcome back!")

            return redirect("/dashboard")

        flash("Invalid email or password.")
        return redirect("/login")

    return render_template("login.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("Passwords do not match.")
            return redirect("/forgot-password")

        connection = get_db_connection()

        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if not user:
            connection.close()
            flash("No account found with this email.")
            return redirect("/forgot-password")

        hashed_password = generate_password_hash(new_password)

        connection.execute(
            "UPDATE users SET password = ? WHERE email = ?",
            (hashed_password, email)
        )

        connection.commit()
        connection.close()

        flash("Password reset successful. Please login with your new password.")
        return redirect("/login")

    return render_template("forgot_password.html")    


@app.route("/logout")
def logout():

    session.clear()
    flash("You have been logged out.")
    return redirect("/")


# ================================
# PROFILE
# ================================

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect("/login")

    connection = get_db_connection()

    profile_data = connection.execute(
        """
        SELECT * FROM profile
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (session["user_id"],)
    ).fetchone()

    connection.close()

    return render_template(
        "profile.html",
        profile=profile_data
    )

# ================================
# AI STYLING
# ================================

@app.route("/ai-styling")
def ai_styling():

    if "user_id" not in session:
        return redirect("/login")

    return render_template("ai_styling.html")

# ================================
# SHOPPING ASSISTANT
# ================================

@app.route("/shopping-assistant", methods=["GET", "POST"])
def shopping_assistant():

    # -------------------------------------------------
    # LOGIN CHECK
    # -------------------------------------------------

    if "user_id" not in session:
        return redirect("/login")


    # -------------------------------------------------
    # Create shopping list table if it does not exist
    # -------------------------------------------------

    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS shopping_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            price TEXT NOT NULL,
            user_id INTEGER
        )
    """)

    # Add user_id to an existing shopping_list table
    try:
        connection.execute(
            "ALTER TABLE shopping_list ADD COLUMN user_id INTEGER"
        )
    except sqlite3.OperationalError:
        pass

    connection.commit()


    # -------------------------------------------------
    # Default values
    # -------------------------------------------------

    strong_categories = "Your wardrobe insights will appear here."
    potential_gaps = "Answer the questions to discover useful gaps."
    smart_insight = "Complete the questions to get a personalised insight."

    products = []


    # -------------------------------------------------
    # SHOPPING CATALOGUE
    # This is separate from the user's wardrobe.
    # -------------------------------------------------

    shopping_catalogue = [

        {
            "name": "Oversized Denim Jacket",
            "category": "Clothing",
            "uses": ["Everyday", "College", "Travel"],
            "styles": ["Casual", "Trendy"],
            "price": "₹1,500–₹3,000",
            "min_price": 1500,
            "max_price": 3000,
            "tag": "Trend-inspired",
            "icon": "🧥",
            "stores": [
                {"name": "Myntra", "url": "https://www.myntra.com/"},
                {"name": "AJIO", "url": "https://www.ajio.com/"},
                {"name": "H&M", "url": "https://www2.hm.com/"}
            ]
        },

        {
            "name": "Minimal Shoulder Bag",
            "category": "Accessories",
            "uses": ["Everyday", "College", "Occasional"],
            "styles": ["Minimal", "Elegant"],
            "price": "₹800–₹2,000",
            "min_price": 800,
            "max_price": 2000,
            "tag": "Everyday",
            "icon": "👜",
            "stores": [
                {"name": "Myntra", "url": "https://www.myntra.com/"},
                {"name": "AJIO", "url": "https://www.ajio.com/"},
                {"name": "ZARA", "url": "https://www.zara.com/in/"}
            ]
        },

        {
            "name": "Retro Sneakers",
            "category": "Footwear",
            "uses": ["Everyday", "College", "Travel"],
            "styles": ["Casual", "Trendy"],
            "price": "₹2,000–₹4,000",
            "min_price": 2000,
            "max_price": 4000,
            "tag": "Casual",
            "icon": "👟",
            "stores": [
                {"name": "Myntra", "url": "https://www.myntra.com/"},
                {"name": "AJIO", "url": "https://www.ajio.com/"},
                {"name": "Amazon", "url": "https://www.amazon.in/"}
            ]
        },

        {
            "name": "Classic White Shirt",
            "category": "Clothing",
            "uses": ["Everyday", "College", "Occasional"],
            "styles": ["Minimal", "Elegant"],
            "price": "₹900–₹1,800",
            "min_price": 900,
            "max_price": 1800,
            "tag": "Versatile",
            "icon": "👔",
            "stores": [
                {"name": "Myntra", "url": "https://www.myntra.com/"},
                {"name": "H&M", "url": "https://www2.hm.com/"},
                {"name": "AJIO", "url": "https://www.ajio.com/"}
            ]
        },

        {
            "name": "Elegant Midi Dress",
            "category": "Clothing",
            "uses": ["Occasional", "Special occasions"],
            "styles": ["Elegant", "Minimal"],
            "price": "₹1,800–₹4,000",
            "min_price": 1800,
            "max_price": 4000,
            "tag": "Occasion-ready",
            "icon": "👗",
            "stores": [
                {"name": "Myntra", "url": "https://www.myntra.com/"},
                {"name": "ZARA", "url": "https://www.zara.com/in/"},
                {"name": "AJIO", "url": "https://www.ajio.com/"}
            ]
        },

        {
            "name": "Structured Handbag",
            "category": "Accessories",
            "uses": ["Occasional", "Special occasions"],
            "styles": ["Elegant", "Minimal"],
            "price": "₹2,500–₹5,000",
            "min_price": 2500,
            "max_price": 5000,
            "tag": "Elegant",
            "icon": "👜",
            "stores": [
                {"name": "Myntra", "url": "https://www.myntra.com/"},
                {"name": "ZARA", "url": "https://www.zara.com/in/"},
                {"name": "AJIO", "url": "https://www.ajio.com/"}
            ]
        },

        {
            "name": "Travel Crossbody Bag",
            "category": "Accessories",
            "uses": ["Travel", "Everyday"],
            "styles": ["Casual", "Minimal"],
            "price": "₹1,000–₹2,500",
            "min_price": 1000,
            "max_price": 2500,
            "tag": "Travel",
            "icon": "🎒",
            "stores": [
                {"name": "Myntra", "url": "https://www.myntra.com/"},
                {"name": "AJIO", "url": "https://www.ajio.com/"},
                {"name": "Amazon", "url": "https://www.amazon.in/"}
            ]
        },

        {
            "name": "Statement Accessories Set",
            "category": "Accessories",
            "uses": ["Occasional", "Special occasions"],
            "styles": ["Trendy", "Elegant"],
            "price": "₹700–₹1,500",
            "min_price": 700,
            "max_price": 1500,
            "tag": "Statement",
            "icon": "✨",
            "stores": [
                {"name": "Myntra", "url": "https://www.myntra.com/"},
                {"name": "AJIO", "url": "https://www.ajio.com/"}
            ]
        }
    ]


    # -------------------------------------------------
    # HANDLE POST REQUEST
    # -------------------------------------------------

    if request.method == "POST":

        action = request.form.get("action")


        # =============================================
        # ADD ITEM TO SHOPPING LIST
        # =============================================

        if action == "add":

            product_name = request.form.get("product_name")
            product_price = request.form.get("product_price")

            if product_name and product_price:

                existing_item = connection.execute(
                    """
                    SELECT id
                    FROM shopping_list
                    WHERE product_name = ?
                    AND user_id = ?
                    """,
                    (
                        product_name,
                        session["user_id"]
                    )
                ).fetchone()


                if not existing_item:

                    connection.execute(
                        """
                        INSERT INTO shopping_list
                        (product_name, price, user_id)
                        VALUES (?, ?, ?)
                        """,
                        (
                            product_name,
                            product_price,
                            session["user_id"]
                        )
                    )

                    connection.commit()


                saved_results = session.get("shopping_results")

                if saved_results:
                    strong_categories = saved_results["strong_categories"]
                    potential_gaps = saved_results["potential_gaps"]
                    smart_insight = saved_results["smart_insight"]
                    products = saved_results["products"]


        # =============================================
        # REMOVE ITEM FROM SHOPPING LIST
        # =============================================

        elif action == "remove":

            item_id = request.form.get("item_id")

            if item_id:

                connection.execute(
                    """
                    DELETE FROM shopping_list
                    WHERE id = ?
                    AND user_id = ?
                    """,
                    (
                        item_id,
                        session["user_id"]
                    )
                )

                connection.commit()


                saved_results = session.get("shopping_results")

                if saved_results:
                    strong_categories = saved_results["strong_categories"]
                    potential_gaps = saved_results["potential_gaps"]
                    smart_insight = saved_results["smart_insight"]
                    products = saved_results["products"]


        # =============================================
        # PROCESS THE FIVE SHOPPING QUESTIONS
        # =============================================

        else:

            goal = request.form.get("goal", "").strip()
            category = request.form.get("category", "").strip()
            use = request.form.get("use", "").strip()
            style = request.form.get("style", "").strip()
            budget = request.form.get("budget", "").strip()

            session["shopping_preferences"] = {
                "goal": goal,
                "category": category,
                "use": use,
                "style": style,
                "budget": budget
            }


            # -----------------------------------------
            # WARDROBE INSIGHTS
            # -----------------------------------------

            wardrobe_items = connection.execute(
                """
                SELECT category, occasion
                FROM wardrobe_items
                WHERE user_id = ?
                """,
                (session["user_id"],)
            ).fetchall()


            category_counts = {}

            for item in wardrobe_items:

                item_category = item["category"].strip().title()

                category_counts[item_category] = (
                    category_counts.get(item_category, 0) + 1
                )


            # Strong categories

            if category_counts:

                sorted_categories = sorted(
                    category_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )

                top_categories = sorted_categories[:3]

                strong_categories = ", ".join(
                    [
                        f"{name} ({count})"
                        for name, count in top_categories
                    ]
                )

            else:

                strong_categories = (
                    "Your wardrobe is still waiting for its first pieces."
                )


            # Potential gaps

            important_categories = [
                "Clothing",
                "Footwear",
                "Accessories"
            ]

            missing_categories = []

            for important_category in important_categories:

                found = False

                for existing_category in category_counts:

                    if existing_category.lower() == important_category.lower():

                        found = True
                        break

                if not found:

                    missing_categories.append(important_category)


            if missing_categories:

                potential_gaps = (
                    "You have fewer or no items in: "
                    + ", ".join(missing_categories)
                    + "."
                )

            else:

                low_categories = []

                for important_category in important_categories:

                    count = 0

                    for existing_category, number in category_counts.items():

                        if existing_category.lower() == important_category.lower():

                            count = number

                    if count <= 1:

                        low_categories.append(important_category)


                if low_categories:

                    potential_gaps = (
                        "You could add more variety in: "
                        + ", ".join(low_categories)
                        + "."
                    )

                else:

                    potential_gaps = (
                        "Your main wardrobe categories have a good base."
                    )


            # Smart insight

            if category and category.lower() != "any category":

                selected_count = 0

                for existing_category, number in category_counts.items():

                    if existing_category.lower() == category.lower():

                        selected_count = number

                if selected_count == 0:

                    smart_insight = (
                        f"You don't currently have much in the "
                        f"{category.lower()} category, so this could "
                        f"be a useful addition to your wardrobe."
                    )

                elif selected_count <= 2:

                    smart_insight = (
                        f"You have {selected_count} "
                        f"{category.lower()} item(s). "
                        f"A different colour or style could add variety."
                    )

                else:

                    smart_insight = (
                        f"You already have several {category.lower()} "
                        f"items. Consider choosing a piece that adds "
                        f"something different to your wardrobe."
                    )

            elif goal:

                smart_insight = (
                    f"Since you're looking to {goal.lower()}, "
                    f"focus on versatile pieces that work with "
                    f"what you already own."
                )


            # -----------------------------------------
            # PRODUCT MATCHING
            # -----------------------------------------

            budget_ranges = {
                "₹500–₹1,000": (500, 1000),
                "₹1,000–₹2,500": (1000, 2500),
                "₹2,500–₹5,000": (2500, 5000),
                "₹5,000+": (5000, 100000)
            }

            selected_budget = budget_ranges.get(
                budget,
                (0, 100000)
            )


            scored_products = []


            for product in shopping_catalogue:

                score = 0


                # Category match

                if (
                    category.lower() == "any category"
                    or product["category"].lower() == category.lower()
                ):

                    score += 4


                # Use match

                if use in product["uses"]:

                    score += 3


                # Style match

                if style in product["styles"]:

                    score += 3


                # Budget overlap

                budget_min, budget_max = selected_budget

                if (
                    product["max_price"] >= budget_min
                    and product["min_price"] <= budget_max
                ):

                    score += 3


                # Goal-specific bonus

                if goal == "Prepare for a trip" and use == "Travel":

                    if product["category"] in [
                        "Accessories",
                        "Footwear",
                        "Clothing"
                    ]:

                        score += 2


                if goal == "Prepare for an event":

                    if use in [
                        "Occasional",
                        "Special occasions"
                    ]:

                        score += 2


                if goal == "Build versatile outfits":

                    if product["name"] in [
                        "Classic White Shirt",
                        "Oversized Denim Jacket",
                        "Minimal Shoulder Bag"
                    ]:

                        score += 2


                scored_products.append(
                    (score, product)
                )


            scored_products.sort(
                key=lambda item: item[0],
                reverse=True
            )


            products = [
                product
                for score, product in scored_products[:3]
            ]


            session["shopping_results"] = {
                "strong_categories": strong_categories,
                "potential_gaps": potential_gaps,
                "smart_insight": smart_insight,
                "products": products
            }


    # -------------------------------------------------
    # SHOPPING LIST
    # -------------------------------------------------

    shopping_list = connection.execute(
        """
        SELECT id, product_name, price
        FROM shopping_list
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()


    connection.close()


    # -------------------------------------------------
    # DISPLAY PAGE
    # -------------------------------------------------

    return render_template(
        "shopping_assistant.html",
        strong_categories=strong_categories,
        potential_gaps=potential_gaps,
        smart_insight=smart_insight,
        products=products,
        shopping_list=shopping_list
    )

# ================================
# AI OUTFIT GENERATOR
# ================================

from itertools import product


@app.route("/generate-outfit", methods=["POST"])
def generate_outfit():

    if "user_id" not in session:
        return redirect("/login")

    occasion = request.form.get("occasion", "").strip()

    connection = get_db_connection()

    items = connection.execute(
        """
        SELECT *
        FROM wardrobe_items
        WHERE user_id = ?
        AND LOWER(TRIM(occasion)) = LOWER(TRIM(?))
        ORDER BY id DESC
        """,
        (session["user_id"], occasion)
    ).fetchall()

    connection.close()

    # =====================================
    # CATEGORY COLLECTIONS
    # =====================================

    tops = []
    bottoms = []
    dresses = []
    ethnic_wear = []
    footwear = []
    accessories = []
    seasonal_items = []

    for item in items:

        category = (
            item["category"] or ""
        ).strip().lower()

        name = (
            item["name"] or ""
        ).strip().lower()

        # Standard categories
        if category == "tops":
            tops.append(item)

        elif category == "bottoms":
            bottoms.append(item)

        elif category == "dresses":
            dresses.append(item)

        elif category == "ethnic wear":
            ethnic_wear.append(item)

        elif category == "footwear":
            footwear.append(item)

        elif category in ["accessory", "accessories"]:
            accessories.append(item)

        # Seasonal categories
        elif category in [
            "summer style",
            "rainy style",
            "winter style"
        ]:

            seasonal_items.append(item)

            # Identify clothing type from its name
            if any(word in name for word in [
                "dress", "gown", "jumpsuit"
            ]):
                dresses.append(item)

            elif any(word in name for word in [
                "top", "shirt", "t-shirt", "tshirt",
                "blouse", "crop top", "kurti"
            ]):
                tops.append(item)

            elif any(word in name for word in [
                "bottom", "jeans", "trouser", "pants",
                "leggings", "skirt", "shorts", "palazzo"
            ]):
                bottoms.append(item)

            elif any(word in name for word in [
                "boot", "boots", "sneakers", "shoes",
                "sandals", "heels", "footwear"
            ]):
                footwear.append(item)

    # =====================================
    # CREATE BASE OUTFITS
    # =====================================

    outfits = []

    # 1. Generate all top + bottom combinations
    for top, bottom in product(tops, bottoms):

        outfits.append([top, bottom])

    # If only tops or bottoms exist
    if tops and not bottoms:

        for top in tops:
            outfits.append([top])

    elif bottoms and not tops:

        for bottom in bottoms:
            outfits.append([bottom])

    # 2. Include every dress
    for dress in dresses:

        outfits.append([dress])

    # 3. Include complete traditional outfits
    for ethnic_item in ethnic_wear:

        outfits.append([ethnic_item])

    # =====================================
    # REMOVE DUPLICATE BASE OUTFITS
    # =====================================

    unique_outfits = []
    seen_combinations = set()

    for outfit in outfits:

        outfit_ids = tuple(
            item["id"] for item in outfit
        )

        if outfit_ids not in seen_combinations:

            unique_outfits.append(outfit)
            seen_combinations.add(outfit_ids)

    # =====================================
    # ADD FOOTWEAR AND ACCESSORIES
    # =====================================

    final_outfits = []

    for index, outfit in enumerate(unique_outfits):

        completed_outfit = list(outfit)

        # Don't add extra items already in the outfit
        outfit_ids = {
            item["id"] for item in completed_outfit
        }

        if footwear:

            available_footwear = [
                item for item in footwear
                if item["id"] not in outfit_ids
            ]

            if available_footwear:

                completed_outfit.append(
                    available_footwear[
                        index % len(available_footwear)
                    ]
                )

        outfit_ids = {
            item["id"] for item in completed_outfit
        }

        if accessories:

            available_accessories = [
                item for item in accessories
                if item["id"] not in outfit_ids
            ]

            if available_accessories:

                completed_outfit.append(
                    available_accessories[
                        index % len(available_accessories)
                    ]
                )

        final_outfits.append(completed_outfit)

    # =====================================
    # DISPLAY ALL GENERATED OUTFITS
    # =====================================

    return render_template(
        "ai_styling.html",
        outfits=final_outfits,
        selected_occasion=occasion
    )

@app.route("/save-outfit", methods=["POST"])
def save_outfit():

    if "user_id" not in session:
        return redirect("/login")

    outfit_data = request.form.get("outfit_data")

    if outfit_data:

        connection = get_db_connection()

        connection.execute(
            """
            INSERT INTO saved_outfits
            (outfit_data, user_id)
            VALUES (?, ?)
            """,
            (
                outfit_data,
                session["user_id"]
            )
        )

        connection.commit()
        connection.close()

    return redirect("/ai-styling")

# ================================
# SAVED OUTFITS
# ================================

@app.route("/saved-outfits")
def saved_outfits():

    if "user_id" not in session:
        return redirect("/login")

    connection = get_db_connection()

    saved_rows = connection.execute(
        """
        SELECT * FROM saved_outfits
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    saved_outfits_list = []

    for saved in saved_rows:

        item_ids = saved["outfit_data"].split(",")

        outfit_items = []

        for item_id in item_ids:

            item = connection.execute(
                """
                SELECT * FROM wardrobe_items
                WHERE id = ? AND user_id = ?
                """,
                (
                    item_id,
                    session["user_id"]
                )
            ).fetchone()

            if item:
                outfit_items.append(item)

        if outfit_items:
            saved_outfits_list.append(outfit_items)

    connection.close()

    return render_template(
        "saved_outfits.html",
        saved_outfits=saved_outfits_list
    )

# ================================
# SAVE PROFILE
# ================================

@app.route("/save-profile", methods=["POST"])
def save_profile():

    if "user_id" not in session:
        return redirect("/login")

    name = request.form["name"]

    age = request.form["age"]

    style = request.form["style"]

    favorite_color = request.form["favorite_color"]

    connection = get_db_connection()

    # Check if a profile already exists for this user

    existing_profile = connection.execute(
        """
        SELECT * FROM profile
        WHERE user_id = ?
        LIMIT 1
        """,
        (session["user_id"],)
    ).fetchone()

    if existing_profile:

        # Update this user's profile

        connection.execute(
            """
            UPDATE profile
            SET name = ?,
                age = ?,
                style = ?,
                favorite_color = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                name,
                age,
                style,
                favorite_color,
                existing_profile["id"],
                session["user_id"]
            )
        )

    else:

        # Create a profile for this user

        connection.execute(
            """
            INSERT INTO profile
            (name, age, style, favorite_color, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                age,
                style,
                favorite_color,
                session["user_id"]
            )
        )

    connection.commit()

    connection.close()

    flash("Profile saved successfully!")
    return redirect("/profile")

# ================================
# DASHBOARD
# ================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    connection = get_db_connection()

    wardrobe_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM wardrobe_items
        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchone()[0]

    outfit_count = connection.execute(
        """
        SELECT COUNT(DISTINCT outfit_data)
        FROM saved_outfits
        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchone()[0]

    connection.close()

    return render_template(
        "dashboard.html",
        wardrobe_count=wardrobe_count,
        outfit_count=outfit_count
    )

# ================================
# MY WARDROBE
# ================================

@app.route("/wardrobe")
def wardrobe():

    if "user_id" not in session:
        return redirect("/login")

    connection = get_db_connection()

    items = connection.execute(
        """
        SELECT * FROM wardrobe_items
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "wardrobe.html",
        items=items
    )

# ================================
# DETECT OUTFIT COLOR
# ================================

def get_dominant_color(image_path):

    image = Image.open(image_path)

    # Make the image smaller for faster processing
    image = image.resize((100, 100))

    # Convert image to RGB
    image = image.convert("RGB")

    pixels = list(image.getdata())

    # Calculate average RGB values
    total_red = 0
    total_green = 0
    total_blue = 0

    for red, green, blue in pixels:

        total_red += red
        total_green += green
        total_blue += blue

    pixel_count = len(pixels)

    average_red = total_red // pixel_count
    average_green = total_green // pixel_count
    average_blue = total_blue // pixel_count

    # Convert RGB into a simple color name
    if average_red > 180 and average_green > 180 and average_blue > 180:
        return "White"

    elif average_red < 70 and average_green < 70 and average_blue < 70:
        return "Black"

    elif average_red > average_green * 1.3 and average_red > average_blue * 1.3:
        return "Red"

    elif average_blue > average_red * 1.3 and average_blue > average_green * 1.1:
        return "Blue"

    elif average_green > average_red * 1.2 and average_green > average_blue * 1.2:
        return "Green"

    elif average_red > 150 and average_green > 100 and average_blue < 100:
        return "Yellow"

    elif average_red > 120 and average_green < 100 and average_blue > 100:
        return "Purple"

    else:
        return "Neutral"

# ================================
# ACCESSORIES
# ================================

@app.route("/accessories")
def accessories():

    if "user_id" not in session:
        return redirect("/login")

    connection = get_db_connection()

    accessories = connection.execute(
        """
        SELECT * FROM wardrobe_items
        WHERE user_id = ? AND LOWER(category) = LOWER(?)
        ORDER BY id DESC
        """,
        (session["user_id"], "Accessories")
    ).fetchall()

    connection.close()

    return render_template(
        "accessories.html",
        accessories=accessories
    )


@app.route("/analyze-accessories", methods=["POST"])
def analyze_accessories():

    if "user_id" not in session:
        return redirect("/login")

    outfit_image = request.files.get("outfit_image")
    image_path = None
    detected_color = None

    if outfit_image and outfit_image.filename:

        if allowed_file(outfit_image.filename):

            filename = secure_filename(outfit_image.filename)

            outfit_image.save(
                os.path.join(app.config["UPLOAD_FOLDER"], filename)
            )

            image_path = filename

            # Detect outfit color
            detected_color = get_dominant_color(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

    connection = get_db_connection()

    # Get all saved accessories
    all_accessories = connection.execute(
        """
        SELECT * FROM wardrobe_items
        WHERE user_id = ? AND LOWER(category) IN ('accessory', 'accessories')
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    # Color combinations for accessory matching
    color_matches = {
        "Black": ["Black", "Silver", "Gold", "White", "Red"],
        "White": ["White", "Gold", "Silver", "Black", "Blue"],
        "Red": ["Red", "Gold", "Black", "Silver"],
        "Blue": ["Blue", "Silver", "White", "Gold"],
        "Green": ["Green", "Gold", "White", "Black"],
        "Yellow": ["Yellow", "Gold", "White", "Black"],
        "Purple": ["Purple", "Silver", "Gold", "White"],
        "Neutral": ["Neutral", "Black", "White", "Gold", "Silver"]
    }

    # Find matching accessories
    accessories = []

    if detected_color:

        matching_colors = color_matches.get(
            detected_color,
            [detected_color]
        )

        for color in matching_colors:

            for item in all_accessories:

                if item["color"].lower() == color.lower():
                    accessories.append(item)

    # Remove duplicate accessories
    unique_accessories = []

    for item in accessories:

        if item["id"] not in [
            x["id"] for x in unique_accessories
        ]:
            unique_accessories.append(item)

    accessories = unique_accessories

    # If no matching accessories are found,
    # show all saved accessories
    if not accessories:
        accessories = all_accessories

    return render_template(
        "accessories.html",
        accessories=accessories,
        outfit_image=image_path,
        detected_color=detected_color
    )


# ================================
# ADD CLOTHING
# ================================

@app.route("/add-clothing", methods=["POST"])
def add_clothing():

    if "user_id" not in session:
        return redirect("/login")

    name = request.form["name"]

    category = request.form["category"]

    color = request.form["color"]

    occasion = request.form["occasion"]

    image_path = None

    # Handle uploaded image

    if "image" in request.files:

        image = request.files["image"]

        if image and image.filename:

            if allowed_file(image.filename):

                filename = secure_filename(image.filename)

                image.save(
                    os.path.join(
                        app.config["UPLOAD_FOLDER"],
                        filename
                    )
                )

                image_path = filename

    # Save clothing details

    connection = get_db_connection()

    connection.execute(
        """
        INSERT INTO wardrobe_items
        (name, category, color, occasion, image, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            category,
            color,
            occasion,
            image_path,
            session["user_id"]
        )
    )

    connection.commit()

    connection.close()

    return redirect("/wardrobe")


# ================================
# DELETE CLOTHING
# ================================

@app.route("/delete-clothing/<int:item_id>", methods=["POST"])
def delete_clothing(item_id):

    if "user_id" not in session:
        return redirect("/login")

    connection = get_db_connection()

    # Find the clothing item belonging to the logged-in user

    item = connection.execute(
        """
        SELECT * FROM wardrobe_items
        WHERE id = ? AND user_id = ?
        """,
        (item_id, session["user_id"])
    ).fetchone()

    if item:

        # Delete the uploaded image if it exists

        if item["image"]:

            image_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                item["image"]
            )

            if os.path.exists(image_path):

                os.remove(image_path)

        # Delete the database record

        connection.execute(
            """
            DELETE FROM wardrobe_items
            WHERE id = ? AND user_id = ?
            """,
            (item_id, session["user_id"])
        )

        connection.commit()

    connection.close()

    return redirect("/wardrobe")

@app.route("/weather-styling")
def weather_styling():

    if "user_id" not in session:
        return redirect("/login")
        
    connection = get_db_connection()

    items = connection.execute(
        """
        SELECT * FROM wardrobe_items
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "weather_styling.html",
        items=items
    )

# ================================
# GET WEATHER
# ================================

@app.route("/get-weather")
def get_weather():

    if "user_id" not in session:
        return redirect("/login")

    latitude = request.args.get("latitude")
    longitude = request.args.get("longitude")

    if not latitude or not longitude:
        return {
            "error": "Location coordinates are missing."
        }, 400

    weather_url = "https://api.openweathermap.org/data/2.5/weather"

    parameters = {
        "lat": latitude,
        "lon": longitude,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric"
    }

    response = requests.get(
        weather_url,
        params=parameters
    )

    if response.status_code != 200:
        return {
            "error": "Unable to get weather information."
        }, response.status_code

    weather_data = response.json()

    temperature = weather_data["main"]["temp"]
    condition = weather_data["weather"][0]["main"]

    # =========================================
    # DECIDE WEATHER CATEGORY
    # =========================================

    if condition in ["Rain", "Drizzle", "Thunderstorm"]:

        weather_category = "Rainy Style"

    elif temperature >= 28:

        weather_category = "Summer Style"

    elif temperature <= 20:

        weather_category = "Winter Style"

    else:

        weather_category = "Summer Style"

    # =========================================
    # GET SUITABLE CLOTHING
    # =========================================

    connection = get_db_connection()

    if weather_category == "Summer Style":

        categories = (
            "Tops",
            "Bottoms",
            "Dresses",
            "Footwear",
            "Summer Style"
        )

    elif weather_category == "Rainy Style":

        categories = (
            "Tops",
            "Bottoms",
            "Dresses",
            "Footwear",
            "Rainy Style"
        )

    else:

        categories = (
            "Tops",
            "Bottoms",
            "Dresses",
            "Ethnic Wear",
            "Footwear",
            "Winter Style"
        )

    placeholders = ",".join(["?"] * len(categories))

    wardrobe_items = connection.execute(
        f"""
        SELECT *
        FROM wardrobe_items
        WHERE user_id = ?
        AND category IN ({placeholders})
        ORDER BY id DESC
        """,
        (session["user_id"], *categories)
    ).fetchall()

    connection.close()

    # =========================================
    # SEPARATE CLOTHING BY TYPE
    # =========================================

    tops = []
    bottoms = []
    dresses = []
    footwear = []
    seasonal = []

    for item in wardrobe_items:

        item_data = {
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "color": item["color"],
            "occasion": item["occasion"],
            "image": item["image"]
        }

        if item["category"] == "Tops":

            tops.append(item_data)

        elif item["category"] == "Bottoms":

            bottoms.append(item_data)

        elif item["category"] == "Dresses":

            dresses.append(item_data)

        elif item["category"] == "Footwear":

            footwear.append(item_data)

        elif item["category"] == weather_category:

            seasonal.append(item_data)

    # =========================================
    # CREATE OUTFIT
    # =========================================

    outfit = []

    # -----------------------------------------
    # SUMMER OUTFIT
    # -----------------------------------------

    if weather_category == "Summer Style":

        if dresses:

            outfit.append(dresses[0])

        elif tops:

            outfit.append(tops[0])

            if bottoms:

                outfit.append(bottoms[0])

        if footwear:

            outfit.append(footwear[0])

        if seasonal and not outfit:

            outfit.append(seasonal[0])

    # -----------------------------------------
    # RAINY OUTFIT
    # -----------------------------------------

    elif weather_category == "Rainy Style":

        if tops:

            outfit.append(tops[0])

            if bottoms:

                outfit.append(bottoms[0])

        elif dresses:

            outfit.append(dresses[0])

        if footwear:

            outfit.append(footwear[0])

        if seasonal:

            outfit.append(seasonal[0])

    # -----------------------------------------
    # WINTER OUTFIT
    # -----------------------------------------

    elif weather_category == "Winter Style":

        if tops:

            outfit.append(tops[0])

            if bottoms:

                outfit.append(bottoms[0])

        elif dresses:

            outfit.append(dresses[0])

        if seasonal:

            outfit.append(seasonal[0])

        if footwear:

            outfit.append(footwear[0])

    # =========================================
    # REMOVE DUPLICATE ITEMS
    # =========================================

    unique_outfit = []

    used_ids = set()

    for item in outfit:

        if item["id"] not in used_ids:

            unique_outfit.append(item)

            used_ids.add(item["id"])

    # =========================================
    # RECOMMENDED ITEMS
    # =========================================

    recommended_items = wardrobe_items

    recommended_items_data = []

    for item in recommended_items:

        recommended_items_data.append({
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "color": item["color"],
            "occasion": item["occasion"],
            "image": item["image"]
        })

    # =========================================
    # FINAL RESPONSE
    # =========================================

    return {

        "temperature": temperature,

        "feels_like": weather_data["main"]["feels_like"],

        "humidity": weather_data["main"]["humidity"],

        "condition": condition,

        "description": weather_data["weather"][0]["description"],

        "weather_category": weather_category,

        "outfit": unique_outfit,

        "recommended_items": recommended_items_data

    }

# ================================
# PACKING PLANNER
# ================================

@app.route("/packing-planner", methods=["GET", "POST"])
def packing_planner():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        destination = request.form["destination"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        trip_type = request.form["trip_type"]
        activities = request.form.get("activities", "")

        # Calculate trip duration
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")

            trip_days = (end - start).days + 1

            if trip_days < 1:
                trip_days = 1

        except ValueError:
            trip_days = 1


        # =================================
        # BASIC PACKING REQUIREMENTS
        # =================================

        packing_list = {

            "Clothing": [
                f"{trip_days} Tops",
                f"{max(1, (trip_days + 1) // 2)} Bottoms",
                "1 Extra Outfit",
                "Nightwear",
                "Innerwear",
                "Socks"
            ],

            "Footwear": [
                "Comfortable Shoes",
                "Sandals / Slippers"
            ],

            "Accessories": [
                "Sunglasses",
                "Hat / Cap",
                "Handbag / Sling Bag"
            ],

            "Toiletries": [
                "Toothbrush",
                "Toothpaste",
                "Face Wash",
                "Shampoo",
                "Conditioner",
                "Soap / Body Wash",
                "Deodorant",
                "Sunscreen",
                "Moisturizer",
                "Comb / Hairbrush"
            ],

            "Electronics": [
                "Phone Charger",
                "Charging Cable",
                "Power Bank",
                "Earphones / Headphones"
            ],

            "Documents": [
                "Aadhaar / ID Card",
                "Travel Tickets",
                "Hotel / Accommodation Details",
                "Emergency Contact Details"
            ],

            "Travel Essentials": [
                "Water Bottle",
                "Small Backpack / Day Bag",
                "Travel Pouch",
                "Tissues / Wet Wipes",
                "Small First-Aid Kit",
                "Reusable Bags"
            ],

            "Personal Essentials": [
                "Wallet",
                "Cash",
                "Personal Care Items",
                "Personal Medication, if applicable",
                "Hair Ties / Clips",
                "Personal Essentials"
            ]
        }


        # =================================
        # TRIP TYPE RULES
        # =================================

        trip_type_lower = trip_type.lower()


        # Beach / Vacation
        if "beach" in trip_type_lower or "vacation" in trip_type_lower:

            packing_list["Accessories"].extend([
                "Beachwear",
                "Beach Bag"
            ])

            packing_list["Footwear"].append(
                "Beach-friendly Footwear"
            )


        # Business
        if "business" in trip_type_lower:

            packing_list["Clothing"].extend([
                "Formal Outfit",
                "Formal Shirt / Top"
            ])

            packing_list["Footwear"].append(
                "Formal Shoes"
            )

            packing_list["Electronics"].append(
                "Laptop"
            )


        # College
        if "college" in trip_type_lower:

            packing_list["Clothing"].append(
                "Casual College Outfit"
            )

            packing_list["Footwear"].append(
                "Comfortable Sneakers"
            )

            packing_list["Documents"].append(
                "College ID Card"
            )

            packing_list["Travel Essentials"].append(
                "College Backpack"
            )


        # =================================
        # ACTIVITY RULES
        # =================================

        activity_list = activities.lower().split(",")


        for activity in activity_list:

            activity = activity.strip()


            # Beach
            if "beach" in activity:

                packing_list["Accessories"].extend([
                    "Beachwear",
                    "Sunglasses",
                    "Hat / Cap"
                ])

                packing_list["Footwear"].append(
                    "Sandals / Beach Slippers"
                )

                packing_list["Toiletries"].append(
                    "Extra Sunscreen"
                )


            # Rain
            if "rain" in activity:

                packing_list["Travel Essentials"].append(
                    "Umbrella"
                )

                packing_list["Footwear"].append(
                    "Rain-friendly Footwear"
                )


            # Hiking / Trekking
            if "hiking" in activity or "trek" in activity:

                packing_list["Footwear"].append(
                    "Trekking Shoes"
                )

                packing_list["Clothing"].append(
                    "Activewear"
                )

                packing_list["Travel Essentials"].append(
                    "Small Backpack"
                )


            # Swimming
            if "swimming" in activity:

                packing_list["Accessories"].append(
                    "Swimwear"
                )

                packing_list["Accessories"].append(
                    "Extra Towel"
                )


        # =================================
        # REMOVE DUPLICATES
        # =================================

        for category in packing_list:

            packing_list[category] = list(
                dict.fromkeys(
                    packing_list[category]
                )
            )


        return render_template(
            "packing_planner.html",
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            trip_type=trip_type,
            activities=activities,
            trip_days=trip_days,
            packing_list=packing_list
        )


    return render_template(
        "packing_planner.html",
        destination=None,
        start_date=None,
        end_date=None,
        trip_type=None,
        activities=None,
        trip_days=None,
        packing_list=None
    )   

    # =========================================
    # REMOVE DUPLICATE ITEMS
    # =========================================

    unique_outfit = []

    used_ids = set()


    for item in outfit:

        if item["id"] not in used_ids:

            unique_outfit.append(item)

            used_ids.add(item["id"])


    # =========================================
    # RECOMMENDED ITEMS
    # =========================================

    recommended_items = wardrobe_items


    recommended_items_data = []


    for item in recommended_items:

        recommended_items_data.append({
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "color": item["color"],
            "occasion": item["occasion"],
            "image": item["image"]
        })


    # =========================================
    # FINAL RESPONSE
    # =========================================

    return {

        "temperature": temperature,

        "feels_like": weather_data["main"]["feels_like"],

        "humidity": weather_data["main"]["humidity"],

        "condition": condition,

        "description": weather_data["weather"][0]["description"],

        "weather_category": weather_category,

        "outfit": unique_outfit,

        "recommended_items": recommended_items_data

    }

# ================================
# START APPLICATION
# ================================

if __name__ == "__main__":

    os.makedirs(
        UPLOAD_FOLDER,
        exist_ok=True
    )

    create_database()

    app.run(debug=True)