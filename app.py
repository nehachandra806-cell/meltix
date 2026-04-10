from flask import Flask, render_template, request, jsonify, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, inspect, text
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import hashlib
import json
import re
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'meltix-profile-secret'

# 🔥 NAYA CONNECTION: PostgreSQL 🔥
# Format: postgresql://username:password@localhost:5432/database_name
# 🔥 PERMANENT DATABASE LOGIC 🔥
# Agar code live server (Render) pe hai toh wahan ka database lega, 
# warna tere computer (localhost) par local database chalayega.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 
    'postgresql://postgres:meltix.candle.neha@localhost:5432/meltix_db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

AVATAR_FILENAMES = [f"avatar_{index}.jpg" for index in range(1, 18)]
DEFAULT_AVATAR_FILENAME = AVATAR_FILENAMES[0]

ORDER_STAGE_FLOW = [
    {
        "key": "placed",
        "label": "Order Placed",
        "description": "Your candle brief has been received and approved by the Meltix atelier.",
    },
    {
        "key": "wax_pouring",
        "label": "Wax Pouring",
        "description": "Our makers are pouring and shaping your candle vessel.",
    },
    {
        "key": "curing",
        "label": "Curing",
        "description": "Your candle is resting to ensure the fragrance and wax settle perfectly.",
    },
    {
        "key": "shipped",
        "label": "Shipped",
        "description": "Your parcel is in transit and moving toward your delivery address.",
    },
    {
        "key": "delivered",
        "label": "Delivered",
        "description": "Your order has arrived and is ready to light.",
    },
]

REWARD_TIERS = [
    {"level": 1, "points": 1000, "label": "Level 1: 50% Off Coupon"},
    {"level": 2, "points": 2000, "label": "Level 2: 70% Off Single Product"},
    {"level": 3, "points": 3000, "label": "Level 3: 80% Off Multiple Products"},
    {"level": 4, "points": 4000, "label": "Level 4: Premium Milestone"},
    {"level": 5, "points": 5000, "label": "Level 5: 1 Free Candle of your choice"},
]

MISSION_CATALOG = {
    1: [
        {"key": "welcome", "title": "Account Created", "description": "Activate your atelier and start your Meltix RPG journey."},
        {"key": "portrait_pick", "title": "Portrait Selected", "description": "Choose your first custom avatar portrait."},
        {"key": "wishlist_spark", "title": "Wishlist Spark", "description": "Save your first candle to the wishlist."},
        {"key": "scent_quiz", "title": "Scent Quiz Completed", "description": "Complete your scent quiz and reveal your signature notes."},
    ],
    2: [
        {"key": "first_review", "title": "First Review Posted", "description": "Publish your first review for the Meltix collection."},
        {"key": "first_order", "title": "First Order Placed", "description": "Place your first order and unlock deeper rewards."},
        {"key": "special_date", "title": "Special Date Added", "description": "Plan a special date moment inside your candle ritual."},
        {"key": "studio_visit", "title": "Studio Explorer", "description": "Explore the Meltix craft studio experience."},
    ],
    3: [
        {"key": "zodiac_hunter", "title": "Zodiac Hunter", "description": "Discover the zodiac candle that matches your sign."},
        {"key": "story_keeper", "title": "Story Keeper", "description": "Unlock the Story Candle collection and claim its lore."},
        {"key": "hidden_message", "title": "Hidden Message Found", "description": "Explore the Hidden Message candle experience."},
        {"key": "craft_studio", "title": "Craft Studio Visit", "description": "Dive deeper into how Meltix candles are crafted."},
    ],
    4: [
        {"key": "break_to_reveal", "title": "Break to Reveal Master", "description": "Explore the Break to Reveal collection."},
        {"key": "date_night", "title": "Date Night Curator", "description": "Check out the Candle Date Kit and plan the mood."},
        {"key": "gift_set_scout", "title": "Gift Set Scout", "description": "Explore the Gift Set collection for your next surprise."},
        {"key": "feedback_share", "title": "Atelier Feedback Shared", "description": "Submit feedback and help shape the Meltix experience."},
    ],
    5: [
        {"key": "easter_egg", "title": "Found the Secret Egg", "description": "Discover the secret Meltix easter egg hidden in the atelier."},
        {"key": "head_to_explorer", "title": "Head To Explorer", "description": "Unlock the Head To experience and complete the route."},
        {"key": "bug_reporter", "title": "Bug Hunter", "description": "Report a bug and help refine the atelier."},
        {"key": "melt_master", "title": "Melt Master", "description": "Complete your final prestige mission and become Meltix royalty."},
    ],
}

MAX_PLAYER_LEVEL = 5
MISSION_POINTS = 250
MISSION_LOOKUP = {
    mission["key"]: {**mission, "level": level}
    for level, missions in MISSION_CATALOG.items()
    for mission in missions
}

LEVEL_REWARD_COUPONS = {
    2: {
        "code": "LVL2-HALF50",
        "title": "Level 2 Welcome Drop",
        "description": "50% off your next Meltix checkout.",
        "discount_percentage": 50,
        "max_uses": 1,
        "expires_at": None,
        "is_active": True,
    },
    3: {
        "code": "LVL3-SINGLE70",
        "title": "Level 3 Solo Boost",
        "description": "70% off on any single handcrafted candle.",
        "discount_percentage": 70,
        "max_uses": 1,
        "expires_at": None,
        "is_active": True,
    },
    4: {
        "code": "LVL4-MULTI80",
        "title": "Level 4 Haul Reward",
        "description": "80% off your entire cart when buying multiple items.",
        "discount_percentage": 80,
        "max_uses": 1,
        "expires_at": None,
        "is_active": True,
    },
}
LEVEL_REWARD_COUPONS_BY_CODE = {
    coupon_data["code"]: {**coupon_data, "level": level}
    for level, coupon_data in LEVEL_REWARD_COUPONS.items()
}
ALLOWED_REWARD_COUPON_CODES = set(LEVEL_REWARD_COUPONS_BY_CODE.keys())

SCENT_KEYWORDS = {
    "Vanilla": ["vanilla", "cream", "dessert", "cake", "sweet"],
    "Lavender": ["lavender", "calm", "sleep", "soothe"],
    "Sandalwood": ["sandalwood", "wood", "woody", "sandal"],
    "Amber": ["amber", "resin", "warm"],
    "Rose": ["rose", "floral", "petal"],
    "Jasmine": ["jasmine", "white floral"],
    "Cedar": ["cedar", "cedarwood", "forest"],
    "Citrus": ["citrus", "orange", "bergamot", "lemon"],
    "Musk": ["musk", "powder", "soft"],
    "Coffee": ["coffee", "espresso", "latte", "mocha"],
    "Cocoa": ["cocoa", "chocolate"],
}


def avatar_required_level(avatar_index):
    if avatar_index <= 5:
        return 1
    if avatar_index <= 8:
        return 2
    if avatar_index <= 11:
        return 3
    if avatar_index <= 14:
        return 4
    return 5


def avatar_required_level_for_filename(filename):
    try:
        avatar_index = AVATAR_FILENAMES.index(filename) + 1
    except ValueError:
        return None
    return avatar_required_level(avatar_index)


def sanitize_avatar_filename(filename, player_level=None):
    if filename not in AVATAR_FILENAMES:
        return ''

    required_level = avatar_required_level_for_filename(filename)
    if player_level is not None and required_level and player_level < required_level:
        return ''

    return filename


AVATAR_NAMES = {
    "avatar_1.jpg": "Cozy Jar",
    "avatar_2.jpg": "Bubble Dream",
    "avatar_3.jpg": "Sweet Cupcake",
    "avatar_4.jpg": "Botanical Bowl",
    "avatar_5.jpg": "Earthy Pot",
    "avatar_6.jpg": "Classic Pillar",
    "avatar_7.jpg": "Midnight Melt",
    "avatar_8.jpg": "Pastel Dream",
    "avatar_9.jpg": "Bath Retreat",
    "avatar_10.jpg": "Pink Twist",
    "avatar_11.jpg": "Emerald Plinth",
    "avatar_12.jpg": "Sweetheart",
    "avatar_13.jpg": "Golden Aura",
    "avatar_14.jpg": "Vanilla Swirl",
    "avatar_15.jpg": "Obsidian Flame",
    "avatar_16.jpg": "Rose Petal",
    "avatar_17.jpg": "Crystal Ember",
}

