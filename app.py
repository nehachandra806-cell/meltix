from flask import Flask, render_template, request, jsonify, session, url_for
from flask_sqlalchemy import SQLAlchemy
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
    {"points": 500, "label": "Complimentary Wick Trimmer"},
    {"points": 900, "label": "Signature Gift Wrap Upgrade"},
    {"points": 1400, "label": "Private Atelier Access"},
    {"points": 2200, "label": "Founders Circle Reward"},
]

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


def sanitize_avatar_filename(filename):
    return filename if filename in AVATAR_FILENAMES else ''


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
            'src': url_for('static', filename=f'images/avatar/{filename}')
        }
        for index, filename in enumerate(AVATAR_FILENAMES, start=1)
    ]


def avatar_label_for_filename(filename):
    for avatar in build_avatar_options():
        if avatar['filename'] == filename:
            return avatar['label']
    return "Custom Avatar"

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

# Tera Review Table Model
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, nullable=False) # Ye batayega kis candle ka review hai
    user_name = db.Column(db.String(100), nullable=False)
    review_text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False) # 1 se 5 tak star rating
    created_at = db.Column(db.DateTime, default=datetime.utcnow) # Review ka time

    # 🔴 STRICT RULE: 1 User = 1 Review per product
    __table_args__ = (db.UniqueConstraint('user_name', 'product_id', name='unique_user_review'),)

    # Cascade Delete: Review delete hoga toh uske saare likes bhi automatically ud jayenge
    review_likes = db.relationship('ReviewLike', backref='review', cascade="all, delete-orphan")

    def __repr__(self):
        return f"Review('{self.user_name}', Rating: {self.rating}, Product: {self.product_id})"

# 🔴 NAYA TABLE: Review Likes (1 User = 1 Action per review)
class ReviewLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    action_type = db.Column(db.String(10), nullable=False) # 'like' ya 'dislike'

    # STRICT RULE: Ek review pe ek banda ek hi baar like/dislike save kar sake
    __table_args__ = (db.UniqueConstraint('review_id', 'user_name', name='unique_user_review_like'),)


class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False, default='Guest')
    avatar_filename = db.Column(db.String(50), nullable=False, default='')
    glow_points = db.Column(db.Integer, nullable=False, default=250)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"UserProfile('{self.email}', Avatar: {self.avatar_filename})"


# 🔴 NAYA TABLE: Saved Products (Wishlist / Buy Later)
class UserAddress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(25), nullable=False, default='')
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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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

# Ye line chalte hi PostgreSQL mein saari tables aur rules ban jayenge
with app.app_context():
    db.create_all() 


def safe_json_loads(raw_value, fallback):
    if raw_value in (None, ''):
        return fallback
    try:
        return json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


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
        "phone_number": address_record.phone_number,
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
    entries = [
        {
            "title": "Welcome Bonus",
            "description": "Your Meltix Atelier was activated.",
            "points": 250,
            "date_value": profile_record.created_at,
        }
    ]

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

    entries.sort(key=lambda entry: entry["date_value"], reverse=True)
    total_points = sum(entry["points"] for entry in entries)

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
        next_reward_label = "Founders Circle Reward Unlocked"

    return {
        "current_points": total_points,
        "progress_percent": progress_percent,
        "points_to_next_reward": points_to_next,
        "next_reward_label": next_reward_label,
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

    profile_record = UserProfile.query.filter_by(email=normalized_email).first()
    if not profile_record:
        profile_record = UserProfile(
            email=normalized_email,
            display_name=readable_name,
            avatar_filename=''
        )
        db.session.add(profile_record)
    else:
        profile_record.display_name = readable_name or profile_record.display_name

    return profile_record


def get_or_create_address(user_email):
    address_record = UserAddress.query.filter_by(user_email=user_email).first()
    if not address_record:
        address_record = UserAddress(user_email=user_email)
        db.session.add(address_record)
    return address_record


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


def serialize_profile(profile_record, google_picture_url=None, use_google_picture=False):
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

    all_reviews = Review.query.filter_by(user_name=profile_record.display_name).order_by(Review.created_at.desc()).all()
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
            'dislikes': review_action_map.get(review.id, {}).get('dislikes', 0)
        }
        for review in recent_reviews
    ]

    orders = ProfileOrder.query.filter_by(user_email=profile_record.email).order_by(ProfileOrder.created_at.desc()).all()
    serialized_orders = [serialize_order(order) for order in orders]
    orders_in_progress = sum(1 for order in orders if order.stage_key != 'delivered')
    total_spent = sum(max(order.total_amount, 0) for order in orders)
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

    address_record = UserAddress.query.filter_by(user_email=profile_record.email).first()
    address_book = serialize_address(address_record)

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
        'member_since': profile_record.created_at.strftime("%b %Y"),
        'stats': {
            'wishlist_count': len(wishlist_items),
            'review_count': len(all_reviews),
            'review_likes': total_review_likes,
            'review_dislikes': total_review_dislikes,
            'orders_in_progress': orders_in_progress,
            'order_count': len(orders),
            'total_spent': total_spent,
            'total_spent_display': format_money(total_spent),
            'avatar_count': len(AVATAR_FILENAMES)
        },
        'wishlist_items': wishlist_items,
        'recent_reviews': review_items,
        'orders': serialized_orders,
        'address_book': address_book,
        'rewards': rewards,
        'scent_persona': scent_persona
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
    return render_template(
        'profile.html',
        avatar_options=build_avatar_options(),
        default_avatar=url_for('static', filename=f'images/avatar/{DEFAULT_AVATAR_FILENAME}')
    )