def build_avatar_options():
    return [
        {
            'filename': filename,
            'label': AVATAR_NAMES.get(filename, f"Avatar {index:02d}"),
            'src': url_for('static', filename=f'images/avatar/{filename}'),
            'required_level': avatar_required_level(index)
        }
        for index, filename in enumerate(AVATAR_FILENAMES, start=1)
    ]


def avatar_label_for_filename(filename):
    for avatar in build_avatar_options():
        if avatar['filename'] == filename:
            return avatar['label']
    return "Custom Avatar"


def public_avatar_filename(filename):
    return sanitize_avatar_filename(filename) or DEFAULT_AVATAR_FILENAME


def public_avatar_url(filename):
    return url_for('static', filename=f'images/avatar/{public_avatar_filename(filename)}')


def public_profile_identity(profile_record, fallback_name='Meltix Collector'):
    display_name = fallback_name
    level = 1
    avatar_filename = DEFAULT_AVATAR_FILENAME
    avatar_url = public_avatar_url(avatar_filename)

    if profile_record:
        display_name = (profile_record.display_name or '').strip() or fallback_name
        level = normalize_level(profile_record.level)
        
        # KEY FIX: Serve Google Photo if custom avatar is empty
        if not profile_record.avatar_filename and profile_record.google_picture_url:
            avatar_filename = '' 
            avatar_url = profile_record.google_picture_url
        else:
            avatar_filename = public_avatar_filename(profile_record.avatar_filename)
            avatar_url = public_avatar_url(avatar_filename)

    return {
        'display_name': display_name,
        'level': level,
        'avatar_filename': avatar_filename,
        'avatar_url': avatar_url,
    }

# ==========================================
# 🔴 DATABASE MODELS (TABLES) 🔴
# ==========================================

# Tera Product Table Model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    image_file = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    likes = db.Column(db.Integer, default=0) 

    def __repr__(self):
        return f"Product('{self.name}', Likes: {self.likes})"


class ProductLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user_account.id'), nullable=False)

    __table_args__ = (db.UniqueConstraint('product_id', 'user_id', name='unique_user_product_like'),)

# Tera Review Table Model
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, nullable=False) # Ye batayega kis candle ka review hai
    user_id = db.Column(db.Integer, db.ForeignKey('user_account.id'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    review_text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False) # 1 se 5 tak star rating
    created_at = db.Column(db.DateTime, default=datetime.utcnow) # Review ka time

    # 🔴 STRICT RULE: 1 User = 1 Review per product
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='unique_user_review'),)

    # Cascade Delete: Review delete hoga toh uske saare likes bhi automatically ud jayenge
    review_likes = db.relationship('ReviewLike', backref='review', cascade="all, delete-orphan")

    def __repr__(self):
        return f"Review('{self.user_name}', Rating: {self.rating}, Product: {self.product_id})"

# 🔴 NAYA TABLE: Review Likes (1 User = 1 Action per review)
class ReviewLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user_account.id'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    action_type = db.Column(db.String(10), nullable=False) # 'like' ya 'dislike'

    # STRICT RULE: Ek review pe ek banda ek hi baar like/dislike save kar sake
    __table_args__ = (db.UniqueConstraint('review_id', 'user_id', name='unique_user_review_like'),)


class Coupon(db.Model):
    __tablename__ = 'coupon'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    discount_percentage = db.Column(db.Integer, nullable=False)
    max_uses = db.Column(db.Integer, nullable=True)
    current_uses = db.Column(db.Integer, nullable=False, default=0)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"Coupon('{self.code}', {self.discount_percentage}% off)"


class UserAccount(db.Model):
    __tablename__ = 'user_account'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False, default='Guest')
    avatar_filename = db.Column(db.String(50), nullable=False, default='')
    google_picture_url = db.Column(db.Text, nullable=False, default='')
    glow_points = db.Column(db.Integer, nullable=False, default=0)
    level = db.Column(db.Integer, nullable=False, default=1)
    completed_missions_json = db.Column(db.Text, nullable=False, default='[]')
    unlocked_coupons = db.Column(db.Text, nullable=False, default='[]')
    lifetime_spend = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    phone = db.Column(db.String(25), nullable=False, default='')
    shipping_name = db.Column(db.String(120), nullable=False, default='')
    shipping_line1 = db.Column(db.String(160), nullable=False, default='')
    shipping_line2 = db.Column(db.String(160), nullable=False, default='')
    shipping_city = db.Column(db.String(80), nullable=False, default='')
    shipping_state = db.Column(db.String(80), nullable=False, default='')
    shipping_postal_code = db.Column(db.String(20), nullable=False, default='')
    shipping_country = db.Column(db.String(60), nullable=False, default='India')

    billing_same_as_shipping = db.Column(db.Boolean, nullable=False, default=True)
    billing_name = db.Column(db.String(120), nullable=False, default='')
    billing_line1 = db.Column(db.String(160), nullable=False, default='')
    billing_line2 = db.Column(db.String(160), nullable=False, default='')
    billing_city = db.Column(db.String(80), nullable=False, default='')
    billing_state = db.Column(db.String(80), nullable=False, default='')
    billing_postal_code = db.Column(db.String(20), nullable=False, default='')
    billing_country = db.Column(db.String(60), nullable=False, default='India')

    reviews = db.relationship('Review', backref='author', lazy='dynamic')

    def __repr__(self):
        return f"UserAccount('{self.email}', Avatar: {self.avatar_filename})"


class ProfileOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False, index=True)
    order_code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    stage_key = db.Column(db.String(30), nullable=False, default='placed')
    status_label = db.Column(db.String(80), nullable=False, default='Order Placed')
    tracking_note = db.Column(
        db.String(220),
        nullable=False,
        default='Your order has been received by the Meltix atelier.'
    )
    subtotal = db.Column(db.Integer, nullable=False, default=0)
    shipping_fee = db.Column(db.Integer, nullable=False, default=0)
    total_amount = db.Column(db.Integer, nullable=False, default=0)
    currency = db.Column(db.String(10), nullable=False, default='INR')
    item_count = db.Column(db.Integer, nullable=False, default=0)
    line_items_json = db.Column(db.Text, nullable=False, default='[]')
    scent_notes_json = db.Column(db.Text, nullable=False, default='[]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserScentPersona(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False, default='')
    description = db.Column(db.Text, nullable=False, default='')
    notes_json = db.Column(db.Text, nullable=False, default='[]')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Wishlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False) # Google login ke baad wali email
    product_id = db.Column(db.Integer, nullable=False)
    
    # STRICT RULE: Ek user ek product ko ek hi baar wishlist me daal sake
    __table_args__ = (db.UniqueConstraint('user_email', 'product_id', name='unique_user_wishlist'),)


def calculate_lifetime_spend_total(user_email, executor=None):
    if not user_email:
        return 0

    runner = executor or db.session
    result = runner.execute(
        text("""
            SELECT COALESCE(SUM(CASE WHEN total_amount > 0 THEN total_amount ELSE 0 END), 0)
            FROM profile_order
            WHERE user_email = :user_email
        """),
        {"user_email": user_email},
    )
    return int(result.scalar() or 0)


def sync_lifetime_spend_for_user(user_email, connection=None):
    if not user_email:
        return 0

    total_spend = calculate_lifetime_spend_total(user_email, executor=connection)
    if connection is not None:
        connection.execute(
            text("""
                UPDATE user_account
                SET lifetime_spend = :total_spend
                WHERE email = :user_email
            """),
            {"user_email": user_email, "total_spend": total_spend},
        )
    else:
        profile_record = UserAccount.query.filter_by(email=user_email).first()
        if profile_record:
            profile_record.lifetime_spend = total_spend
    return total_spend