# ==========================================
# 🔴 BACKEND API ROUTES (Product Likes) 🔴
# ==========================================

@app.route('/like_product', methods=['POST'])
def like_product():
    data = request.get_json()
    product_id = int(data.get('product_id'))
    action = data.get('action')
    
    real_name = data.get('name', f"Meltix Candle #{product_id}")
    real_image = data.get('image_file', f"candle_{product_id}.jpg")

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

    if action == 'like':
        product.likes += 1
    elif action == 'unlike' and product.likes > 0:
        product.likes -= 1

    db.session.commit()
    return jsonify({'success': True, 'total_likes': product.likes})


# ==========================================
# 🔴 REVIEW SYSTEM API ROUTES (Fully Updated) 🔴
# ==========================================

# 1. Review Save Route
@app.route('/submit_review', methods=['POST'])
def submit_review():
    data = request.get_json()
    new_review = Review(
        product_id=int(data.get('product_id')),
        user_name=data.get('user_name'),
        review_text=data.get('review_text'),
        rating=int(data.get('rating'))
    )
    
    try:
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
    
    reviews_list = []
    for r in reviews:
        # Is review ke total 'like' count karo
        likes_count = ReviewLike.query.filter_by(review_id=r.id, action_type='like').count()
        
        reviews_list.append({
            'id': r.id, # 🔴 FIX: ID bhejna zaroori hai Javascript ko delete/like ke liye
            'user_name': r.user_name,
            'review_text': r.review_text,
            'rating': r.rating,
            'date': r.created_at.strftime("%d %b %Y"),
            'likes': likes_count
        })
        
    return jsonify({
        'average_rating': avg_rating,
        'total_reviews': len(reviews),
        'reviews_data': reviews_list
    })


# 3. NAYA: Delete Review Route
@app.route('/delete_review/<int:review_id>', methods=['DELETE'])
def delete_review_route(review_id):
    try:
        review = db.session.get(Review, review_id)
        if review:
            db.session.delete(review) # Cascade ki wajah se likes automatically delete ho jayenge
            db.session.commit()
            return jsonify({"status": "success"}), 200
        return jsonify({"status": "error", "message": "Review not found"}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


# 4. NAYA: Toggle Like/Dislike Route
@app.route('/toggle_review_like', methods=['POST'])
def toggle_review_like():
    data = request.get_json()
    review_id = data.get('review_id')
    user_name = data.get('user_name')
    action = data.get('action')

    try:
        # Check karo agar user ne pehle se koi action liya hai
        existing_action = ReviewLike.query.filter_by(review_id=review_id, user_name=user_name).first()

        if existing_action:
            existing_action.action_type = action # Update kar do (like -> dislike ya vice versa)
        else:
            new_action = ReviewLike(review_id=review_id, user_name=user_name, action_type=action) # Naya banao
            db.session.add(new_action)

        db.session.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    

# ==========================================
# 🔴 WISH LIST (SAVE FOR LATER) ROUTE 🔴
# ==========================================
@app.route('/toggle_wishlist', methods=['POST'])
def toggle_wishlist():
    data = request.get_json()
    user_email = data.get('user_email')
    product_id = data.get('product_id')

    if not user_email:
        return jsonify({"status": "error", "message": "Login required"}), 401

    try:
        # Check karo agar pehle se saved hai
        existing = Wishlist.query.filter_by(user_email=user_email, product_id=product_id).first()
        
        if existing:
            db.session.delete(existing) # Un-save kar do
            action = "removed"
        else:
            new_saved = Wishlist(user_email=user_email, product_id=product_id) # Save kar do
            db.session.add(new_saved)
            action = "added"
            
        db.session.commit()
        return jsonify({"status": "success", "action": action}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/profile/bootstrap', methods=['POST'])
def profile_bootstrap():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    display_name = (data.get('name') or '').strip()
    google_picture_url = (data.get('picture') or '').strip()
    orders_payload = data.get('orders') or []

    if not email:
        return jsonify({"success": False, "message": "Email required"}), 400

    try:
        profile_record = get_or_create_profile(email, display_name)
        sync_profile_orders(profile_record.email, orders_payload)
        session['profile_email'] = profile_record.email
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


@app.route('/api/profile/avatar', methods=['POST'])
def update_profile_avatar():
    data = request.get_json() or {}
    email = (data.get('email') or session.get('profile_email') or '').strip().lower()
    use_google_photo = bool(data.get('use_google_photo'))
    avatar_filename = '' if use_google_photo else sanitize_avatar_filename(data.get('avatar'))
    display_name = (data.get('name') or '').strip()
    google_picture_url = (data.get('picture') or '').strip()

    try:
        if not email:
            return jsonify({"success": False, "message": "Sign in required"}), 401

        if not avatar_filename and not use_google_photo:
            return jsonify({"success": False, "message": "Valid avatar required"}), 400

        profile_record = get_or_create_profile(email, display_name)
        profile_record.avatar_filename = avatar_filename
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
        address_record = get_or_create_address(email)
        shipping = data.get('shipping') or {}
        billing = data.get('billing') or {}
        billing_same_as_shipping = bool(data.get('billing_same_as_shipping', True))

        address_record.phone_number = (data.get('phone_number') or '').strip()
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

if __name__ == '__main__':
    app.run(debug=True)