def backfill_all_lifetime_spend():
    with db.engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE user_account AS ua
                SET lifetime_spend = COALESCE((
                    SELECT SUM(CASE WHEN po.total_amount > 0 THEN po.total_amount ELSE 0 END)
                    FROM profile_order AS po
                    WHERE po.user_email = ua.email
                ), 0)
            """)
        )


@event.listens_for(ProfileOrder, 'after_insert')
@event.listens_for(ProfileOrder, 'after_update')
@event.listens_for(ProfileOrder, 'after_delete')
def update_lifetime_spend_after_order_change(mapper, connection, target):
    sync_lifetime_spend_for_user(getattr(target, 'user_email', ''), connection=connection)

def ensure_profile_schema():
    inspector = inspect(db.engine)
    user_columns = {column['name'] for column in inspector.get_columns('user_account')}

    if 'level' not in user_columns:
        with db.engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE user_account ADD COLUMN level INTEGER NOT NULL DEFAULT 1")
            )

    if 'completed_missions_json' not in user_columns:
        with db.engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE user_account ADD COLUMN completed_missions_json TEXT NOT NULL DEFAULT '[]'")
            )

    if 'unlocked_coupons' not in user_columns:
        with db.engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE user_account ADD COLUMN unlocked_coupons TEXT NOT NULL DEFAULT '[]'")
            )

    if 'lifetime_spend' not in user_columns:
        with db.engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE user_account ADD COLUMN lifetime_spend INTEGER NOT NULL DEFAULT 0")
            )

    if 'google_picture_url' not in user_columns:
        with db.engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE user_account ADD COLUMN google_picture_url TEXT NOT NULL DEFAULT ''")
            )


def ensure_coupon_catalog():
    reward_codes = [coupon_data["code"] for coupon_data in LEVEL_REWARD_COUPONS.values()]
    existing_coupons = {
        coupon.code: coupon
        for coupon in Coupon.query.filter(Coupon.code.in_(reward_codes)).all()
    }

    catalog_changed = False
    for level, coupon_data in LEVEL_REWARD_COUPONS.items():
        coupon = existing_coupons.get(coupon_data["code"])
        if not coupon:
            coupon = Coupon(code=coupon_data["code"])
            db.session.add(coupon)
            catalog_changed = True

        if coupon.discount_percentage != coupon_data["discount_percentage"]:
            coupon.discount_percentage = coupon_data["discount_percentage"]
            catalog_changed = True
        if coupon.max_uses != coupon_data["max_uses"]:
            coupon.max_uses = coupon_data["max_uses"]
            catalog_changed = True
        if coupon.expires_at != coupon_data["expires_at"]:
            coupon.expires_at = coupon_data["expires_at"]
            catalog_changed = True
        if coupon.is_active != coupon_data["is_active"]:
            coupon.is_active = coupon_data["is_active"]
            catalog_changed = True
        if coupon.current_uses is None:
            coupon.current_uses = 0
            catalog_changed = True

    for coupon in Coupon.query.filter(Coupon.code.like('LVL%')).all():
        if coupon.code not in ALLOWED_REWARD_COUPON_CODES and coupon.is_active:
            coupon.is_active = False
            catalog_changed = True

    if catalog_changed:
        db.session.commit()


# Ye line chalte hi PostgreSQL mein saari tables aur rules ban jayenge
with app.app_context():
    db.create_all()
    ensure_profile_schema()
    backfill_all_lifetime_spend()
    ensure_coupon_catalog()


def safe_json_loads(raw_value, fallback):
    if raw_value in (None, ''):
        return fallback
    try:
        return json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def normalize_completed_missions(raw_value):
    normalized = []
    for mission_key in safe_json_loads(raw_value, []):
        clean_key = str(mission_key).strip()
        if clean_key and clean_key in MISSION_LOOKUP and clean_key not in normalized:
            normalized.append(clean_key)
    return normalized


def normalize_unlocked_coupons(raw_value):
    normalized = []
    for coupon_code in safe_json_loads(raw_value, []):
        clean_code = str(coupon_code).strip().upper()
        if clean_code and clean_code in ALLOWED_REWARD_COUPON_CODES and clean_code not in normalized:
            normalized.append(clean_code)
    return normalized


def normalize_level(level_value):
    try:
        normalized = int(level_value or 1)
    except (TypeError, ValueError):
        normalized = 1
    return max(1, min(MAX_PLAYER_LEVEL, normalized))


def get_level_missions(level_value, completed_missions=None):
    current_level = normalize_level(level_value)
    completed_set = set(completed_missions or [])
    missions = []

    for mission in MISSION_CATALOG.get(current_level, []):
        missions.append(
            {
                "key": mission["key"],
                "title": mission["title"],
                "description": mission["description"],
                "level": current_level,
                "points": MISSION_POINTS,
                "completed": mission["key"] in completed_set,
            }
        )

    return missions


def coupon_is_available(coupon_record):
    if not coupon_record:
        return False
    if not coupon_record.is_active:
        return False
    if coupon_record.expires_at and coupon_record.expires_at < datetime.utcnow():
        return False
    if coupon_record.max_uses is not None and coupon_record.current_uses >= coupon_record.max_uses:
        return False
    return True


def build_reward_vault(unlocked_coupons):
    if not unlocked_coupons:
        return []

    coupon_rows = {
        coupon.code: coupon
        for coupon in Coupon.query.filter(Coupon.code.in_(unlocked_coupons)).all()
    }
    reward_vault = []

    for coupon_code in unlocked_coupons:
        coupon = coupon_rows.get(coupon_code)
        catalog_coupon = LEVEL_REWARD_COUPONS_BY_CODE.get(coupon_code, {})
        max_uses = coupon.max_uses if coupon else catalog_coupon.get("max_uses")
        current_uses = coupon.current_uses if coupon else 0
        expires_at = coupon.expires_at if coupon else catalog_coupon.get("expires_at")
        is_active = coupon.is_active if coupon else catalog_coupon.get("is_active", True)
        remaining_uses = None if max_uses is None else max(max_uses - current_uses, 0)

        reward_vault.append(
            {
                "code": coupon_code,
                "title": catalog_coupon.get("title", "Exclusive Reward Code"),
                "description": catalog_coupon.get("description", "Use this code during checkout to redeem your atelier reward."),
                "level": catalog_coupon.get("level"),
                "discount_percentage": coupon.discount_percentage if coupon else catalog_coupon.get("discount_percentage", 0),
                "max_uses": max_uses,
                "current_uses": current_uses,
                "remaining_uses": remaining_uses,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "expires_at_display": expires_at.strftime("%d %b %Y") if expires_at else "No expiry",
                "is_active": bool(is_active),
                "is_available": coupon_is_available(coupon) if coupon else bool(is_active),
                "status_text": (
                    "Ready to use"
                    if (coupon_is_available(coupon) if coupon else bool(is_active))
                    else (
                        "Expired"
                        if expires_at and expires_at < datetime.utcnow()
                        else "Unavailable"
                    )
                ),
            }
        )

    return reward_vault


def unlock_level_coupon(profile_record, level_value):
    unlocked_coupons = normalize_unlocked_coupons(profile_record.unlocked_coupons)
    reward_coupon = LEVEL_REWARD_COUPONS.get(normalize_level(level_value))
    granted_code = None

    if reward_coupon and reward_coupon["code"] not in unlocked_coupons:
        unlocked_coupons.append(reward_coupon["code"])
        granted_code = reward_coupon["code"]

    profile_record.unlocked_coupons = json.dumps(unlocked_coupons)
    return unlocked_coupons, granted_code


def sync_unlocked_coupons_for_level(profile_record):
    raw_coupons = safe_json_loads(profile_record.unlocked_coupons, [])
    unlocked_coupons = normalize_unlocked_coupons(profile_record.unlocked_coupons)
    normalized_existing = []

    for coupon_code in raw_coupons:
        clean_code = str(coupon_code).strip().upper()
        if clean_code and clean_code not in normalized_existing:
            normalized_existing.append(clean_code)

    changed = unlocked_coupons != normalized_existing

    for level_value in range(2, normalize_level(profile_record.level) + 1):
        reward_coupon = LEVEL_REWARD_COUPONS.get(level_value)
        if reward_coupon and reward_coupon["code"] not in unlocked_coupons:
            unlocked_coupons.append(reward_coupon["code"])
            changed = True

    if changed or profile_record.unlocked_coupons in (None, ''):
        profile_record.unlocked_coupons = json.dumps(unlocked_coupons)

    return unlocked_coupons, changed


def get_session_user():
    session_email = (session.get('profile_email') or '').strip().lower()
    if not session_email:
        return None
    return UserAccount.query.filter_by(email=session_email).first()


def parse_money_value(value):
    if isinstance(value, (int, float)):
        return int(round(float(value)))

    if isinstance(value, str):
        cleaned = re.sub(r'[^0-9.]', '', value.strip())
        if not cleaned:
            return 0
        try:
            return int(round(float(cleaned)))
        except ValueError:
            return 0

    return 0


def parse_datetime_value(value):
    if isinstance(value, datetime):
        return value

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except (OSError, OverflowError, ValueError):
            return datetime.utcnow()

    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return datetime.utcnow()

        try:
            return datetime.fromisoformat(candidate.replace('Z', '+00:00')).replace(tzinfo=None)
        except ValueError:
            for fmt in ("%d %b %Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(candidate, fmt)
                except ValueError:
                    continue

    return datetime.utcnow()


def format_money(amount):
    return f"INR {int(amount):,}"


def get_stage_config(stage_key):
    for stage in ORDER_STAGE_FLOW:
        if stage["key"] == stage_key:
            return stage
    return ORDER_STAGE_FLOW[0]


def infer_stage_key(source_value):
    raw = (source_value or '').strip().lower()
    if any(keyword in raw for keyword in ("delivered", "complete", "completed")):
        return "delivered"
    if any(keyword in raw for keyword in ("shipped", "dispatch", "in transit", "courier")):
        return "shipped"
    if any(keyword in raw for keyword in ("curing", "cure", "resting", "setting")):
        return "curing"
    if any(keyword in raw for keyword in ("wax", "pour", "craft", "making", "production")):
        return "wax_pouring"
    return "placed"


def build_tracking_timeline(stage_key):
    current_index = next(
        (index for index, stage in enumerate(ORDER_STAGE_FLOW) if stage["key"] == stage_key),
        0,
    )

    timeline = []
    for index, stage in enumerate(ORDER_STAGE_FLOW):
        timeline.append(
            {
                "key": stage["key"],
                "label": stage["label"],
                "description": stage["description"],
                "complete": index < current_index,
                "current": index == current_index,
                "locked": index > current_index,
            }
        )

    return timeline


def deterministic_order_code(email, order_payload, fallback_index):
    explicit_code = (
        order_payload.get("order_id")
        or order_payload.get("id")
        or order_payload.get("reference")
        or order_payload.get("code")
    )
    if explicit_code:
        return str(explicit_code).strip().upper()

    normalized_payload = json.dumps(order_payload, sort_keys=True, default=str)
    digest = hashlib.md5(f"{email}:{normalized_payload}:{fallback_index}".encode("utf-8")).hexdigest()
    return f"MX-{digest[:10].upper()}"


def normalize_order_items(raw_items):
    items = raw_items
    if isinstance(items, str):
        items = safe_json_loads(items, [])

    if not isinstance(items, list):
        return []

    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        quantity = item.get("quantity") or item.get("qty") or 1
        try:
            quantity = max(1, int(quantity))
        except (TypeError, ValueError):
            quantity = 1

        normalized.append(
            {
                "name": item.get("name") or item.get("title") or "Meltix Candle",
                "quantity": quantity,
                "price": parse_money_value(item.get("price") or item.get("amount") or 0),
                "fragrance": (
                    item.get("fragrance")
                    or item.get("scent")
                    or item.get("signature_notes")
                    or item.get("notes")
                    or ""
                ),
            }
        )

    return normalized


def extract_scent_notes(order_payload, items):
    note_sources = []

    for key in ("fragrance", "scent", "signature_notes", "notes", "custom_note", "custom_notes"):
        value = order_payload.get(key)
        if value:
            note_sources.append(str(value))

    for item in items:
        if item.get("fragrance"):
            note_sources.append(str(item["fragrance"]))
        if item.get("name"):
            note_sources.append(str(item["name"]))

    matches = {}
    joined_source = " ".join(note_sources).lower()
    for note, keywords in SCENT_KEYWORDS.items():
        score = sum(joined_source.count(keyword) for keyword in keywords)
        if score > 0:
            matches[note] = score

    sorted_notes = sorted(matches.items(), key=lambda item: (-item[1], item[0]))
    return [note for note, _score in sorted_notes[:5]]


def serialize_address(address_record):
    if not address_record:
        return {
            "phone_number": "",
            "shipping": {
                "name": "",
                "line1": "",
                "line2": "",
                "city": "",
                "state": "",
                "postal_code": "",
                "country": "India",
            },
            "billing_same_as_shipping": True,
            "billing": {
                "name": "",
                "line1": "",
                "line2": "",
                "city": "",
                "state": "",
                "postal_code": "",
                "country": "India",
            },
        }

    return {
        "phone_number": address_record.phone,
        "shipping": {
            "name": address_record.shipping_name,
            "line1": address_record.shipping_line1,
            "line2": address_record.shipping_line2,
            "city": address_record.shipping_city,
            "state": address_record.shipping_state,
            "postal_code": address_record.shipping_postal_code,
            "country": address_record.shipping_country,
        },
        "billing_same_as_shipping": address_record.billing_same_as_shipping,
        "billing": {
            "name": address_record.billing_name,
            "line1": address_record.billing_line1,
            "line2": address_record.billing_line2,
            "city": address_record.billing_city,
            "state": address_record.billing_state,
            "postal_code": address_record.billing_postal_code,
            "country": address_record.billing_country,
        },
    }


def serialize_order(order_record):
    items = safe_json_loads(order_record.line_items_json, [])
    scent_notes = safe_json_loads(order_record.scent_notes_json, [])
    stage = get_stage_config(order_record.stage_key)
    return {
        "order_id": order_record.order_code,
        "date": order_record.created_at.strftime("%d %b %Y"),
        "created_at": order_record.created_at.isoformat(),
        "status": order_record.status_label,
        "stage_key": order_record.stage_key,
        "stage_label": stage["label"],
        "tracking_note": order_record.tracking_note,
        "timeline": build_tracking_timeline(order_record.stage_key),
        "subtotal": order_record.subtotal,
        "shipping_fee": order_record.shipping_fee,
        "total": order_record.total_amount,
        "total_display": format_money(order_record.total_amount),
        "currency": order_record.currency,
        "item_count": order_record.item_count,
        "items": items,
        "scent_notes": scent_notes,
    }


def build_glow_ledger(profile_record, orders, reviews):
    entries = []

    for order in orders:
        entries.append(
            {
                "title": "Order Reward",
                "description": f"Reward credited for order {order.order_code}.",
                "points": 100,
                "date_value": order.created_at,
            }
        )

    for review in reviews:
        entries.append(
            {
                "title": "Review Reward",
                "description": f"Reward credited for review on product #{review.product_id}.",
                "points": 50,
                "date_value": review.created_at,
            }
        )

    claimed_missions = normalize_completed_missions(profile_record.completed_missions_json)
    for mission_key in claimed_missions:
        mission_data = MISSION_LOOKUP.get(mission_key, {"title": mission_key.replace('_', ' ').title()})
        mission_title = mission_data["title"]
        mission_date = profile_record.created_at if mission_key == 'welcome' else (profile_record.updated_at or profile_record.created_at)
        entries.append(
            {
                "title": mission_title,
                "description": f"Mission cleared: {mission_title}.",
                "points": MISSION_POINTS,
                "date_value": mission_date,
            }
        )

    entries.sort(key=lambda entry: entry["date_value"], reverse=True)
    total_points = sum(entry["points"] for entry in entries)

    if total_points >= 5000:
        is_max_level = True
        progress_percent = 100
        points_to_next = 0
        next_reward_label = "You have achieved max lvl. Stay tuned for more challenges!"
    else:
        is_max_level = False
        previous_tier = 0
        next_tier = None
        for tier in REWARD_TIERS:
            if total_points < tier["points"]:
                next_tier = tier
                break
            previous_tier = tier["points"]

        if next_tier:
            tier_span = max(next_tier["points"] - previous_tier, 1)
            progress_percent = int(((total_points - previous_tier) / tier_span) * 100)
            points_to_next = max(next_tier["points"] - total_points, 0)
            next_reward_label = next_tier["label"]
        else:
            progress_percent = 100
            points_to_next = 0
            next_reward_label = "You have achieved max lvl. Stay tuned for more challenges!"

    return {
        "current_points": total_points,
        "progress_percent": progress_percent,
        "points_to_next_reward": points_to_next,
        "next_reward_label": next_reward_label,
        "is_max_level": is_max_level,
        "ledger": [
            {
                "title": entry["title"],
                "description": entry["description"],
                "points": entry["points"],
                "date": entry["date_value"].strftime("%d %b %Y"),
            }
            for entry in entries[:8]
        ],
    }


def derive_scent_persona(profile_record, orders, explicit_persona=None):
    if explicit_persona and explicit_persona.get("notes"):
        return explicit_persona

    note_counts = {}
    for order in orders:
        for note in safe_json_loads(order.scent_notes_json, []):
            note_counts[note] = note_counts.get(note, 0) + 1

    if not note_counts:
        return {
            "title": "Discover Your Signature Notes",
            "description": "Take the scent quiz to reveal the fragrance family that suits your private atelier.",
            "notes": [],
            "has_data": False,
            "cta_label": "Take the Scent Quiz",
        }

    top_notes = [note for note, _count in sorted(note_counts.items(), key=lambda item: (-item[1], item[0]))[:3]]
    return {
        "title": "Your Signature Notes",
        "description": f"{profile_record.display_name} naturally leans toward {', '.join(top_notes)}.",
        "notes": top_notes,
        "has_data": True,
        "cta_label": "Refresh Persona",
    }


def get_or_create_profile(email, display_name=None):
    normalized_email = (email or '').strip().lower()
    readable_name = (display_name or '').strip() or normalized_email.split('@')[0] or 'Guest'

    profile_record = UserAccount.query.filter_by(email=normalized_email).first()
    if not profile_record:
        profile_record = UserAccount(
            email=normalized_email,
            display_name=readable_name,
            avatar_filename=''
        )
        db.session.add(profile_record)
    else:
        if readable_name and readable_name != 'Guest':
            profile_record.display_name = readable_name

    sync_unlocked_coupons_for_level(profile_record)

    return profile_record


def sync_profile_orders(user_email, orders_payload):
    if not isinstance(orders_payload, list):
        return

    for index, raw_order in enumerate(orders_payload):
        if not isinstance(raw_order, dict):
            continue

        order_code = deterministic_order_code(user_email, raw_order, index)
        order_record = ProfileOrder.query.filter_by(order_code=order_code).first()
        if not order_record:
            order_record = ProfileOrder(user_email=user_email, order_code=order_code)
            db.session.add(order_record)

        items = normalize_order_items(raw_order.get("items", []))
        scent_notes = extract_scent_notes(raw_order, items)
        stage_key = infer_stage_key(raw_order.get("stage") or raw_order.get("status"))
        stage = get_stage_config(stage_key)
        subtotal = parse_money_value(raw_order.get("subtotal"))
        shipping_fee = parse_money_value(raw_order.get("shipping_fee") or raw_order.get("shipping") or 0)
        total_amount = parse_money_value(raw_order.get("total") or raw_order.get("amount") or subtotal)
        if total_amount == 0 and subtotal:
            total_amount = subtotal + shipping_fee
        if subtotal == 0 and total_amount:
            subtotal = max(total_amount - shipping_fee, 0)

        order_record.user_email = user_email
        order_record.stage_key = stage_key
        order_record.status_label = stage["label"]
        order_record.tracking_note = stage["description"]
        order_record.subtotal = subtotal
        order_record.shipping_fee = shipping_fee
        order_record.total_amount = total_amount
        order_record.currency = (raw_order.get("currency") or "INR").upper()
        order_record.item_count = (
            sum(item["quantity"] for item in items)
            if items
            else int(raw_order.get("item_count") or 0)
        )
        order_record.line_items_json = json.dumps(items)
        order_record.scent_notes_json = json.dumps(scent_notes)
        order_record.created_at = parse_datetime_value(raw_order.get("date") or raw_order.get("created_at"))

    sync_lifetime_spend_for_user(user_email)


def serialize_profile(profile_record, google_picture_url=None, use_google_picture=False):
    completed_missions = normalize_completed_missions(profile_record.completed_missions_json)
    unlocked_coupons = normalize_unlocked_coupons(profile_record.unlocked_coupons)
    current_level = normalize_level(profile_record.level)
    current_identity = public_profile_identity(profile_record, fallback_name=profile_record.display_name or 'Meltix Collector')
    current_level_missions = get_level_missions(current_level, completed_missions)
    reward_vault = build_reward_vault(unlocked_coupons)
    wishlist_rows = Wishlist.query.filter_by(user_email=profile_record.email).order_by(Wishlist.id.desc()).all()
    wishlist_items = []

    for row in wishlist_rows:
        product = db.session.get(Product, row.product_id)
        wishlist_items.append({
            'product_id': row.product_id,
            'name': product.name if product else f"Meltix Candle #{row.product_id}",
            'price': product.price if product else 999,
            'likes': product.likes if product else 0,
            'image_url': (
                url_for('static', filename=f"images/{product.image_file}")
                if product and product.image_file else None
            )
        })

    all_reviews = Review.query.filter(Review.user_id == profile_record.id).order_by(Review.created_at.desc()).all()
    review_ids = [review.id for review in all_reviews]

    total_review_likes = 0
    total_review_dislikes = 0
    review_action_map = {}

    if review_ids:
        review_actions = ReviewLike.query.filter(ReviewLike.review_id.in_(review_ids)).all()
        for action in review_actions:
            action_counts = review_action_map.setdefault(action.review_id, {'likes': 0, 'dislikes': 0})
            if action.action_type == 'like':
                action_counts['likes'] += 1
                total_review_likes += 1
            elif action.action_type == 'dislike':
                action_counts['dislikes'] += 1
                total_review_dislikes += 1

    recent_reviews = all_reviews[:5]
    review_items = [
        {
            'product_id': review.product_id,
            'rating': review.rating,
            'review_text': review.review_text,
            'date': review.created_at.strftime("%d %b %Y"),
            'likes': review_action_map.get(review.id, {}).get('likes', 0),
            'dislikes': review_action_map.get(review.id, {}).get('dislikes', 0),
            'display_name': current_identity['display_name'],
            'author_level': current_identity['level'],
            'author_avatar_filename': current_identity['avatar_filename'],
            'author_avatar_url': current_identity['avatar_url'],
        }
        for review in recent_reviews
    ]

    orders = ProfileOrder.query.filter_by(user_email=profile_record.email).order_by(ProfileOrder.created_at.desc()).all()
    serialized_orders = [serialize_order(order) for order in orders]
    orders_in_progress = sum(1 for order in orders if order.stage_key != 'delivered')
    total_spent = sum(max(order.total_amount, 0) for order in orders)
    lifetime_spend = max(int(profile_record.lifetime_spend or 0), total_spent)
    rewards = build_glow_ledger(profile_record, orders, all_reviews)

    scent_persona_record = UserScentPersona.query.filter_by(user_email=profile_record.email).first()
    explicit_persona = None
    if scent_persona_record:
        explicit_persona = {
            'title': scent_persona_record.title,
            'description': scent_persona_record.description,
            'notes': safe_json_loads(scent_persona_record.notes_json, []),
            'has_data': True,
            'cta_label': 'Refresh Persona'
        }
    scent_persona = derive_scent_persona(profile_record, orders, explicit_persona=explicit_persona)

    address_book = serialize_address(profile_record)

    has_custom_avatar = bool(profile_record.avatar_filename)
    avatar_url = None
    avatar_label = "Awaiting Sign-In"

    if use_google_picture and google_picture_url:
        avatar_url = google_picture_url
        avatar_label = "Google Profile Photo"
    elif has_custom_avatar:
        avatar_url = url_for('static', filename=f"images/avatar/{profile_record.avatar_filename}")
        avatar_label = avatar_label_for_filename(profile_record.avatar_filename)

    return {
        'display_name': profile_record.display_name,
        'email': profile_record.email,
        'avatar_filename': profile_record.avatar_filename,
        'avatar_url': avatar_url,
        'avatar_label': avatar_label,
        'using_google_avatar': bool(use_google_picture and google_picture_url),
        'level': current_level,
        'member_since': profile_record.created_at.strftime("%b %Y"),
        'stats': {
            'wishlist_count': len(wishlist_items),
            'review_count': len(all_reviews),
            'review_likes': total_review_likes,
            'review_dislikes': total_review_dislikes,
            'orders_in_progress': orders_in_progress,
            'order_count': len(orders),
            'total_spent': lifetime_spend,
            'total_spent_display': format_money(lifetime_spend),
            'lifetime_spend': lifetime_spend,
            'lifetime_spend_display': format_money(lifetime_spend),
            'avatar_count': len(AVATAR_FILENAMES),
            'level': current_level
        },
        'wishlist_items': wishlist_items,
        'recent_reviews': review_items,
        'orders': serialized_orders,
        'address_book': address_book,
        'rewards': rewards,
        'scent_persona': scent_persona,
        'completed_missions': completed_missions,
        'current_level_missions': current_level_missions,
        'unlocked_coupons': unlocked_coupons,
        'reward_vault': reward_vault
    }

# ==========================================
# 🔴 FRONTEND PAGE ROUTES (Untouched) 🔴
# ==========================================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/shop')
def shop():
    return render_template('shop.html')

@app.route('/hidden-message')
def hidden_message():
    return render_template('hidden_message.html')

@app.route('/story-candle')
def story_candle():
    return render_template('story_candle.html')

@app.route('/zodiac-candle')
def zodiac_candle():
    return render_template('zodiac_candle.html')

@app.route('/break-to-reveal')
def break_to_reveal():
    return render_template('break_to_reveal.html')

@app.route('/candle-date-kit')
def candle_date_kit():
    return render_template('candle_date_kit.html')

@app.route('/about-us')
def about_us():
    return render_template('about_us.html')

@app.route('/contact-us')
def contact_us():
    return render_template('contact_us.html')

@app.route('/craft-studio')
def craft_studio():
    return render_template('craft_studio.html')

@app.route('/head_to')
def head_to():
    return render_template('head_to.html')

@app.route('/suggestions')
def suggestions():
    top_products = Product.query.filter(Product.likes > 0).order_by(Product.likes.desc()).limit(10).all()
    return render_template('suggestion.html', top_products=top_products)

@app.route('/gift_sets')
def gift_sets():
    return render_template('gift_set.html')

# 🔴 Naya Feedback Route
@app.route('/feedback')
def feedback():
    return render_template('feedback.html')

# 🔴 Naya Bug Report Route
@app.route('/bug-report')
def bug_report():
    return render_template('bug_report.html')

@app.route('/profile')
def profile():
    session_email = (session.get('profile_email') or '').strip().lower()
    session_name = (session.get('profile_name') or '').strip()
    session_picture = (session.get('profile_picture') or '').strip()
    profile_data = {}
    current_user = {"name": "", "email": "", "picture": ""}

    if session_email:
        try:
            profile_record = get_or_create_profile(session_email, session_name)
            db.session.commit()
            profile_data = serialize_profile(
                profile_record,
                google_picture_url=session_picture,
                use_google_picture=bool(session_picture and not profile_record.avatar_filename)
            )
            current_user = {
                "name": session_name or profile_record.display_name,
                "email": profile_record.email,
                "picture": session_picture,
            }
        except Exception:
            db.session.rollback()
            profile_data = {}
            current_user = {"name": "", "email": "", "picture": ""}

    profile_data.setdefault('completed_missions', [])
    profile_data.setdefault('current_level_missions', [])
    profile_data.setdefault('unlocked_coupons', [])
    profile_data.setdefault('reward_vault', [])
    profile_data.setdefault('level', 1)
    profile_data.setdefault('rewards', {})
    profile_data.setdefault('stats', {})
    profile_data.setdefault('recent_reviews', [])
    profile_data.setdefault('wishlist_items', [])
    profile_data.setdefault('orders', [])

    return render_template(
        'profile.html',
        avatar_options=build_avatar_options(),
        default_avatar=url_for('static', filename=f'images/avatar/{DEFAULT_AVATAR_FILENAME}'),
        profile=profile_data,
        profile_data=profile_data,
        stats=profile_data.get('stats', {}),
        recent_reviews=profile_data.get('recent_reviews', []),
        current_user=current_user
    )


# ==========================================
# 🔴 BACKEND API ROUTES (Product Likes) 🔴
# ==========================================

@app.route('/like_product', methods=['POST'])
def like_product():
    data = request.get_json() or {}
    product_id = int(data.get('product_id'))
    action = data.get('action')
    user_account = get_session_user()
    
    real_name = data.get('name', f"Meltix Candle #{product_id}")
    real_image = data.get('image_file', f"candle_{product_id}.jpg")

    if not user_account:
        return jsonify({'success': False, 'message': 'Login required'}), 401

    product = db.session.get(Product, product_id)

    if not product:
        product = Product(
            id=product_id, 
            name=real_name, 
            image_file=real_image, 
            price=999, 
            likes=0
        )
        db.session.add(product)
    else:
        product.name = real_name
        product.image_file = real_image

    existing_like = ProductLike.query.filter_by(product_id=product_id, user_id=user_account.id).first()

    if action == 'like':
        if not existing_like:
            db.session.add(ProductLike(product_id=product_id, user_id=user_account.id))
    elif action == 'unlike':
        if existing_like:
            db.session.delete(existing_like)
    else:
        return jsonify({'success': False, 'message': 'Invalid like action'}), 400

    db.session.flush()
    product.likes = ProductLike.query.filter_by(product_id=product_id).count()

    db.session.commit()
    return jsonify({
        'success': True,
        'total_likes': product.likes,
        'liked_by_user': action == 'like' and ProductLike.query.filter_by(product_id=product_id, user_id=user_account.id).first() is not None
    })


@app.route('/api/product-states', methods=['POST'])
def product_states():
    data = request.get_json() or {}
    raw_product_ids = data.get('product_ids') or []
    product_ids = []

    for raw_product_id in raw_product_ids:
        try:
            product_ids.append(int(raw_product_id))
        except (TypeError, ValueError):
            continue

    product_ids = sorted(set(product_ids))
    like_counts = {str(product_id): 0 for product_id in product_ids}

    if product_ids:
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        for product in products:
            like_counts[str(product.id)] = product.likes or 0

    user_account = get_session_user()
    if not user_account:
        return jsonify({
            'success': True,
            'liked_product_ids': [],
            'wishlist_product_ids': [],
            'product_like_counts': like_counts
        }), 200

    liked_rows = []
    wishlist_rows = []

    if product_ids:
        liked_rows = ProductLike.query.filter(
            ProductLike.user_id == user_account.id,
            ProductLike.product_id.in_(product_ids)
        ).all()
        wishlist_rows = Wishlist.query.filter(
            Wishlist.user_email == user_account.email,
            Wishlist.product_id.in_(product_ids)
        ).all()

    return jsonify({
        'success': True,
        'liked_product_ids': [row.product_id for row in liked_rows],
        'wishlist_product_ids': [row.product_id for row in wishlist_rows],
        'product_like_counts': like_counts
    }), 200


# ==========================================
# 🔴 REVIEW SYSTEM API ROUTES (Fully Updated) 🔴
# ==========================================

# 1. Review Save Route
@app.route('/submit_review', methods=['POST'])
def submit_review():
    data = request.get_json() or {}
    try:
        user_account = get_session_user()

        if not user_account:
            return jsonify({'success': False, 'message': 'Login required to post a review'}), 401

        new_review = Review(
            product_id=int(data.get('product_id')),
            user_id=user_account.id,
            user_name=data.get('user_name') or user_account.display_name,
            review_text=data.get('review_text'),
            rating=int(data.get('rating'))
        )
        db.session.add(new_review)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Review posted successfully!'}), 200
    except IntegrityError:
        # Postgres rule block karega agar user pehle hi review de chuka hai
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Aap already review de chuke hain!'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# 2. Review Fetch Route (Saath me Likes bhi layega)
@app.route('/get_reviews/<int:product_id>', methods=['GET'])
def get_reviews(product_id):
    reviews = Review.query.filter_by(product_id=product_id).order_by(Review.created_at.desc()).all()
    
    if not reviews:
        return jsonify({'average_rating': 0, 'total_reviews': 0, 'reviews_data': []})
    
    total_stars = sum(r.rating for r in reviews)
    avg_rating = round(total_stars / len(reviews), 1)
    review_ids = [review.id for review in reviews]
    review_actions = ReviewLike.query.filter(ReviewLike.review_id.in_(review_ids)).all()
    action_counts = {}
    current_user_action_map = {}
    session_email = (session.get('profile_email') or '').strip().lower()
    current_user = UserAccount.query.filter_by(email=session_email).first() if session_email else None
    current_user_id = current_user.id if current_user else None

    for action in review_actions:
        counts = action_counts.setdefault(action.review_id, {'likes': 0, 'dislikes': 0})
        if action.action_type == 'like':
            counts['likes'] += 1
        elif action.action_type == 'dislike':
            counts['dislikes'] += 1

        if current_user_id and action.user_id == current_user_id:
            current_user_action_map[action.review_id] = action.action_type
    
    reviews_list = []
    for r in reviews:
        author = db.session.get(UserAccount, r.user_id)
        author_identity = public_profile_identity(author, fallback_name=r.user_name or 'Meltix Collector')
        counts = action_counts.get(r.id, {'likes': 0, 'dislikes': 0})
        
        reviews_list.append({
            'id': r.id, # 🔴 FIX: ID bhejna zaroori hai Javascript ko delete/like ke liye
            'user_name': author_identity['display_name'],
            'display_name': author_identity['display_name'],
            'author_email': author.email if author else "",
            'author_level': author_identity['level'],
            'author_avatar_filename': author_identity['avatar_filename'],
            'author_avatar_url': author_identity['avatar_url'],
            'review_text': r.review_text,
            'rating': r.rating,
            'date': r.created_at.strftime("%d %b %Y"),
            'likes': counts['likes'],
            'dislikes': counts['dislikes'],
            'current_user_action': current_user_action_map.get(r.id)
        })
        
    return jsonify({
        'average_rating': avg_rating,
        'total_reviews': len(reviews),
        'reviews_data': reviews_list
    })


# 3. NAYA: Delete Review Route
@app.route('/delete_review/<int:review_id>', methods=['POST', 'DELETE'])
def delete_review_route(review_id):
    try:
        user_account = get_session_user()

        if not user_account:
            return jsonify({'status': 'error', 'message': 'Login required'}), 401
            
        review = db.session.get(Review, review_id)
        if not review:
            return jsonify({"status": "error", "message": "Review not found"}), 404
            
        if review.user_id != user_account.id:
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
            
        db.session.delete(review) # Cascade deletes likes
        db.session.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


# 4. NAYA: Toggle Like/Dislike Route
@app.route('/toggle_review_like', methods=['POST'])
def toggle_review_like():
    data = request.get_json() or {}
    review_id = data.get('review_id')
    user_name = data.get('user_name')
    action = data.get('action')

    try:
        user_account = get_session_user()

        if not user_account:
            return jsonify({'status': 'error', 'message': 'Login required'}), 401
            
        # Check karo agar user ne pehle se koi action liya hai
        existing_action = ReviewLike.query.filter_by(review_id=review_id, user_id=user_account.id).first()

        if existing_action:
            if existing_action.action_type == action:
                db.session.delete(existing_action)
            else:
                existing_action.action_type = action # Update kar do (like -> dislike ya vice versa)
        else:
            new_action = ReviewLike(review_id=review_id, user_id=user_account.id, user_name=user_name or user_account.display_name, action_type=action) # Naya banao
            db.session.add(new_action)

        db.session.commit()
        likes_count = ReviewLike.query.filter_by(review_id=review_id, action_type='like').count()
        dislikes_count = ReviewLike.query.filter_by(review_id=review_id, action_type='dislike').count()
        active_action = ReviewLike.query.filter_by(review_id=review_id, user_id=user_account.id).first()
        return jsonify({
            "status": "success",
            "likes": likes_count,
            "dislikes": dislikes_count,
            "current_user_action": active_action.action_type if active_action else None
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    

# ==========================================
# 🔴 WISH LIST (SAVE FOR LATER) ROUTE 🔴
# ==========================================
@app.route('/toggle_wishlist', methods=['POST'])
def toggle_wishlist():
    data = request.get_json() or {}
    product_id = data.get('product_id')
    user_account = get_session_user()

    if not user_account:
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        # Check karo agar pehle se saved hai
        existing = Wishlist.query.filter_by(user_email=user_account.email, product_id=product_id).first()
        
        if existing:
            db.session.delete(existing) # Un-save kar do
            action = "removed"
        else:
            new_saved = Wishlist(user_email=user_account.email, product_id=product_id) # Save kar do
            db.session.add(new_saved)
            action = "added"
            
        db.session.commit()
        return jsonify({
            "status": "success",
            "action": action,
            "saved_in_wishlist": action == "added"
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/profile/bootstrap', methods=['POST'])
def profile_bootstrap():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    display_name = (data.get('name') or '').strip()
    google_picture_url = data.get('google_picture_url') or data.get('picture') or ''

    if not email:
        return jsonify({"success": False, "message": "Email required"}), 400

    try:
        profile_record = get_or_create_profile(email, display_name)
        if google_picture_url: profile_record.google_picture_url = google_picture_url
        session['profile_email'] = profile_record.email
        session['profile_name'] = display_name or profile_record.display_name
        if google_picture_url:
            session['profile_picture'] = google_picture_url
        else:
            session.pop('profile_picture', None)
        db.session.commit()
        prefer_google_picture = bool(google_picture_url and not profile_record.avatar_filename)
        return jsonify({
            "success": True,
            "profile": serialize_profile(
                profile_record,
                google_picture_url=google_picture_url,
                use_google_picture=prefer_google_picture
            )
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/profile/logout', methods=['POST'])
def profile_logout():
    session.pop('profile_email', None)
    session.pop('profile_name', None)
    session.pop('profile_picture', None)
    return jsonify({"success": True}), 200


@app.route('/api/profile/avatar', methods=['POST'])
def update_profile_avatar():
    data = request.get_json() or {}
    email = (data.get('email') or session.get('profile_email') or '').strip().lower()
    use_google_photo = bool(data.get('use_google_photo'))
    display_name = (data.get('name') or '').strip()
    google_picture_url = data.get('google_picture_url') or data.get('picture') or ''

    try:
        if not email:
            return jsonify({"success": False, "message": "Sign in required"}), 401

        profile_record = get_or_create_profile(email, display_name)
        player_level = normalize_level(profile_record.level)
        avatar_filename = '' if use_google_photo else sanitize_avatar_filename(data.get('avatar'), player_level=player_level)

        if not avatar_filename and not use_google_photo:
            return jsonify({"success": False, "message": "This avatar is locked for your current level"}), 403

        profile_record.avatar_filename = avatar_filename
        if google_picture_url: profile_record.google_picture_url = google_picture_url
        session['profile_email'] = profile_record.email
        db.session.commit()

        return jsonify({
            "success": True,
            "avatar_url": (
                google_picture_url
                if use_google_photo and google_picture_url
                else url_for('static', filename=f'images/avatar/{avatar_filename}')
            ) if (avatar_filename or google_picture_url) else None,
            "profile": serialize_profile(
                profile_record,
                google_picture_url=google_picture_url,
                use_google_picture=bool(use_google_photo and google_picture_url)
            )
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/profile/address', methods=['POST'])
def save_profile_address():
    data = request.get_json() or {}
    email = (data.get('email') or session.get('profile_email') or '').strip().lower()

    if not email:
        return jsonify({"success": False, "message": "Sign in required"}), 401

    try:
        address_record = UserAccount.query.filter_by(email=email).first()
        if not address_record:
            return jsonify({"success": False, "message": "User not found"}), 404
            
        shipping = data.get('shipping') or {}
        billing = data.get('billing') or {}
        billing_same_as_shipping = bool(data.get('billing_same_as_shipping', True))

        address_record.phone = (data.get('phone_number') or '').strip()
        address_record.shipping_name = (shipping.get('name') or '').strip()
        address_record.shipping_line1 = (shipping.get('line1') or '').strip()
        address_record.shipping_line2 = (shipping.get('line2') or '').strip()
        address_record.shipping_city = (shipping.get('city') or '').strip()
        address_record.shipping_state = (shipping.get('state') or '').strip()
        address_record.shipping_postal_code = (shipping.get('postal_code') or '').strip()
        address_record.shipping_country = (shipping.get('country') or 'India').strip()
        address_record.billing_same_as_shipping = billing_same_as_shipping

        if billing_same_as_shipping:
            address_record.billing_name = address_record.shipping_name
            address_record.billing_line1 = address_record.shipping_line1
            address_record.billing_line2 = address_record.shipping_line2
            address_record.billing_city = address_record.shipping_city
            address_record.billing_state = address_record.shipping_state
            address_record.billing_postal_code = address_record.shipping_postal_code
            address_record.billing_country = address_record.shipping_country
        else:
            address_record.billing_name = (billing.get('name') or '').strip()
            address_record.billing_line1 = (billing.get('line1') or '').strip()
            address_record.billing_line2 = (billing.get('line2') or '').strip()
            address_record.billing_city = (billing.get('city') or '').strip()
            address_record.billing_state = (billing.get('state') or '').strip()
            address_record.billing_postal_code = (billing.get('postal_code') or '').strip()
            address_record.billing_country = (billing.get('country') or 'India').strip()

        db.session.commit()
        return jsonify({"success": True, "address_book": serialize_address(address_record)}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/profile/scent-persona', methods=['POST'])
def save_scent_persona():
    data = request.get_json() or {}
    email = (data.get('email') or session.get('profile_email') or '').strip().lower()
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    notes = data.get('notes') or []

    if not email:
        return jsonify({"success": False, "message": "Sign in required"}), 401

    if not isinstance(notes, list) or not notes:
        return jsonify({"success": False, "message": "At least one note is required"}), 400

    try:
        persona_record = UserScentPersona.query.filter_by(user_email=email).first()
        if not persona_record:
            persona_record = UserScentPersona(user_email=email)
            db.session.add(persona_record)

        persona_record.title = title or 'Your Signature Notes'
        persona_record.description = description or 'A custom scent profile has been saved for your atelier.'
        persona_record.notes_json = json.dumps([str(note).strip() for note in notes if str(note).strip()])
        db.session.commit()

        return jsonify({
            "success": True,
            "scent_persona": {
                "title": persona_record.title,
                "description": persona_record.description,
                "notes": safe_json_loads(persona_record.notes_json, []),
                "has_data": True,
                "cta_label": "Refresh Persona"
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/claim_mission', methods=['POST'])
def claim_mission():
    data = request.get_json() or {}
    user_email = (data.get('user_email') or session.get('profile_email') or '').strip().lower()
    mission_key = (data.get('mission_key') or '').strip()

    if not user_email:
        return jsonify({"success": False, "message": "Sign in required"}), 401

    mission_data = MISSION_LOOKUP.get(mission_key)
    if not mission_data:
        return jsonify({"success": False, "message": "Invalid mission key"}), 400

    try:
        profile_record = UserAccount.query.filter_by(email=user_email).first()
        if not profile_record:
            return jsonify({"success": False, "message": "User not found"}), 404

        current_level = normalize_level(profile_record.level)
        unlocked_coupons, _ = sync_unlocked_coupons_for_level(profile_record)
        completed_missions = normalize_completed_missions(profile_record.completed_missions_json)
        already_claimed = mission_key in completed_missions
        level_up = False
        new_coupon_code = None

        if not already_claimed and mission_data["level"] != current_level:
            return jsonify({
                "success": False,
                "message": f"This mission unlocks at Level {mission_data['level']}."
            }), 403

        # ═══════════════════════════════════════════════════════════
        # 🔒 ANTI-CHEAT VALIDATION — Har mission ke liye real proof
        # ═══════════════════════════════════════════════════════════
        if not already_claimed:
            if mission_key == 'welcome':
                # Sirf account hona chahiye — already verified above
                pass

            elif mission_key == 'portrait_pick':
                # User ne avatar select kiya hona chahiye
                if not profile_record.avatar_filename:
                    return jsonify({
                        "success": False,
                        "message": "Please select a custom portrait first from the Avatar Gallery."
                    }), 403

            elif mission_key == 'wishlist_spark':
                # Wishlist mein koi item hona chahiye
                wishlist_count = Wishlist.query.filter_by(user_email=user_email).count()
                if wishlist_count < 1:
                    return jsonify({
                        "success": False,
                        "message": "Add at least one candle to your wishlist first."
                    }), 403

            elif mission_key == 'scent_quiz':
                # Scent persona saved honi chahiye
                persona_record = UserScentPersona.query.filter_by(user_email=user_email).first()
                if not persona_record or not safe_json_loads(persona_record.notes_json, []):
                    return jsonify({
                        "success": False,
                        "message": "Complete the Scent Quiz and save your persona first."
                    }), 403

            elif mission_key == 'first_review':
                # User ka real review hona chahiye database mein
                review_count = Review.query.filter_by(user_id=profile_record.id).count()
                if review_count < 1:
                    return jsonify({
                        "success": False,
                        "message": "Post your first review on a candle before claiming this mission."
                    }), 403

            elif mission_key == 'first_order':
                # User ka real order hona chahiye database mein
                order_count = ProfileOrder.query.filter_by(user_email=user_email).count()
                if order_count < 1:
                    return jsonify({
                        "success": False,
                        "message": "Place your first order before claiming this mission."
                    }), 403

            elif mission_key == 'special_date':
                # Candle Date Kit page visit — order ya real engagement check
                order_count = ProfileOrder.query.filter_by(user_email=user_email).count()
                if order_count < 1:
                    return jsonify({
                        "success": False,
                        "message": "Explore the Candle Date Kit and place an order first."
                    }), 403

            elif mission_key == 'studio_visit':
                # No strict server-side proof needed, page visit is enough (honour system)
                pass

            elif mission_key in ('zodiac_hunter', 'story_keeper', 'hidden_message',
                                  'craft_studio', 'break_to_reveal', 'date_night',
                                  'gift_set_scout', 'easter_egg', 'head_to_explorer'):
                # Page exploration missions — honour system (frontend handles navigation)
                pass

            elif mission_key == 'feedback_share':
                # No strict backend proof needed — honour system
                pass

            elif mission_key == 'bug_reporter':
                # No strict backend proof needed — honour system
                pass

            elif mission_key == 'melt_master':
                # Final prestige — user must have completed all Level 5 missions except this one
                level5_keys = [m["key"] for m in MISSION_CATALOG.get(5, []) if m["key"] != 'melt_master']
                if not all(key in completed_missions for key in level5_keys):
                    return jsonify({
                        "success": False,
                        "message": "Complete all other Level 5 missions before claiming Melt Master."
                    }), 403

        if not already_claimed:
            completed_missions.append(mission_key)
            profile_record.completed_missions_json = json.dumps(completed_missions)

        current_level_keys = [mission["key"] for mission in MISSION_CATALOG.get(current_level, [])]
        if current_level < MAX_PLAYER_LEVEL and current_level_keys and all(key in completed_missions for key in current_level_keys):
            profile_record.level = current_level + 1
            unlocked_coupons, new_coupon_code = unlock_level_coupon(profile_record, profile_record.level)
            level_up = True
        else:
            profile_record.level = current_level
            profile_record.unlocked_coupons = json.dumps(unlocked_coupons)

        db.session.commit()

        return jsonify({
            "success": True,
            "already_claimed": already_claimed,
            "level_up": level_up,
            "level": normalize_level(profile_record.level),
            "completed_missions": completed_missions,
            "unlocked_coupons": unlocked_coupons,
            "new_coupon_code": new_coupon_code,
            "profile": serialize_profile(
                profile_record,
                google_picture_url=(session.get('profile_picture') or '').strip(),
                use_google_picture=bool((session.get('profile_picture') or '').strip() and not profile_record.avatar_filename)
            )
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/validate_coupon', methods=['POST'])
def validate_coupon():
    data = request.get_json() or {}
    coupon_code = (data.get('code') or '').strip().upper()

    if not coupon_code:
        return jsonify({"success": False, "message": "Coupon code is required"}), 400

    if coupon_code not in ALLOWED_REWARD_COUPON_CODES:
        return jsonify({"success": False, "message": "Coupon code not found"}), 404

    coupon = Coupon.query.filter_by(code=coupon_code).first()
    if not coupon:
        return jsonify({"success": False, "message": "Coupon code not found"}), 404

    if not coupon.is_active:
        return jsonify({"success": False, "message": "This coupon is inactive"}), 400

    if coupon.expires_at and coupon.expires_at < datetime.utcnow():
        return jsonify({"success": False, "message": "This coupon has expired"}), 400

    if coupon.max_uses is not None and coupon.current_uses >= coupon.max_uses:
        return jsonify({"success": False, "message": "This coupon has reached its usage limit"}), 400

    remaining_uses = None if coupon.max_uses is None else max(coupon.max_uses - coupon.current_uses, 0)
    return jsonify({
        "success": True,
        "code": coupon.code,
        "discount_percentage": coupon.discount_percentage,
        "remaining_uses": remaining_uses,
        "expires_at": coupon.expires_at.isoformat() if coupon.expires_at else None,
        "message": "Coupon is valid"
    }), 200


@app.route('/api/leaderboard', methods=['GET'])
def leaderboard_api():
    top_accounts = (
        UserAccount.query
        .order_by(UserAccount.lifetime_spend.desc(), UserAccount.level.desc(), UserAccount.display_name.asc())
        .limit(50)
        .all()
    )

    leaderboard_items = []
    for account in top_accounts:
        identity = public_profile_identity(account, fallback_name=account.email.split('@')[0] if account.email else 'Meltix Collector')
        leaderboard_items.append({
            "name": identity['display_name'],
            "display_name": identity['display_name'],
            "level": identity['level'],
            "avatar_filename": identity['avatar_filename'],
            "avatar_url": identity['avatar_url'],
            "lifetime_spend": int(account.lifetime_spend or 0),
            "lifetime_spend_display": format_money(int(account.lifetime_spend or 0)),
        })

    return jsonify({"success": True, "items": leaderboard_items}), 200

if __name__ == '__main__':
    app.run(debug=True)
