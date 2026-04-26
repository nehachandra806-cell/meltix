from flask import Flask, render_template, request, jsonify, session, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, inspect, text
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from collections import defaultdict, deque
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import hashlib
import json
import smtplib
import re
import os
import ssl
import time
import razorpay

try:
    from litellm import completion as litellm_completion
except ModuleNotFoundError:
    litellm_completion = None

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(dotenv_path):
        env_path = Path(dotenv_path)
        if not env_path.exists():
            return False
        for raw_line in env_path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return True

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


def env_flag(name, default=False):
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in {'1', 'true', 'yes', 'on'}


class CheckoutError(Exception):
    def __init__(self, message, status_code=400, error_code='checkout_error'):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


DEFAULT_WHATSAPP_BUSINESS = '919876543210'
GENERIC_ERROR_MESSAGE = 'Something went wrong. Please try again.'
ADMIN_SECRET_PASSWORD = (os.environ.get('ADMIN_SECRET_PASSWORD') or 'meltix-founder-desk').strip()
PAYMENT_STATUS_OPTIONS = ('Pending', 'Paid', 'Failed')
DELIVERY_STATUS_OPTIONS = ('Pending', 'Shipped', 'Delivered')
DELIVERY_STAGE_MAP = {
    'Pending': 'placed',
    'Shipped': 'shipped',
    'Delivered': 'delivered',
}
FORM_RATE_LIMIT_WINDOW_SECONDS = max(60, int(os.environ.get('FORM_RATE_LIMIT_WINDOW_SECONDS', '600') or 600))
FORM_RATE_LIMIT_MAX_ATTEMPTS = max(1, int(os.environ.get('FORM_RATE_LIMIT_MAX_ATTEMPTS', '5') or 5))
BOT_RATE_LIMIT_WINDOW_SECONDS = max(10, int(os.environ.get('BOT_RATE_LIMIT_WINDOW_SECONDS', '60') or 60))
BOT_RATE_LIMIT_MAX_ATTEMPTS = max(1, int(os.environ.get('BOT_RATE_LIMIT_MAX_ATTEMPTS', '12') or 12))
FORM_RATE_LIMIT_BUCKETS = defaultdict(deque)
FORM_RATE_LIMIT_LOCK = Lock()
TRUST_PROXY_HEADERS = env_flag('TRUST_PROXY_HEADERS', default=False)
AUTO_SEED_INVENTORY = env_flag('AUTO_SEED_INVENTORY', default=False)
CATALOG_CATEGORY_ALIASES = {
    'hidden-message': 'hidden-message',
    'hidden_message': 'hidden-message',
    'hidden': 'hidden-message',
    'story-candle': 'story-candle',
    'story_candle': 'story-candle',
    'story': 'story-candle',
    'zodiac-candle': 'zodiac-candle',
    'zodiac_candle': 'zodiac-candle',
    'zodiac': 'zodiac-candle',
    'break-to-reveal': 'break-to-reveal',
    'break_to_reveal': 'break-to-reveal',
    'break': 'break-to-reveal',
    'candle-date-kit': 'candle-date-kit',
    'candle_date_kit': 'candle-date-kit',
    'date-kit': 'candle-date-kit',
    'date': 'candle-date-kit',
    'gift-sets': 'gift-sets',
    'gift_set': 'gift-sets',
    'gift_sets': 'gift-sets',
    'gifts': 'gift-sets',
}
SHOP_COLLECTIONS = [
    {
        'number': '01',
        'slug': 'hidden-message',
        'href': '/hidden-message',
        'title_lines': ['Hidden', 'Message'],
        'quote': 'The flame fades. The words remain.',
        'cta_label': 'Uncover',
        'caption': 'Hidden Message Candle',
    },
    {
        'number': '02',
        'slug': 'story-candle',
        'href': '/story-candle',
        'title_lines': ['Story', 'Candle'],
        'quote': 'A new chapter with every burn.',
        'cta_label': 'Begin the Story',
        'caption': 'Story Candle',
    },
    {
        'number': '03',
        'slug': 'zodiac-candle',
        'href': '/zodiac-candle',
        'title_lines': ['Zodiac', 'Candle'],
        'quote': 'The stars chose your scent.',
        'cta_label': 'Find Your Sign',
        'caption': 'Zodiac Candle',
    },
    {
        'number': '04',
        'slug': 'break-to-reveal',
        'href': '/break-to-reveal',
        'title_lines': ['Break to', 'Reveal'],
        'quote': 'Shatter it. The secret is inside.',
        'cta_label': 'Break It Open',
        'caption': 'Break to Reveal',
    },
    {
        'number': '05',
        'slug': 'candle-date-kit',
        'href': '/candle-date-kit',
        'title_lines': ['Candle', 'Date Kit'],
        'quote': 'Set the mood. Let the wax do the rest.',
        'cta_label': 'Plan the Night',
        'caption': 'Candle Date Kit',
    },
]

BOT_MAX_HISTORY = 16
BOT_MODELS_TO_TRY = [
    "groq/llama-3.1-8b-instant",
    "gemini/gemini-2.5-flash",
    "nvidia_nim/meta/llama-3.1-8b-instruct",
    "github/gpt-4o",
]
BOT_TOOL_MODELS_TO_TRY = [
    "github/gpt-4o",
    "gemini/gemini-2.5-flash",
    "groq/llama-3.1-8b-instant",
    "nvidia_nim/meta/llama-3.1-8b-instruct",
]
BOT_TOOLS = [{
    "type": "function",
    "function": {
        "name": "search_store_products",
        "description": (
            "Meltix database se real products dhundne ke liye. "
            "Sirf tab use karo jab user kisi specific product, category ya gift ke baare mein pooche. "
            "Normal greetings ya general baat pe mat chalao."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": "Product ki category ya naam (eg. hidden, story, zodiac, break, date, gift)"
                },
                "max_price": {
                    "type": "integer",
                    "description": "Maximum budget agar user ne bataya ho, warna 100000"
                }
            },
            "required": ["search_term"]
        }
    }
}, {
    "type": "function",
    "function": {
        "name": "suggest_product_card",
        "description": (
            "Jab user ko ek specific candle ya product recommend karna ho aur chat ke andar clickable product card dikhana ho tab use karo. "
            "Real Meltix product pick karo aur sirf tab use karo jab user buying intent, recommendation, ya product interest dikhaye."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": "Product, collection, mood, ya keyword jiske basis par ek best product card suggest karna hai."
                },
                "max_price": {
                    "type": "integer",
                    "description": "Optional budget ceiling agar user ne budget bataya ho."
                }
            },
            "required": ["search_term"]
        }
    }
}, {
    "type": "function",
    "function": {
        "name": "redirect_user",
        "description": (
            "Jab user kahe ki kisi collection, product page, shop, gift sets, profile, cart, studio, suggestions, "
            "feedback ya bug report par jana hai tab use karo. Is tool ka kaam user ko correct Meltix page par le jana hai."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": "User jis page ya section par jana chahta hai. Example: zodiac candle, hidden message, shop, gift sets, profile, cart"
                }
            },
            "required": ["destination"]
        }
    }
}]
BOT_SYSTEM_PROMPT = """You are Meltix Bot, a highly professional, concise sales assistant at Meltix Atelier. Your only job is to help users discover and buy the right product.

[STRICT LANGUAGE MATCHING]
- Reply only in the language and script the user started the conversation in.
- If they start in English, reply in English.
- If they start in Hinglish, reply in Hinglish.
- If they start in Hindi, reply in Hindi.
- Do not switch languages unless the user clearly switches first.

[SMART SALES MODE]
- Keep every reply extremely short: maximum 1 to 3 sentences.
- Politely greet the user, then quickly ask what they want to buy, gift, explore, or get suggested.
- Move the conversation toward a product, collection, budget, occasion, or next page.
- If the user is vague, ask one short sales question such as who the gift is for, budget, occasion, or preferred collection.
- If the user is browsing a product page, stay relevant to that page first.

[ANTI-WASTE PROTOCOL]
- Do not entertain off-topic chats, jokes, or casual hanging out.
- If the user tries unrelated conversation, politely and firmly redirect them toward gifts, candles, suggestions, collections, or buying intent.
- If the user only says hello or asks how you are, answer briefly and immediately ask what they want to shop for.
- No long paragraphs, no essays, no storytelling unless it directly helps sell the product.

[SELLING STYLE]
- Sound polished, warm, and efficient.
- Focus on what the user wants to buy, gift, or explore.
- Mention price only if the user asks for price, budget, affordability, or options in a range.
- End with a short sales CTA when useful, such as asking whether they want a suggestion, a collection, or a specific product.

[PRODUCT GUIDE]
1. Hidden Message Candles -> for personal messages, confessions, surprises, reveal moments.
2. Story Candles -> for mood shifts, routines, calming rituals, layered experiences.
3. Zodiac Candles -> for astrology lovers, zodiac gifting, crystal-led gifting.
4. Break to Reveal -> for surprise gifting, stress release, dramatic reveal moments.
5. Candle Date Kit -> for date nights, anniversaries, cozy romantic setups.
6. Gift Sets -> best option when the user is unsure and wants a polished gift.

[TOOL USE]
- Use search_store_products only when the user wants real product options, suggestions, budgets, or a specific collection/product.
- Use suggest_product_card when you are recommending one specific product and want the UI to show a tappable product card.
- If the user asks to see a specific collection, go to a different page, visit the shop, open profile, or view cart, use redirect_user.
- Do not use the tool for greetings, jokes, or off-topic chatter."""
BOT_ROMAN_HINDI_MARKERS = (
    'acha', 'achha', 'are', 'arre', 'bata', 'batao', 'batau', 'bhai', 'bhaiya', 'bolo', 'chaiye',
    'chahiye', 'dekh', 'dekhna', 'dena', 'hona', 'hoon', 'hu', 'kafi', 'kaisa', 'kaise', 'kar',
    'karna', 'karo', 'koi', 'kr', 'krna', 'krta', 'krte', 'kya', 'kyu', 'kyun', 'lena', 'mai',
    'main', 'mera', 'mere', 'mood', 'mujhe', 'nhi', 'nahi', 'pasand', 'raha', 'rha', 'sahi',
    'samjha', 'suno', 'tha', 'thoda', 'toh', 'tum', 'tumhe', 'wala', 'wali', 'yar', 'yaar'
)
BOT_CONTEXT_LABELS = {
    'shop': 'main shop',
    'hidden-message': 'Hidden Message collection page',
    'story-candle': 'Story Candle collection page',
    'zodiac-candle': 'Zodiac Candle collection page',
    'break-to-reveal': 'Break to Reveal collection page',
    'candle-date-kit': 'Candle Date Kit collection page',
}
BOT_REDIRECT_DESTINATIONS = [
    {'keywords': ('hidden message', 'hidden-message', 'hidden'), 'endpoint': 'hidden_message', 'label': 'Hidden Message'},
    {'keywords': ('story candle', 'story-candle', 'story'), 'endpoint': 'story_candle', 'label': 'Story Candle'},
    {'keywords': ('zodiac candle', 'zodiac-candle', 'zodiac'), 'endpoint': 'zodiac_candle', 'label': 'Zodiac Candle'},
    {'keywords': ('break to reveal', 'break-to-reveal', 'break reveal', 'treasure hunt', 'stress buster'), 'endpoint': 'break_to_reveal', 'label': 'Break to Reveal'},
    {'keywords': ('candle date kit', 'candle-date-kit', 'date kit', 'date night'), 'endpoint': 'candle_date_kit', 'label': 'Candle Date Kit'},
    {'keywords': ('shop', 'collections', 'browse'), 'endpoint': 'shop', 'label': 'Shop'},
    {'keywords': ('gift sets', 'gift set', 'gifts'), 'endpoint': 'gift_sets', 'label': 'Gift Sets'},
    {'keywords': ('profile', 'account', 'my profile'), 'endpoint': 'profile', 'label': 'Profile'},
    {'keywords': ('cart', 'bag', 'basket', 'checkout bag'), 'endpoint': 'shop', 'label': 'Cart', 'query': {'open_cart': '1'}},
    {'keywords': ('meltix studio', 'craft studio', 'studio'), 'endpoint': 'craft_studio', 'label': 'Meltix Studio'},
    {'keywords': ('suggestions', 'suggestion', 'recommendations', 'recommendation'), 'endpoint': 'suggestions', 'label': 'Suggestions'},
    {'keywords': ('another section', 'head to', 'navigation'), 'endpoint': 'head_to', 'label': 'Another Section'},
    {'keywords': ('feedback', 'review page'), 'endpoint': 'feedback', 'label': 'Feedback'},
    {'keywords': ('bug report', 'bug', 'issue'), 'endpoint': 'bug_report', 'label': 'Bug Report'},
]


app = Flask(__name__)
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    raise RuntimeError("SECRET_KEY environment variable is required. Set it in your environment or .env file.")
app.config['SECRET_KEY'] = secret_key
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    raise RuntimeError("DATABASE_URL environment variable is required. Set it in your environment or .env file.")
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
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

CATALOG_SEED_PATHS = [
    BASE_DIR / 'data' / 'catalog_seed.json',
    BASE_DIR / 'scratch' / 'catalog_seed.json',
]


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
    name = db.Column(db.String(180), nullable=False)
    image_file = db.Column(db.String(255), nullable=False)
    image_path = db.Column(db.String(255), nullable=False, default='')
    collection_slug = db.Column(db.String(80), nullable=False, default='', index=True)
    collection_label = db.Column(db.String(120), nullable=False, default='')
    group_name = db.Column(db.String(120), nullable=False, default='', index=True)
    details_json = db.Column(db.Text, nullable=False, default='{}')
    ui_flags_json = db.Column(db.Text, nullable=False, default='{}')
    price = db.Column(db.Integer, nullable=False, default=500)
    stock_quantity = db.Column(db.Integer, nullable=False, default=5)
    likes = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"Product('{self.name}', Collection: {self.collection_slug}, Likes: {self.likes})"


class ProductLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user_account.id'), nullable=False)

    __table_args__ = (db.UniqueConstraint('product_id', 'user_id', name='unique_user_product_like'),)

# Tera Review Table Model
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False) # Ye batayega kis candle ka review hai
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
    payment_status = db.Column(db.String(20), nullable=False, default='Pending')
    delivery_status = db.Column(db.String(20), nullable=False, default='Pending')
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
    confirmation_email_sent = db.Column(db.Boolean, nullable=False, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)
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


class FeedbackSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False, default=0)
    message = db.Column(db.Text, nullable=False, default='')
    source_page = db.Column(db.String(120), nullable=False, default='feedback')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class BugReportSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    source_page = db.Column(db.String(120), nullable=False, default='bug-report')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def normalize_catalog_category(category_value):
    clean_value = (category_value or '').strip().lower()
    return CATALOG_CATEGORY_ALIASES.get(clean_value)


def load_catalog_seed():
    seed_path = next((path for path in CATALOG_SEED_PATHS if path.exists()), None)
    if not seed_path:
        raise FileNotFoundError("Catalog seed file not found.")

    with seed_path.open('r', encoding='utf-8') as seed_file:
        payload = json.load(seed_file)

    if not isinstance(payload, list):
        raise ValueError("Catalog seed file must contain a list of products.")

    return payload


def ensure_product_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table('product'):
        return

    product_columns = {column['name'] for column in inspector.get_columns('product')}
    column_definitions = {
        'image_path': "ALTER TABLE product ADD COLUMN image_path VARCHAR(255) NOT NULL DEFAULT ''",
        'collection_slug': "ALTER TABLE product ADD COLUMN collection_slug VARCHAR(80) NOT NULL DEFAULT ''",
        'collection_label': "ALTER TABLE product ADD COLUMN collection_label VARCHAR(120) NOT NULL DEFAULT ''",
        'group_name': "ALTER TABLE product ADD COLUMN group_name VARCHAR(120) NOT NULL DEFAULT ''",
        'details_json': "ALTER TABLE product ADD COLUMN details_json TEXT NOT NULL DEFAULT '{}'",
        'ui_flags_json': "ALTER TABLE product ADD COLUMN ui_flags_json TEXT NOT NULL DEFAULT '{}'",
        'stock_quantity': "ALTER TABLE product ADD COLUMN stock_quantity INTEGER NOT NULL DEFAULT 5",
    }

    for column_name, statement in column_definitions.items():
        if column_name not in product_columns:
            with db.engine.begin() as connection:
                connection.execute(text(statement))

    with db.engine.begin() as connection:
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_product_collection_slug ON product (collection_slug)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_product_group_name ON product (group_name)"))


def ensure_review_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table('review') or not inspector.has_table('product'):
        return

    review_foreign_keys = inspector.get_foreign_keys('review')
    for foreign_key in review_foreign_keys:
        if (
            foreign_key.get('referred_table') == 'product'
            and foreign_key.get('constrained_columns') == ['product_id']
        ):
            return

    invalid_review_count = int(
        db.session.execute(
            text("""
                SELECT COUNT(*)
                FROM review AS r
                LEFT JOIN product AS p ON p.id = r.product_id
                WHERE p.id IS NULL
            """)
        ).scalar() or 0
    )
    if invalid_review_count:
        app.logger.warning(
            'Review.product_id foreign key skipped because %s review rows reference missing products.',
            invalid_review_count,
        )
        return

    with db.engine.begin() as connection:
        connection.execute(
            text("""
                ALTER TABLE review
                ADD CONSTRAINT fk_review_product_id
                FOREIGN KEY (product_id) REFERENCES product(id)
            """)
        )


def seed_inventory():
    seed_rows = load_catalog_seed()
    changed = False

    for raw_row in seed_rows:
        product_id = int(raw_row['id'])
        collection_slug = normalize_catalog_category(raw_row.get('collection_slug'))
        if not collection_slug:
            raise ValueError(f"Unsupported catalog category for product {product_id}: {raw_row.get('collection_slug')}")

        image_path = str(raw_row.get('image_path') or '').strip().replace('\\', '/')
        if not image_path:
            raise ValueError(f"Missing image path for product {product_id}")

        image_path = image_path.lstrip('/')
        absolute_image_path = BASE_DIR / 'static' / image_path
        if not absolute_image_path.exists():
            raise FileNotFoundError(f"Catalog image missing for product {product_id}: {absolute_image_path}")

        product = db.session.get(Product, product_id)
        if not product:
            product = Product(id=product_id)
            db.session.add(product)
            changed = True

        try:
            normalized_price = max(0, int(raw_row.get('price') if raw_row.get('price') is not None else 500))
        except (TypeError, ValueError):
            normalized_price = 500

        expected_values = {
            'name': str(raw_row.get('name') or '').strip(),
            'image_file': Path(image_path).name,
            'image_path': image_path,
            'collection_slug': collection_slug,
            'collection_label': str(raw_row.get('collection_label') or '').strip(),
            'group_name': str(raw_row.get('group_name') or '').strip(),
            'details_json': json.dumps(raw_row.get('details') or {}, ensure_ascii=False),
            'ui_flags_json': json.dumps(raw_row.get('ui_flags') or {}, ensure_ascii=False),
            'price': normalized_price,
        }

        for field_name, field_value in expected_values.items():
            if getattr(product, field_name) != field_value:
                setattr(product, field_name, field_value)
                changed = True

        if product.likes is None:
            product.likes = 0
            changed = True

        if product.stock_quantity is None or int(product.stock_quantity) < 0:
            product.stock_quantity = 5
            changed = True

    if changed:
        db.session.commit()


@app.cli.command("seed-meltix")
def seed_meltix_command():
    seed_inventory()
    print("Meltix catalog seeded.")


@app.cli.command("backfill-lifetime-spend")
def backfill_lifetime_spend_command():
    backfill_all_lifetime_spend()
    print("User lifetime spend backfill completed.")


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


def ensure_order_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table('profile_order'):
        return

    order_columns = {column['name'] for column in inspector.get_columns('profile_order')}
    column_definitions = {
        'payment_status': "ALTER TABLE profile_order ADD COLUMN payment_status VARCHAR(20) NOT NULL DEFAULT 'Pending'",
        'delivery_status': "ALTER TABLE profile_order ADD COLUMN delivery_status VARCHAR(20) NOT NULL DEFAULT 'Pending'",
        'confirmation_email_sent': "ALTER TABLE profile_order ADD COLUMN confirmation_email_sent BOOLEAN NOT NULL DEFAULT FALSE",
        'paid_at': "ALTER TABLE profile_order ADD COLUMN paid_at TIMESTAMP NULL",
    }

    for column_name, statement in column_definitions.items():
        if column_name not in order_columns:
            with db.engine.begin() as connection:
                connection.execute(text(statement))


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
# Heavy backfills ko startup se hata diya gaya hai; woh CLI se one-time chalenge.
with app.app_context():
    db.create_all()
    ensure_product_schema()
    ensure_review_schema()
    ensure_profile_schema()
    ensure_order_schema()
    ensure_coupon_catalog()
    if AUTO_SEED_INVENTORY:
        seed_inventory()


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


def product_static_path(product_record):
    if not product_record:
        return ''

    image_path = (product_record.image_path or '').strip().replace('\\', '/')
    if image_path:
        return image_path.lstrip('/')

    image_file = (product_record.image_file or '').strip()
    if image_file:
        if '/' in image_file:
            return image_file.lstrip('/')
        return f"images/{image_file}"

    return ''


def product_image_url(product_record):
    image_path = product_static_path(product_record)
    if not image_path:
        return ''
    return url_for('static', filename=image_path)


def serialize_product(product_record):
    details = safe_json_loads(product_record.details_json, {})
    ui_flags = safe_json_loads(product_record.ui_flags_json, {})
    image_url = product_image_url(product_record)
    stock_quantity = max(0, int(product_record.stock_quantity or 0))
    price_value = max(0, int(product_record.price or 0))

    return {
        'id': product_record.id,
        'name': product_record.name,
        'title': details.get('title') or product_record.name,
        'collection_slug': product_record.collection_slug,
        'collection_label': product_record.collection_label,
        'group_name': product_record.group_name,
        'price': price_value,
        'price_display': format_money(price_value),
        'likes': int(product_record.likes or 0),
        'stock': stock_quantity,
        'stock_quantity': stock_quantity,
        'image_file': product_record.image_file,
        'image_path': product_static_path(product_record),
        'image_url': image_url,
        'gallery_images': [image_url] if image_url else [],
        'details': details,
        'ui_flags': ui_flags,
    }


def _seed_shop_preview_images():
    preview_images_by_slug = defaultdict(list)

    try:
        seed_rows = load_catalog_seed()
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return preview_images_by_slug

    valid_slugs = {collection['slug'] for collection in SHOP_COLLECTIONS}
    for raw_row in seed_rows:
        collection_slug = normalize_catalog_category(raw_row.get('collection_slug'))
        if collection_slug not in valid_slugs:
            continue

        image_path = str(raw_row.get('image_path') or '').strip().replace('\\', '/').lstrip('/')
        if not image_path:
            continue

        preview_images_by_slug[collection_slug].append(
            {
                'url': url_for('static', filename=image_path),
                'alt': str(raw_row.get('name') or raw_row.get('collection_label') or 'Collection preview').strip(),
            }
        )

    return preview_images_by_slug


def build_shop_collections(max_preview_images=3):
    collection_slugs = [collection['slug'] for collection in SHOP_COLLECTIONS]
    product_rows = (
        Product.query
        .filter(Product.collection_slug.in_(collection_slugs))
        .order_by(Product.collection_slug.asc(), Product.id.asc())
        .all()
    )

    products_by_slug = defaultdict(list)
    for product in product_rows:
        products_by_slug[product.collection_slug].append(product)

    seed_preview_images = _seed_shop_preview_images()
    shop_collections = []

    for collection in SHOP_COLLECTIONS:
        preview_images = []

        for product in products_by_slug.get(collection['slug'], [])[:max_preview_images]:
            image_url = product_image_url(product)
            if not image_url:
                continue
            preview_images.append(
                {
                    'url': image_url,
                    'alt': (product.name or collection['slug']).strip(),
                }
            )

        if not preview_images:
            preview_images = seed_preview_images.get(collection['slug'], [])[:max_preview_images]

        shop_collections.append(
            {
                **collection,
                'preview_images': preview_images,
            }
        )

    return shop_collections


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


def is_admin_desk_authenticated():
    return session.get('admin_secret_authenticated') is True


def search_store_products(search_term="", max_price=100000):
    clean_term = str(search_term or '').strip()
    if not clean_term:
        return "System info: Search term missing."

    try:
        normalized_max_price = max(0, int(max_price or 100000))
    except (TypeError, ValueError):
        normalized_max_price = 100000

    try:
        products = find_bot_products(search_term=clean_term, max_price=normalized_max_price, limit=5)
    except Exception as exc:
        app.logger.warning('Bot product search failed: %s', exc)
        return f"Database Error: {exc}"

    if not products:
        return f"System info: '{clean_term}' se related ₹{normalized_max_price} ke andar koi product database mein nahi mila."

    result_lines = ["Items found in database:"]
    for product in products:
        result_lines.append(
            f"- {product.name} | {product.collection_label} | {product.group_name} (Price: ₹{max(0, int(product.price or 0))})"
        )
    return "\n".join(result_lines)


def normalize_bot_history(raw_history):
    if not isinstance(raw_history, list):
        return []

    normalized = []
    for entry in raw_history[-BOT_MAX_HISTORY:]:
        if not isinstance(entry, dict):
            continue
        role = str(entry.get('role') or '').strip().lower()
        if role not in {'user', 'assistant'}:
            continue
        content = str(entry.get('text') or entry.get('content') or '').strip()
        if not content:
            continue
        normalized.append({'role': role, 'content': content[:3000]})
    return normalized[-BOT_MAX_HISTORY:]


def bot_collection_redirect_url(collection_slug):
    endpoint_map = {
        'hidden-message': 'hidden_message',
        'story-candle': 'story_candle',
        'zodiac-candle': 'zodiac_candle',
        'break-to-reveal': 'break_to_reveal',
        'candle-date-kit': 'candle_date_kit',
        'gift-sets': 'gift_sets',
    }
    endpoint_name = endpoint_map.get(normalize_catalog_category(collection_slug) or str(collection_slug or '').strip().lower())
    if not endpoint_name:
        return url_for('shop')
    return url_for(endpoint_name)


def score_bot_product_match(product, search_term, normalized_slug):
    haystacks = {
        'name': str(product.name or '').strip().lower(),
        'collection_label': str(product.collection_label or '').strip().lower(),
        'group_name': str(product.group_name or '').strip().lower(),
        'collection_slug': str(product.collection_slug or '').strip().lower(),
    }
    search_lower = str(search_term or '').strip().lower()
    search_words = [word for word in re.findall(r'[a-z0-9]+', search_lower) if len(word) > 1]
    score = 0

    if normalized_slug and haystacks['collection_slug'] == normalized_slug:
        score += 120
    if search_lower and haystacks['name'] == search_lower:
        score += 100

    for key, value in haystacks.items():
        if not value:
            continue
        if search_lower and search_lower in value:
            score += 32 if key == 'name' else 24
        for word in search_words:
            if word in value:
                score += 12 if key == 'name' else 8

    score += min(max(0, int(product.likes or 0)), 25)
    return score


def find_bot_products(search_term="", max_price=100000, limit=5):
    clean_term = str(search_term or '').strip()
    if not clean_term:
        return []

    try:
        normalized_max_price = max(0, int(max_price or 100000))
    except (TypeError, ValueError):
        normalized_max_price = 100000

    normalized_slug = normalize_catalog_category(clean_term)
    pattern = f"%{clean_term}%"
    query = Product.query.filter(Product.price <= normalized_max_price)

    filters = [
        Product.collection_label.ilike(pattern),
        Product.group_name.ilike(pattern),
        Product.collection_slug.ilike(pattern),
        Product.name.ilike(pattern),
    ]
    if normalized_slug:
        filters.append(Product.collection_slug == normalized_slug)

    products = (
        query
        .filter(or_(*filters))
        .order_by(Product.likes.desc(), Product.id.asc())
        .limit(max(limit * 3, 9))
        .all()
    )

    ranked = sorted(
        products,
        key=lambda product: (
            -score_bot_product_match(product, clean_term, normalized_slug),
            -max(0, int(product.likes or 0)),
            int(product.id or 0),
        )
    )
    return ranked[:limit]


def build_bot_product_card(product_record):
    if not product_record:
        return None

    image_url = product_image_url(product_record)
    if not image_url:
        return None

    return {
        'product_id': int(product_record.id),
        'name': str(product_record.name or 'Meltix Pick').strip(),
        'image_url': image_url,
        'redirect_url': f"{bot_collection_redirect_url(product_record.collection_slug)}?product={int(product_record.id)}",
    }


def suggest_product_card(search_term="", max_price=100000):
    products = find_bot_products(search_term=search_term, max_price=max_price, limit=1)
    product = products[0] if products else None
    if not product:
        return "No suitable product card found for that request.", None

    tool_text = (
        f"Suggested product card ready: {product.name} | {product.collection_label} | "
        f"{product.group_name or product.collection_slug}"
    )
    return tool_text, build_bot_product_card(product)


def resolve_bot_redirect(destination):
    clean_destination = str(destination or '').strip().lower()
    if not clean_destination:
        return None

    for target in BOT_REDIRECT_DESTINATIONS:
        if any(keyword in clean_destination for keyword in target['keywords']):
            endpoint = target['endpoint']
            query = target.get('query') or {}
            return {
                'label': target['label'],
                'redirect_url': url_for(endpoint, **query),
            }

    normalized_category = normalize_catalog_category(clean_destination)
    if normalized_category:
        endpoint_map = {
            'hidden-message': 'hidden_message',
            'story-candle': 'story_candle',
            'zodiac-candle': 'zodiac_candle',
            'break-to-reveal': 'break_to_reveal',
            'candle-date-kit': 'candle_date_kit',
            'gift-sets': 'gift_sets',
        }
        endpoint_name = endpoint_map.get(normalized_category)
        if endpoint_name:
            return {
                'label': normalized_category.replace('-', ' ').title(),
                'redirect_url': url_for(endpoint_name),
            }

    return None


def redirect_user(destination=""):
    resolved = resolve_bot_redirect(destination)
    if not resolved:
        return "Destination not available for redirect.", None

    return (
        f"Redirect prepared for {resolved['label']}.",
        resolved,
    )




def detect_bot_language_style(prior_history, user_message):
    opener = ''
    for entry in prior_history:
        if entry.get('role') == 'user' and entry.get('content'):
            opener = str(entry.get('content') or '').strip()
            if opener:
                break
    if not opener:
        opener = str(user_message or '').strip()

    if re.search(r'[\u0900-\u097F]', opener):
        return 'hindi'

    words = re.findall(r'[a-z]+', opener.lower())
    if any(word in BOT_ROMAN_HINDI_MARKERS for word in words):
        return 'hinglish'

    return 'english'


def build_bot_system_prompt(prior_history, user_message, bot_context):
    language_style = detect_bot_language_style(prior_history, user_message)
    context_label = BOT_CONTEXT_LABELS.get(str(bot_context or '').strip().lower(), 'general browsing')
    return (
        f"{BOT_SYSTEM_PROMPT}\n\n"
        f"[SESSION LOCK]\n"
        f"- The user started in {language_style}. Reply only in {language_style} unless the user clearly switches.\n"
        f"- Current page context: {context_label}.\n"
        f"- Your first goal in this session is to move the user toward a product, recommendation, budget, or collection choice."
    )


def get_bot_static_message(language_style, key):
    language = str(language_style or 'english').strip().lower()
    copy = {
        'busy': {
            'english': 'Meltix Bot is busy right now. Try again in a moment.',
            'hinglish': 'Meltix Bot abhi busy hai. Thodi der mein phir try karo.',
            'hindi': '\u092e\u0947\u0932\u094d\u091f\u093f\u0915\u094d\u0938 \u092c\u0949\u091f \u0905\u092d\u0940 \u0935\u094d\u092f\u0938\u094d\u0924 \u0939\u0948\u0964 \u0925\u094b\u0921\u093c\u0940 \u0926\u0947\u0930 \u092e\u0947\u0902 \u092b\u093f\u0930 \u0915\u094b\u0936\u093f\u0936 \u0915\u0930\u0947\u0902\u0964',
        },
        'empty': {
            'english': 'Welcome. Looking for a gift, a candle, or a quick suggestion?',
            'hinglish': 'Welcome. Gift, candle, ya quick suggestion chahiye?',
            'hindi': '\u0938\u094d\u0935\u093e\u0917\u0924 \u0939\u0948\u0964 \u0917\u093f\u092b\u094d\u091f, \u0915\u0948\u0902\u0921\u0932, \u092f\u093e \u0915\u094b\u0908 quick suggestion \u091a\u093e\u0939\u093f\u090f?',
        }
    }
    return copy.get(key, {}).get(language) or copy.get(key, {}).get('english', '')


def finalize_bot_reply(raw_text, language_style, fallback_key='empty'):
    text = re.sub(r'\s+', ' ', str(raw_text or '')).strip()
    if not text:
        text = get_bot_static_message(language_style, fallback_key)

    parts = [part.strip() for part in re.split(r'(?<=[.!?\u0964])\s+|\n+', text) if part.strip()]
    concise = ' '.join(parts[:3]) if parts else text

    if len(concise) > 260:
        concise = concise[:257].rsplit(' ', 1)[0].rstrip(' ,;:-') + '...'

    return concise or get_bot_static_message(language_style, fallback_key)


def make_bot_assistant_message(content, tool_calls=None):
    message = {"role": "assistant", "content": content or ""}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                }
            }
            for tool_call in tool_calls
        ]
    return message


def has_malformed_bot_tool_call(message):
    if getattr(message, "tool_calls", None):
        return False
    content = (getattr(message, "content", "") or "").lower()
    bad_markers = ("<function", "</function>", "search_store_products")
    return any(marker in content for marker in bad_markers)


def get_bot_completion(messages, use_tools=True):
    if litellm_completion is None:
        return None, None

    request_kwargs = {"messages": messages}
    models = BOT_MODELS_TO_TRY
    if use_tools:
        request_kwargs["tools"] = BOT_TOOLS
        request_kwargs["tool_choice"] = "auto"
        models = BOT_TOOL_MODELS_TO_TRY

    for model in models:
        try:
            response = litellm_completion(model=model, **request_kwargs)
            if use_tools and has_malformed_bot_tool_call(response.choices[0].message):
                app.logger.warning('%s returned malformed tool-call text instead of structured tool_calls.', model)
                continue
            return response, model
        except Exception as exc:
            app.logger.warning('Bot model %s failed: %s', model, exc)
            continue

    return None, None


def parse_bot_tool_arguments(raw_arguments):
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    return {}


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


def normalize_payment_status(value):
    candidate = str(value or '').strip().title()
    return candidate if candidate in PAYMENT_STATUS_OPTIONS else 'Pending'


def normalize_delivery_status(value):
    candidate = str(value or '').strip().title()
    return candidate if candidate in DELIVERY_STATUS_OPTIONS else 'Pending'


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


def normalize_checkout_request_items(raw_items):
    if not isinstance(raw_items, list):
        return []

    normalized = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        try:
            product_id = int(item.get('product_id') or item.get('id') or 0)
        except (TypeError, ValueError):
            product_id = 0

        try:
            quantity = int(item.get('quantity') or item.get('qty') or 0)
        except (TypeError, ValueError):
            quantity = 0

        if product_id <= 0 or quantity <= 0:
            continue

        normalized.append(
            {
                'product_id': product_id,
                'quantity': quantity,
                'custom_text': str(item.get('customText') or item.get('custom_text') or '').strip()[:500],
                'fragrance': str(item.get('fragrance') or item.get('scent') or '').strip()[:120],
            }
        )

    return normalized


def build_checkout_line_items(requested_items, product_map):
    line_items = []
    subtotal = 0

    for requested_item in requested_items:
        product = product_map[requested_item['product_id']]
        details = safe_json_loads(product.details_json, {})
        unit_price = max(0, int(product.price or 0))
        quantity = requested_item['quantity']
        line_total = unit_price * quantity

        line_item = {
            'id': product.id,
            'product_id': product.id,
            'name': product.name,
            'title': details.get('title') or product.name,
            'collection_slug': product.collection_slug,
            'group_name': product.group_name,
            'image_url': product_image_url(product),
            'price': unit_price,
            'quantity': quantity,
            'line_total': line_total,
        }

        if requested_item['custom_text']:
            line_item['custom_text'] = requested_item['custom_text']
        if requested_item['fragrance']:
            line_item['fragrance'] = requested_item['fragrance']

        line_items.append(line_item)
        subtotal += line_total

    return line_items, subtotal


def get_razorpay_key_id():
    return (os.environ.get('RAZORPAY_KEY_ID') or '').strip()


def get_razorpay_client():
    key_id = get_razorpay_key_id()
    key_secret = (os.environ.get('RAZORPAY_KEY_SECRET') or '').strip()
    if not key_id or not key_secret:
        raise RuntimeError('Razorpay credentials are not configured.')
    return razorpay.Client(auth=(key_id, key_secret))


def normalize_checkout_phone(raw_value):
    digits = re.sub(r'\D', '', str(raw_value or ''))
    if 10 <= len(digits) <= 15:
        return digits
    return ''


def normalize_checkout_address(raw_address, fallback_name=''):
    address = raw_address if isinstance(raw_address, dict) else {}
    return {
        'name': str(address.get('name') or fallback_name or '').strip()[:120],
        'line1': str(address.get('line1') or address.get('address') or '').strip()[:160],
        'line2': str(address.get('line2') or '').strip()[:160],
        'city': str(address.get('city') or '').strip()[:80],
        'state': str(address.get('state') or '').strip()[:80],
        'postal_code': str(address.get('postal_code') or address.get('pin_code') or address.get('pincode') or '').strip()[:20],
        'country': str(address.get('country') or 'India').strip()[:60] or 'India',
    }


def validate_checkout_address(address, label):
    if not address['name']:
        raise CheckoutError(f'{label} name is required.')
    if not address['line1']:
        raise CheckoutError(f'{label} address is required.')
    if not address['city']:
        raise CheckoutError(f'{label} city is required.')
    if not address['state']:
        raise CheckoutError(f'{label} state is required.')
    if not address['postal_code'] or not re.fullmatch(r'\d{6}', address['postal_code']):
        raise CheckoutError(f'{label} PIN Code must be a valid 6-digit number.')


def build_checkout_draft(raw_payload):
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    session_email = (session.get('profile_email') or '').strip().lower()
    requested_email = str(payload.get('email') or '').strip().lower()

    if session_email and requested_email and requested_email != session_email:
        raise CheckoutError('Unauthorized checkout email', status_code=403, error_code='unauthorized_checkout')

    user_email = session_email or requested_email
    if not user_email:
        raise CheckoutError('Email is required.')

    requested_name = str(payload.get('name') or session.get('profile_name') or '').strip()
    if not requested_name:
        raise CheckoutError('Name is required.')

    phone_number = normalize_checkout_phone(payload.get('phone') or payload.get('phone_number'))
    if not phone_number:
        raise CheckoutError('Phone number is required.')

    shipping_address = normalize_checkout_address(payload.get('shipping'), fallback_name=requested_name)
    validate_checkout_address(shipping_address, 'Shipping')

    billing_same_as_shipping = bool(payload.get('billing_same_as_shipping', True))
    if billing_same_as_shipping:
        billing_address = dict(shipping_address)
    else:
        billing_address = normalize_checkout_address(payload.get('billing'), fallback_name=requested_name)
        validate_checkout_address(billing_address, 'Billing')

    requested_items = normalize_checkout_request_items(payload.get('items'))
    if not requested_items:
        raise CheckoutError('At least one valid cart item is required.')

    product_ids = sorted({item['product_id'] for item in requested_items})
    products = Product.query.filter(Product.id.in_(product_ids)).all()
    product_map = {product.id: product for product in products}

    missing_ids = [str(product_id) for product_id in product_ids if product_id not in product_map]
    if missing_ids:
        raise CheckoutError(f"Products not found: {', '.join(missing_ids)}", status_code=404, error_code='products_missing')

    requested_quantities = defaultdict(int)
    for item in requested_items:
        requested_quantities[item['product_id']] += item['quantity']

    for product_id, quantity in requested_quantities.items():
        available_stock = max(0, int(product_map[product_id].stock_quantity or 0))
        if quantity > available_stock:
            raise CheckoutError(
                f"Only {available_stock} left in stock for {product_map[product_id].name}.",
                status_code=409,
                error_code='insufficient_stock',
            )

    _, subtotal = build_checkout_line_items(requested_items, product_map)

    coupon_code = str(payload.get('coupon_code') or '').strip().upper()
    discount_amount = 0
    if coupon_code:
        coupon = Coupon.query.filter_by(code=coupon_code).first()
        if not coupon:
            raise CheckoutError('Coupon code not found', status_code=404, error_code='coupon_missing')
        if not coupon_is_available(coupon):
            raise CheckoutError('This coupon is not available right now', status_code=400, error_code='coupon_unavailable')
        discount_amount = min(
            subtotal,
            int(round(subtotal * (max(0, int(coupon.discount_percentage or 0)) / 100.0)))
        )

    shipping_fee = 0
    total_amount = max(subtotal + shipping_fee - discount_amount, 0)

    return {
        'email': user_email,
        'name': requested_name[:120],
        'phone': phone_number,
        'shipping': shipping_address,
        'billing_same_as_shipping': billing_same_as_shipping,
        'billing': billing_address,
        'coupon_code': coupon_code,
        'items': requested_items,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'shipping_fee': shipping_fee,
        'total_amount': total_amount,
        'currency': 'INR',
    }


def apply_checkout_address_to_profile(profile_record, checkout_draft):
    profile_record.display_name = checkout_draft['name'] or profile_record.display_name
    profile_record.phone = checkout_draft['phone']

    shipping = checkout_draft['shipping']
    billing = checkout_draft['billing']

    profile_record.shipping_name = shipping['name']
    profile_record.shipping_line1 = shipping['line1']
    profile_record.shipping_line2 = shipping['line2']
    profile_record.shipping_city = shipping['city']
    profile_record.shipping_state = shipping['state']
    profile_record.shipping_postal_code = shipping['postal_code']
    profile_record.shipping_country = shipping['country']

    profile_record.billing_same_as_shipping = bool(checkout_draft['billing_same_as_shipping'])
    profile_record.billing_name = billing['name']
    profile_record.billing_line1 = billing['line1']
    profile_record.billing_line2 = billing['line2']
    profile_record.billing_city = billing['city']
    profile_record.billing_state = billing['state']
    profile_record.billing_postal_code = billing['postal_code']
    profile_record.billing_country = billing['country']


def finalize_checkout_order(checkout_draft, payment_context=None):
    requested_quantities = defaultdict(int)
    for item in checkout_draft['items']:
        requested_quantities[item['product_id']] += item['quantity']

    product_ids = sorted(requested_quantities.keys())
    profile_record = UserAccount.query.filter_by(email=checkout_draft['email']).with_for_update().first()
    if not profile_record:
        profile_record = get_or_create_profile(checkout_draft['email'], checkout_draft['name'])
        db.session.flush()

    locked_products = (
        Product.query
        .filter(Product.id.in_(product_ids))
        .order_by(Product.id.asc())
        .with_for_update()
        .all()
    )
    product_map = {product.id: product for product in locked_products}

    missing_ids = [str(product_id) for product_id in product_ids if product_id not in product_map]
    if missing_ids:
        raise CheckoutError(f"Products not found: {', '.join(missing_ids)}", status_code=404, error_code='products_missing')

    for product_id, quantity in requested_quantities.items():
        product = product_map[product_id]
        available_stock = max(0, int(product.stock_quantity or 0))
        if quantity > available_stock:
            raise CheckoutError(
                f"Only {available_stock} left in stock for {product.name}.",
                status_code=409,
                error_code='insufficient_stock',
            )

    line_items, subtotal = build_checkout_line_items(checkout_draft['items'], product_map)

    discount_amount = 0
    applied_coupon_code = None
    coupon_code = (checkout_draft.get('coupon_code') or '').strip().upper()
    if coupon_code:
        coupon = Coupon.query.filter_by(code=coupon_code).with_for_update().first()
        if not coupon:
            raise CheckoutError('Coupon code not found', status_code=404, error_code='coupon_missing')
        if not coupon_is_available(coupon):
            raise CheckoutError('This coupon is not available right now', status_code=409, error_code='coupon_unavailable')

        discount_amount = min(
            subtotal,
            int(round(subtotal * (max(0, int(coupon.discount_percentage or 0)) / 100.0)))
        )
        coupon.current_uses = int(coupon.current_uses or 0) + 1
        applied_coupon_code = coupon.code

    shipping_fee = max(0, int(checkout_draft.get('shipping_fee') or 0))
    total_amount = max(subtotal + shipping_fee - discount_amount, 0)
    amount_paise = total_amount * 100

    if payment_context and int(payment_context.get('amount_paise') or 0) != amount_paise:
        raise CheckoutError('Payment amount mismatch. Please try checkout again.', status_code=409, error_code='amount_mismatch')

    for product_id, quantity in requested_quantities.items():
        product = product_map[product_id]
        product.stock_quantity = max(0, int(product.stock_quantity or 0) - quantity)

    apply_checkout_address_to_profile(profile_record, checkout_draft)

    custom_note_blob = " ".join(
        str(item.get('custom_text') or '').strip()
        for item in line_items
        if str(item.get('custom_text') or '').strip()
    )
    scent_notes = extract_scent_notes({'custom_note': custom_note_blob}, line_items)
    stage = get_stage_config('placed')

    reference = str((payment_context or {}).get('payment_id') or time.time_ns()).strip()
    sanitized_reference = re.sub(r'[^A-Za-z0-9]', '', reference).upper()
    order_code = f"MX-{sanitized_reference[:36] or str(time.time_ns())[:36]}"

    order_record = ProfileOrder(
        user_email=checkout_draft['email'],
        order_code=order_code,
        payment_status='Pending',
        delivery_status='Pending',
        stage_key='placed',
        status_label=stage['label'],
        tracking_note=stage['description'],
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        total_amount=total_amount,
        currency=checkout_draft.get('currency') or 'INR',
        item_count=sum(item['quantity'] for item in line_items),
        line_items_json=json.dumps(line_items, ensure_ascii=False),
        scent_notes_json=json.dumps(scent_notes, ensure_ascii=False),
        confirmation_email_sent=False,
    )
    db.session.add(order_record)
    db.session.flush()

    sync_glow_points_for_user(profile_record)

    return {
        'order_record': order_record,
        'subtotal': subtotal,
        'shipping_fee': shipping_fee,
        'discount_amount': discount_amount,
        'discount_code': applied_coupon_code,
        'total_amount': total_amount,
        'remaining_stock': {
            str(product_id): max(0, int(product_map[product_id].stock_quantity or 0))
            for product_id in product_ids
        },
    }


def issue_payment_refund(razorpay_client, payment_id, amount_paise, reason):
    try:
        refund_payload = {
            'amount': int(amount_paise or 0),
            'notes': {
                'reason': str(reason or 'Checkout finalization failed')[:255],
            },
        }
        refund = razorpay_client.payment.refund(payment_id, refund_payload)
        return {
            'success': True,
            'refund_id': refund.get('id'),
            'status': refund.get('status'),
        }
    except Exception:
        app.logger.exception('Automatic refund request failed for payment %s', payment_id)
        return {
            'success': False,
            'refund_id': None,
            'status': 'failed',
        }


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
        "payment_status": normalize_payment_status(getattr(order_record, 'payment_status', 'Pending')),
        "delivery_status": normalize_delivery_status(getattr(order_record, 'delivery_status', 'Pending')),
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


def format_profile_shipping_address(profile_record):
    if not profile_record:
        return "Address unavailable"

    address_parts = [
        str(profile_record.shipping_name or '').strip(),
        str(profile_record.shipping_line1 or '').strip(),
        str(profile_record.shipping_line2 or '').strip(),
        str(profile_record.shipping_city or '').strip(),
        str(profile_record.shipping_state or '').strip(),
        str(profile_record.shipping_postal_code or '').strip(),
        str(profile_record.shipping_country or '').strip(),
    ]
    compact = [part for part in address_parts if part]
    return ", ".join(compact) if compact else "Address unavailable"


def normalize_order_item_quantity(value):
    try:
        return max(1, int(value or 1))
    except (TypeError, ValueError):
        return 1


def build_order_items_summary(order_record, separator=", "):
    item_labels = []
    for item in safe_json_loads(order_record.line_items_json, []):
        name = str(item.get('title') or item.get('name') or 'Meltix Candle').strip()
        quantity = normalize_order_item_quantity(item.get('quantity'))
        item_labels.append(f"{name} x{quantity}")
    return separator.join(item_labels) if item_labels else "Meltix creation"


def build_order_confirmation_email_html(order_record, profile_record, estimated_delivery_date):
    customer_name = escape(
        (profile_record.display_name if profile_record else '') or order_record.user_email.split('@')[0] or 'Collector'
    )
    order_code = escape(order_record.order_code)
    total_amount = escape(format_money(order_record.total_amount))
    delivery_date = escape(estimated_delivery_date.strftime("%d %b %Y"))
    delivery_address = escape(format_profile_shipping_address(profile_record))
    items_markup = ''.join(
        (
            f"<li style=\"margin:0 0 10px; color:#f5f0e8;\">"
            f"{escape(str(item.get('title') or item.get('name') or 'Meltix Candle'))}"
            f" <span style=\"color:#dcae6f;\">x{normalize_order_item_quantity(item.get('quantity'))}</span>"
            f"</li>"
        )
        for item in safe_json_loads(order_record.line_items_json, [])
    ) or "<li style=\"color:#f5f0e8;\">Your Meltix order is being prepared.</li>"

    return f"""
    <div style="margin:0; padding:32px 16px; background:#050505; font-family:Georgia, 'Times New Roman', serif; color:#f5f0e8;">
      <div style="max-width:680px; margin:0 auto; background:linear-gradient(180deg, rgba(220,174,111,0.08), rgba(5,5,5,0.98)); border:1px solid rgba(220,174,111,0.3); border-radius:28px; overflow:hidden; box-shadow:0 28px 80px rgba(0,0,0,0.45);">
        <div style="padding:40px 40px 28px; border-bottom:1px solid rgba(220,174,111,0.18);">
          <div style="font-size:12px; letter-spacing:0.38em; text-transform:uppercase; color:#dcae6f; margin-bottom:18px;">Meltix Atelier</div>
          <h1 style="margin:0; font-size:38px; line-height:1.1; font-weight:500; color:#fdfbf7;">Thank you for joining the Atelier</h1>
          <p style="margin:18px 0 0; font-size:16px; line-height:1.7; color:rgba(253,251,247,0.72);">Dear {customer_name}, your order has been received and the atelier is now preparing your ritual-worthy package.</p>
        </div>
        <div style="padding:32px 40px;">
          <div style="display:block; margin-bottom:24px; padding:22px 24px; border-radius:22px; background:rgba(255,255,255,0.02); border:1px solid rgba(220,174,111,0.18);">
            <div style="margin-bottom:10px; font-size:12px; letter-spacing:0.28em; text-transform:uppercase; color:rgba(253,251,247,0.54);">Order Reference</div>
            <div style="font-size:24px; color:#fdfbf7;">{order_code}</div>
            <div style="margin-top:16px; font-size:15px; color:rgba(253,251,247,0.72);">Amount Paid: <span style="color:#dcae6f;">{total_amount}</span></div>
            <div style="margin-top:10px; font-size:15px; color:rgba(253,251,247,0.72);">Estimated Delivery: <span style="color:#dcae6f;">{delivery_date}</span></div>
          </div>
          <div style="margin-bottom:24px;">
            <h2 style="margin:0 0 14px; font-size:18px; letter-spacing:0.08em; text-transform:uppercase; color:#dcae6f;">Inside Your Order</h2>
            <ul style="margin:0; padding-left:20px; color:#f5f0e8; line-height:1.7;">{items_markup}</ul>
          </div>
          <div style="padding:20px 22px; border-radius:20px; background:rgba(220,174,111,0.06); border:1px solid rgba(220,174,111,0.18);">
            <div style="margin-bottom:8px; font-size:12px; letter-spacing:0.24em; text-transform:uppercase; color:rgba(253,251,247,0.56);">Delivery Address</div>
            <div style="font-size:15px; line-height:1.8; color:#f5f0e8;">{delivery_address}</div>
          </div>
        </div>
      </div>
    </div>
    """.strip()


def build_order_confirmation_email_text(order_record, profile_record, estimated_delivery_date):
    customer_name = (
        (profile_record.display_name if profile_record else '') or order_record.user_email.split('@')[0] or 'Collector'
    )
    return (
        f"Thank you for joining the Atelier, {customer_name}.\n"
        f"Order ID: {order_record.order_code}\n"
        f"Amount Paid: {format_money(order_record.total_amount)}\n"
        f"Estimated Delivery: {estimated_delivery_date.strftime('%d %b %Y')}\n"
        f"Items: {build_order_items_summary(order_record)}\n"
        f"Delivery Address: {format_profile_shipping_address(profile_record)}"
    )


def send_order_confirmation_email(order_record, profile_record, estimated_delivery_date):
    smtp_host = (os.environ.get('SMTP_HOST') or '').strip()
    try:
        smtp_port = int(os.environ.get('SMTP_PORT') or 587)
    except (TypeError, ValueError):
        smtp_port = 587
    smtp_username = (os.environ.get('SMTP_USERNAME') or '').strip()
    smtp_password = (os.environ.get('SMTP_PASSWORD') or '').strip()
    smtp_from_email = (os.environ.get('SMTP_FROM_EMAIL') or smtp_username).strip()
    smtp_from_name = (os.environ.get('SMTP_FROM_NAME') or 'Meltix Atelier').strip()
    use_ssl = env_flag('SMTP_USE_SSL', default=False)
    use_tls = env_flag('SMTP_USE_TLS', default=not use_ssl)

    if not smtp_host or not smtp_from_email:
        app.logger.warning('Order confirmation email skipped because SMTP is not configured.')
        return False

    message = MIMEMultipart('alternative')
    message['Subject'] = f"Meltix Atelier | Order Confirmation {order_record.order_code}"
    message['From'] = f"{smtp_from_name} <{smtp_from_email}>"
    message['To'] = order_record.user_email
    message.attach(MIMEText(build_order_confirmation_email_text(order_record, profile_record, estimated_delivery_date), 'plain', 'utf-8'))
    message.attach(MIMEText(build_order_confirmation_email_html(order_record, profile_record, estimated_delivery_date), 'html', 'utf-8'))

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context(), timeout=20)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)

        with server:
            if not use_ssl and use_tls:
                server.starttls(context=ssl.create_default_context())
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.sendmail(smtp_from_email, [order_record.user_email], message.as_string())
        return True
    except Exception:
        app.logger.exception('Order confirmation email failed for %s', order_record.order_code)
        return False


def serialize_admin_order(order_record, profile_record):
    return {
        'order_id': order_record.order_code,
        'created_at': order_record.created_at,
        'created_at_display': order_record.created_at.strftime("%d %b %Y, %I:%M %p"),
        'customer_name': (profile_record.display_name if profile_record else '') or order_record.user_email,
        'customer_email': order_record.user_email,
        'customer_phone': (profile_record.phone if profile_record else '') or 'Not available',
        'customer_address': format_profile_shipping_address(profile_record),
        'items_summary': build_order_items_summary(order_record, separator=' • '),
        'amount_display': format_money(order_record.total_amount),
        'payment_status': normalize_payment_status(getattr(order_record, 'payment_status', 'Pending')),
        'delivery_status': normalize_delivery_status(getattr(order_record, 'delivery_status', 'Pending')),
    }


def user_has_candle_date_kit_order(user_email):
    if not user_email:
        return False

    date_keywords = (
        'candle date',
        'date kit',
        'date night',
        'ice breaker',
        'dine in',
        'cozy',
    )

    orders = ProfileOrder.query.filter_by(user_email=user_email).all()
    for order in orders:
        for item in safe_json_loads(order.line_items_json, []):
            searchable_text = " ".join(
                str(item.get(field_name) or '')
                for field_name in ('name', 'title', 'collection_slug', 'category', 'group_name')
            ).strip().lower()
            if searchable_text and any(keyword in searchable_text for keyword in date_keywords):
                return True

    return False


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


def calculate_glow_points_total(profile_record):
    order_count = ProfileOrder.query.filter_by(user_email=profile_record.email).count()
    review_count = Review.query.filter_by(user_id=profile_record.id).count()
    mission_count = len(normalize_completed_missions(profile_record.completed_missions_json))
    return (order_count * 100) + (review_count * 50) + (mission_count * MISSION_POINTS)


def sync_glow_points_for_user(profile_record):
    if not profile_record:
        return 0
    profile_record.glow_points = calculate_glow_points_total(profile_record)
    return profile_record.glow_points


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
    sync_glow_points_for_user(profile_record)

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
        order_record.payment_status = normalize_payment_status(raw_order.get("payment_status") or 'Paid')
        order_record.delivery_status = (
            'Delivered'
            if stage_key == 'delivered'
            else 'Shipped'
            if stage_key == 'shipped'
            else 'Pending'
        )
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
    profile_record = UserAccount.query.filter_by(email=user_email).first()
    if profile_record:
        sync_glow_points_for_user(profile_record)


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
            'price': max(0, int(product.price or 0)) if product else 0,
            'likes': product.likes if product else 0,
            'image_url': product_image_url(product) if product else None
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

@app.route('/api/bot/chat', methods=['POST'])
def bot_chat_api():
    data = request.get_json(silent=True) or {}
    user_message = str(data.get('message') or '').strip()
    if not user_message:
        return jsonify({'success': False, 'message': 'Message is required.'}), 400

    limited_response = rate_limit_response(
        'bot-chat',
        user_message='Too many bot messages too quickly. Please wait a few seconds and try again.',
        window_seconds=BOT_RATE_LIMIT_WINDOW_SECONDS,
        max_attempts=BOT_RATE_LIMIT_MAX_ATTEMPTS,
    )
    if limited_response:
        app.logger.warning('Bot chat rate limit hit for IP %s', get_client_ip())
        return limited_response

    prior_history = normalize_bot_history(data.get('history'))
    bot_context = str(data.get('context') or 'general').strip().lower()
    language_style = detect_bot_language_style(prior_history, user_message)
    system_prompt = build_bot_system_prompt(prior_history, user_message, bot_context)
    messages = [{"role": "system", "content": system_prompt}] + prior_history + [{
        "role": "user",
        "content": user_message[:3000],
    }]

    ai_response, used_model = get_bot_completion(messages, use_tools=True)
    if not ai_response:
        return jsonify({
            'success': False,
            'message': get_bot_static_message(language_style, 'busy'),
        }), 503

    response_message = ai_response.choices[0].message
    reply_text = (response_message.content or '').strip()
    product_card = None
    redirect_url = None

    if getattr(response_message, 'tool_calls', None):
        followup_messages = messages + [
            make_bot_assistant_message(reply_text, getattr(response_message, 'tool_calls', None))
        ]

        for tool_call in response_message.tool_calls:
            tool_name = str(tool_call.function.name or '').strip()
            tool_args = parse_bot_tool_arguments(tool_call.function.arguments)
            tool_output = "Tool unavailable."

            if tool_name == 'search_store_products':
                tool_output = search_store_products(
                    search_term=tool_args.get('search_term', ''),
                    max_price=tool_args.get('max_price', 100000),
                )
            elif tool_name == 'suggest_product_card':
                tool_output, suggested_card = suggest_product_card(
                    search_term=tool_args.get('search_term', ''),
                    max_price=tool_args.get('max_price', 100000),
                )
                if suggested_card:
                    product_card = suggested_card
            elif tool_name == 'redirect_user':
                tool_output, redirect_payload = redirect_user(
                    destination=tool_args.get('destination', ''),
                )
                if redirect_payload:
                    redirect_url = redirect_payload.get('redirect_url')

            followup_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": tool_output,
            })

        final_response, final_model = get_bot_completion(followup_messages, use_tools=False)
        final_text = finalize_bot_reply(
            ((final_response.choices[0].message.content or '').strip()) if final_response else reply_text,
            language_style,
        )

        return jsonify({
            'success': True,
            'reply': final_text,
            'product_card': product_card,
            'redirect_url': redirect_url,
            'model': final_model or used_model,
            'used_tool': True,
        }), 200

    return jsonify({
        'success': True,
        'reply': finalize_bot_reply(reply_text, language_style),
        'product_card': None,
        'redirect_url': None,
        'model': used_model,
        'used_tool': False,
    }), 200


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/shop')
def shop():
    return render_template(
        'shop.html',
        shop_collections=build_shop_collections(),
        show_nav_options=True,
        bot_context='shop',
    )

@app.route('/checkout')
def checkout():
    session_email = (session.get('profile_email') or '').strip().lower()
    profile_record = UserAccount.query.filter_by(email=session_email).first() if session_email else None
    address_book = serialize_address(profile_record)
    prefill = {
        'name': (profile_record.display_name if profile_record else (session.get('profile_name') or '')).strip(),
        'email': session_email,
        'phone': address_book.get('phone_number') or '',
        'shipping': address_book.get('shipping') or {},
        'billing_same_as_shipping': address_book.get('billing_same_as_shipping', True),
        'billing': address_book.get('billing') or {},
    }
    return render_template(
        'checkout.html',
        razorpay_key_id=get_razorpay_key_id(),
        checkout_prefill=prefill,
    )


@app.route('/order-success')
def order_success():
    order_id = str(request.args.get('order_id') or session.get('last_order_id') or '').strip().upper()
    if not order_id:
        return redirect(url_for('shop'))

    order_record = ProfileOrder.query.filter_by(order_code=order_id).first()
    if not order_record:
        return redirect(url_for('profile'))

    profile_record = UserAccount.query.filter_by(email=order_record.user_email).first()
    if normalize_payment_status(order_record.payment_status) != 'Paid':
        order_record.payment_status = 'Paid'
        order_record.paid_at = order_record.paid_at or datetime.utcnow()

    payment_reference_date = order_record.paid_at or datetime.utcnow()
    estimated_delivery_date = payment_reference_date + timedelta(days=5)

    if not bool(getattr(order_record, 'confirmation_email_sent', False)):
        if send_order_confirmation_email(order_record, profile_record, estimated_delivery_date):
            order_record.confirmation_email_sent = True

    db.session.commit()
    session['last_order_id'] = order_record.order_code
    session.modified = True

    return render_template(
        'order_success.html',
        order=serialize_order(order_record),
        customer_name=(profile_record.display_name if profile_record else '') or order_record.user_email,
        customer_email=order_record.user_email,
        estimated_delivery_date=estimated_delivery_date.strftime("%d %b %Y"),
    )


@app.route('/admin-secret-desk', methods=['GET', 'POST'])
def admin_secret_desk():
    if request.args.get('logout') == '1':
        session.pop('admin_secret_authenticated', None)
        session.modified = True
        return redirect(url_for('admin_secret_desk'))

    auth_error = ''
    if request.method == 'POST':
        submitted_password = str(request.form.get('password') or '').strip()
        if submitted_password == ADMIN_SECRET_PASSWORD:
            session['admin_secret_authenticated'] = True
            session.modified = True
            return redirect(url_for('admin_secret_desk'))
        auth_error = 'Incorrect password. Please try again.'

    if not is_admin_desk_authenticated():
        return render_template('admin_dashboard.html', is_authenticated=False, auth_error=auth_error)

    orders = ProfileOrder.query.order_by(ProfileOrder.created_at.desc()).all()
    order_emails = sorted({order.user_email for order in orders if order.user_email})
    profiles = {
        profile.email: profile
        for profile in UserAccount.query.filter(UserAccount.email.in_(order_emails)).all()
    } if order_emails else {}
    admin_orders = [serialize_admin_order(order, profiles.get(order.user_email)) for order in orders]

    return render_template(
        'admin_dashboard.html',
        is_authenticated=True,
        orders=admin_orders,
        delivery_status_options=DELIVERY_STATUS_OPTIONS,
    )


@app.route('/update-order-status/<order_id>', methods=['POST'])
def update_order_status(order_id):
    if not is_admin_desk_authenticated():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    order_record = ProfileOrder.query.filter_by(order_code=str(order_id).strip().upper()).first()
    if not order_record:
        return jsonify({'success': False, 'message': 'Order not found'}), 404

    data = request.get_json(silent=True) or {}
    requested_status = str(data.get('delivery_status') or '').strip().title()
    if requested_status not in DELIVERY_STATUS_OPTIONS:
        return jsonify({'success': False, 'message': 'Invalid delivery status'}), 400

    order_record.delivery_status = requested_status
    mapped_stage_key = DELIVERY_STAGE_MAP.get(requested_status, 'placed')
    stage = get_stage_config(mapped_stage_key)
    order_record.stage_key = mapped_stage_key
    order_record.status_label = stage['label']
    order_record.tracking_note = stage['description']
    db.session.commit()

    return jsonify({
        'success': True,
        'delivery_status': order_record.delivery_status,
        'status_label': order_record.status_label,
        'tracking_note': order_record.tracking_note,
    }), 200

@app.route('/refund-policy')
def refund_policy():
    return render_template('refund_policy.html')

@app.route('/hidden-message')
def hidden_message():
    return render_template(
        'hidden_message.html',
        show_nav_options=False,
        bot_context='hidden-message',
    )

@app.route('/story-candle')
def story_candle():
    return render_template(
        'story_candle.html',
        show_nav_options=False,
        bot_context='story-candle',
    )

@app.route('/zodiac-candle')
def zodiac_candle():
    return render_template(
        'zodiac_candle.html',
        show_nav_options=False,
        bot_context='zodiac-candle',
    )

@app.route('/break-to-reveal')
def break_to_reveal():
    return render_template(
        'break_to_reveal.html',
        show_nav_options=False,
        bot_context='break-to-reveal',
    )

@app.route('/candle-date-kit')
def candle_date_kit():
    return render_template(
        'candle_date_kit.html',
        show_nav_options=False,
        bot_context='candle-date-kit',
    )

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


def normalize_india_mobile(value):
    digits = re.sub(r'\D', '', str(value or ''))
    if len(digits) == 12 and digits.startswith('91') and re.fullmatch(r'[6-9]\d{9}', digits[2:]):
        return digits[2:]
    if len(digits) == 11 and digits.startswith('0') and re.fullmatch(r'[6-9]\d{9}', digits[1:]):
        return digits[1:]
    if len(digits) == 10 and re.fullmatch(r'[6-9]\d{9}', digits):
        return digits
    return ''


def get_messagecentral_credentials():
    customer_id = (os.environ.get('MESSAGECENTRAL_CUSTOMER_ID') or '').strip()
    auth_token = (os.environ.get('MESSAGECENTRAL_AUTH_TOKEN') or '').strip()
    if not customer_id or not auth_token:
        raise RuntimeError('MessageCentral credentials are not configured.')
    return customer_id, auth_token


def messagecentral_request(method, endpoint, query_params):
    customer_id, auth_token = get_messagecentral_credentials()
    params = dict(query_params or {})
    params.setdefault('customerId', customer_id)
    url = f"https://cpaas.messagecentral.com{endpoint}?{urlencode(params)}"
    request_obj = Request(url, method=method.upper(), headers={'authToken': auth_token})

    try:
        with urlopen(request_obj, timeout=15) as response:
            payload = response.read().decode('utf-8')
            return json.loads(payload or '{}'), response.status
    except HTTPError as exc:
        raw_payload = exc.read().decode('utf-8', errors='replace')
        try:
            payload = json.loads(raw_payload or '{}')
        except json.JSONDecodeError:
            payload = {'message': raw_payload or 'MessageCentral request failed'}
        return payload, exc.code
    except URLError as exc:
        raise RuntimeError(f'MessageCentral request failed: {exc.reason}') from exc


def verify_google_credential(credential):
    google_client_id = (os.environ.get('GOOGLE_CLIENT_ID') or '').strip()
    if not google_client_id:
        raise RuntimeError('GOOGLE_CLIENT_ID is not configured.')

    token = str(credential or '').strip()
    if not token:
        raise ValueError('Google credential is required.')

    request_url = f"https://oauth2.googleapis.com/tokeninfo?{urlencode({'id_token': token})}"
    request_obj = Request(request_url, method='GET')

    try:
        with urlopen(request_obj, timeout=15) as response:
            payload = json.loads(response.read().decode('utf-8') or '{}')
    except HTTPError as exc:
        raw_payload = exc.read().decode('utf-8', errors='replace')
        app.logger.warning('Google token verification failed with HTTP %s: %s', exc.code, raw_payload)
        raise ValueError('Google sign-in verification failed.') from exc
    except URLError as exc:
        raise RuntimeError(f'Google sign-in verification failed: {exc.reason}') from exc

    issuer = str(payload.get('iss') or '').strip()
    audience = str(payload.get('aud') or '').strip()
    email = str(payload.get('email') or '').strip().lower()
    email_verified = str(payload.get('email_verified') or '').strip().lower() == 'true'

    try:
        expires_at = int(payload.get('exp') or 0)
    except (TypeError, ValueError):
        expires_at = 0

    if issuer not in {'accounts.google.com', 'https://accounts.google.com'}:
        raise ValueError('Google sign-in verification failed.')
    if audience != google_client_id or not email or not email_verified or expires_at <= int(time.time()):
        raise ValueError('Google sign-in verification failed.')

    return {
        'email': email,
        'name': str(payload.get('name') or '').strip(),
        'picture': str(payload.get('picture') or '').strip(),
    }


def get_verified_session_email(request_email=None):
    session_email = (session.get('profile_email') or '').strip().lower()
    requested_email = (request_email or '').strip().lower()

    if not session_email:
        return None, (jsonify({"success": False, "message": "Sign in required"}), 401)
    if requested_email and requested_email != session_email:
        return None, (jsonify({"success": False, "message": "Unauthorized profile request"}), 403)

    return session_email, None


def get_client_ip():
    if TRUST_PROXY_HEADERS:
        forwarded_for = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
        if forwarded_for:
            return forwarded_for

        real_ip = (request.headers.get('X-Real-IP') or '').strip()
        if real_ip:
            return real_ip

    return (request.remote_addr or 'unknown').strip() or 'unknown'


def check_rate_limit(bucket_name, window_seconds, max_attempts, identity_key=None):
    now = time.time()
    bucket_identity = (identity_key or get_client_ip() or 'unknown').strip() or 'unknown'
    bucket_key = f"{bucket_name}:{bucket_identity}"

    with FORM_RATE_LIMIT_LOCK:
        attempt_times = FORM_RATE_LIMIT_BUCKETS[bucket_key]
        cutoff = now - window_seconds

        while attempt_times and attempt_times[0] <= cutoff:
            attempt_times.popleft()

        if len(attempt_times) >= max_attempts:
            retry_after = max(1, int(window_seconds - (now - attempt_times[0])))
            return retry_after

        attempt_times.append(now)
        return 0


def check_form_rate_limit(bucket_name):
    return check_rate_limit(bucket_name, FORM_RATE_LIMIT_WINDOW_SECONDS, FORM_RATE_LIMIT_MAX_ATTEMPTS)


def rate_limit_response(
    bucket_name,
    user_message='Too many submissions. Please wait a few minutes and try again.',
    window_seconds=None,
    max_attempts=None,
    identity_key=None,
):
    retry_after = check_rate_limit(
        bucket_name,
        window_seconds if window_seconds is not None else FORM_RATE_LIMIT_WINDOW_SECONDS,
        max_attempts if max_attempts is not None else FORM_RATE_LIMIT_MAX_ATTEMPTS,
        identity_key=identity_key,
    )
    if retry_after <= 0:
        return None

    response = jsonify({'success': False, 'message': user_message})
    response.status_code = 429
    response.headers['Retry-After'] = str(retry_after)
    return response


@app.route('/api/catalog/<category>', methods=['GET'])
def catalog_api(category):
    normalized_category = normalize_catalog_category(category)
    if not normalized_category:
        return jsonify({'success': False, 'message': 'Unknown catalog category'}), 404

    products = (
        Product.query
        .filter_by(collection_slug=normalized_category)
        .order_by(Product.id.asc())
        .all()
    )
    return jsonify([serialize_product(product) for product in products]), 200


@app.route('/api/feedback', methods=['POST'])
def submit_feedback_form():
    data = request.get_json() or {}
    user_email = ((data.get('email') or session.get('profile_email') or '').strip().lower())
    message = (data.get('message') or '').strip()
    source_page = (data.get('source_page') or 'feedback').strip() or 'feedback'

    try:
        rating = int(data.get('rating') or 0)
    except (TypeError, ValueError):
        rating = 0

    if not user_email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400
    if rating < 1 or rating > 5:
        return jsonify({'success': False, 'message': 'Rating must be between 1 and 5'}), 400

    limited_response = rate_limit_response('feedback-form')
    if limited_response:
        app.logger.warning('Feedback rate limit hit for IP %s', get_client_ip())
        return limited_response

    try:
        submission = FeedbackSubmission(
            user_email=user_email,
            rating=rating,
            message=message,
            source_page=source_page[:120],
        )
        db.session.add(submission)
        db.session.commit()
        return jsonify({'success': True, 'submission_id': submission.id}), 201
    except Exception:
        db.session.rollback()
        app.logger.exception('Feedback submission failed')
        return jsonify({'success': False, 'message': GENERIC_ERROR_MESSAGE}), 500


@app.route('/api/bug-report', methods=['POST'])
def submit_bug_report_form():
    data = request.get_json() or {}
    user_email = ((data.get('email') or session.get('profile_email') or '').strip().lower())
    message = (data.get('message') or '').strip()
    source_page = (data.get('source_page') or 'bug-report').strip() or 'bug-report'

    if not user_email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400
    if not message:
        return jsonify({'success': False, 'message': 'Issue details are required'}), 400

    limited_response = rate_limit_response('bug-report-form')
    if limited_response:
        app.logger.warning('Bug report rate limit hit for IP %s', get_client_ip())
        return limited_response

    try:
        submission = BugReportSubmission(
            user_email=user_email,
            message=message,
            source_page=source_page[:120],
        )
        db.session.add(submission)
        db.session.commit()
        return jsonify({'success': True, 'submission_id': submission.id}), 201
    except Exception:
        db.session.rollback()
        app.logger.exception('Bug report submission failed')
        return jsonify({'success': False, 'message': GENERIC_ERROR_MESSAGE}), 500


@app.route('/api/studio/send-otp', methods=['POST'])
def studio_send_otp():
    data = request.get_json() or {}
    normalized_mobile = normalize_india_mobile(data.get('mobile_number') or data.get('phone') or '')
    if not normalized_mobile:
        return jsonify({'success': False, 'message': 'Please enter a valid Indian mobile number'}), 400

    try:
        payload, status_code = messagecentral_request(
            'POST',
            '/verification/v3/send',
            {
                'countryCode': '91',
                'flowType': 'SMS',
                'mobileNumber': normalized_mobile,
            },
        )
    except RuntimeError:
        app.logger.exception('Studio OTP send failed')
        return jsonify({'success': False, 'message': GENERIC_ERROR_MESSAGE}), 503

    verification_id = (((payload or {}).get('data') or {}).get('verificationId') or '').strip()
    response_code = int((payload or {}).get('responseCode') or 0)
    if status_code >= 400 or response_code != 200 or not verification_id:
        return jsonify({
            'success': False,
            'message': (payload or {}).get('message') or 'OTP could not be sent right now'
        }), 502

    session['studio_mobile_number'] = normalized_mobile
    session['studio_verification_id'] = verification_id
    session['studio_otp_verified'] = False
    return jsonify({'success': True, 'mobile_number': normalized_mobile}), 200


@app.route('/api/studio/verify-otp', methods=['POST'])
def studio_verify_otp():
    data = request.get_json() or {}
    otp_code = re.sub(r'\D', '', str(data.get('otp') or ''))
    verification_id = (session.get('studio_verification_id') or '').strip()
    mobile_number = (session.get('studio_mobile_number') or '').strip()

    if len(otp_code) < 4:
        return jsonify({'success': False, 'message': 'Please enter a valid OTP'}), 400
    if not verification_id or not mobile_number:
        return jsonify({'success': False, 'message': 'OTP session expired. Please request a new code.'}), 400

    try:
        payload, status_code = messagecentral_request(
            'GET',
            '/verification/v3/validateOtp',
            {
                'countryCode': '91',
                'mobileNumber': mobile_number,
                'verificationId': verification_id,
                'code': otp_code,
            },
        )
    except RuntimeError:
        app.logger.exception('Studio OTP verification failed')
        return jsonify({'success': False, 'message': GENERIC_ERROR_MESSAGE}), 503

    verification_status = (((payload or {}).get('data') or {}).get('verificationStatus') or '').strip().upper()
    response_code = int((payload or {}).get('responseCode') or 0)
    if status_code >= 400 or response_code != 200 or verification_status != 'VERIFICATION_COMPLETED':
        return jsonify({
            'success': False,
            'message': (payload or {}).get('message') or 'OTP verification failed'
        }), 400

    session['studio_otp_verified'] = True
    return jsonify({'success': True, 'verification_status': verification_status}), 200


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
    try:
        product_id = int(data.get('product_id') or 0)
    except (TypeError, ValueError):
        product_id = 0
    action = data.get('action')
    user_account = get_session_user()

    if not user_account:
        return jsonify({'success': False, 'message': 'Login required'}), 401
    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID required'}), 400

    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({'success': False, 'message': 'Product not found'}), 404

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
    review_text = str(data.get('review_text') or '').strip()[:1000]
    try:
        rating = int(data.get('rating') or 0)
    except (TypeError, ValueError):
        rating = 0
    try:
        user_account = get_session_user()
        product_id = int(data.get('product_id') or 0)

        if not user_account:
            return jsonify({'success': False, 'message': 'Login required to post a review'}), 401
        if not db.session.get(Product, product_id):
            return jsonify({'success': False, 'message': 'Product not found'}), 404
        if not review_text:
            return jsonify({'success': False, 'message': 'Review text is required'}), 400
        if rating < 1 or rating > 5:
            return jsonify({'success': False, 'message': 'Rating must be between 1 and 5'}), 400

        new_review = Review(
            product_id=product_id,
            user_id=user_account.id,
            user_name=data.get('user_name') or user_account.display_name,
            review_text=review_text,
            rating=rating
        )
        db.session.add(new_review)
        db.session.flush()
        sync_glow_points_for_user(user_account)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Review posted successfully!'}), 200
    except IntegrityError:
        # Postgres rule block karega agar user pehle hi review de chuka hai
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Aap already review de chuke hain!'}), 400
    except Exception:
        db.session.rollback()
        app.logger.exception('Review creation failed')
        return jsonify({'success': False, 'message': GENERIC_ERROR_MESSAGE}), 500


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
        db.session.flush()
        sync_glow_points_for_user(user_account)
        db.session.commit()
        return jsonify({"status": "success"}), 200
    except Exception:
        db.session.rollback()
        app.logger.exception('Review deletion failed')
        return jsonify({"status": "error", "message": GENERIC_ERROR_MESSAGE}), 500


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
    except Exception:
        db.session.rollback()
        app.logger.exception('Review like toggle failed')
        return jsonify({"status": "error", "message": GENERIC_ERROR_MESSAGE}), 500
    

# ==========================================
# 🔴 WISH LIST (SAVE FOR LATER) ROUTE 🔴
# ==========================================
@app.route('/toggle_wishlist', methods=['POST'])
def toggle_wishlist():
    data = request.get_json() or {}
    product_id = int(data.get('product_id') or 0)
    user_account = get_session_user()

    if not user_account:
        return jsonify({"status": "error", "message": "Login required"}), 401
    if not db.session.get(Product, product_id):
        return jsonify({"status": "error", "message": "Product not found"}), 404

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
    except Exception:
        db.session.rollback()
        app.logger.exception('Wishlist toggle failed')
        return jsonify({"status": "error", "message": GENERIC_ERROR_MESSAGE}), 500


@app.route('/api/profile/bootstrap', methods=['POST'])
def profile_bootstrap():
    data = request.get_json() or {}
    try:
        verified_google_user = verify_google_credential(data.get('credential'))
    except ValueError:
        return jsonify({"success": False, "message": "Google sign-in verification failed"}), 401
    except RuntimeError:
        app.logger.exception('Google sign-in verification failed')
        return jsonify({"success": False, "message": GENERIC_ERROR_MESSAGE}), 503

    email = verified_google_user['email']
    display_name = verified_google_user.get('name') or email.split('@')[0] or 'Meltix Collector'
    google_picture_url = verified_google_user.get('picture') or ''

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
    except Exception:
        db.session.rollback()
        app.logger.exception('Profile bootstrap failed')
        return jsonify({"success": False, "message": GENERIC_ERROR_MESSAGE}), 500


@app.route('/api/profile/logout', methods=['POST'])
def profile_logout():
    session.pop('profile_email', None)
    session.pop('profile_name', None)
    session.pop('profile_picture', None)
    return jsonify({"success": True}), 200


@app.route('/api/profile/avatar', methods=['POST'])
def update_profile_avatar():
    data = request.get_json() or {}
    email, error_response = get_verified_session_email(data.get('email'))
    if error_response:
        return error_response
    use_google_photo = bool(data.get('use_google_photo'))
    display_name = (data.get('name') or '').strip()
    google_picture_url = data.get('google_picture_url') or data.get('picture') or ''

    try:
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
    except Exception:
        db.session.rollback()
        app.logger.exception('Profile avatar update failed')
        return jsonify({"success": False, "message": GENERIC_ERROR_MESSAGE}), 500


@app.route('/api/profile/address', methods=['POST'])
def save_profile_address():
    data = request.get_json() or {}
    email, error_response = get_verified_session_email(data.get('email'))
    if error_response:
        return error_response

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
    except Exception:
        db.session.rollback()
        app.logger.exception('Profile address save failed')
        return jsonify({"success": False, "message": GENERIC_ERROR_MESSAGE}), 500


@app.route('/api/profile/scent-persona', methods=['POST'])
def save_scent_persona():
    data = request.get_json() or {}
    email, error_response = get_verified_session_email(data.get('email'))
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    notes = data.get('notes') or []

    if error_response:
        return error_response

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
    except Exception:
        db.session.rollback()
        app.logger.exception('Scent persona save failed')
        return jsonify({"success": False, "message": GENERIC_ERROR_MESSAGE}), 500


@app.route('/api/claim_mission', methods=['POST'])
def claim_mission():
    data = request.get_json() or {}
    user_email, error_response = get_verified_session_email(data.get('user_email'))
    mission_key = (data.get('mission_key') or '').strip()

    if error_response:
        return error_response

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
                # Candle Date Kit ke related real order hone chahiye
                if not user_has_candle_date_kit_order(user_email):
                    return jsonify({
                        "success": False,
                        "message": "Place a Candle Date Kit order before claiming this mission."
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
                feedback_record = (
                    FeedbackSubmission.query
                    .filter_by(user_email=user_email)
                    .order_by(FeedbackSubmission.created_at.desc())
                    .first()
                )
                if not feedback_record:
                    return jsonify({
                        "success": False,
                        "message": "Submit real feedback before claiming this mission."
                    }), 403

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

        sync_glow_points_for_user(profile_record)

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
    except Exception:
        db.session.rollback()
        app.logger.exception('Mission claim failed')
        return jsonify({"success": False, "message": GENERIC_ERROR_MESSAGE}), 500


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


@app.route('/api/payment/create', methods=['POST'])
def create_payment_order():
    data = request.get_json() or {}

    try:
        checkout_draft = build_checkout_draft(data)
    except CheckoutError as exc:
        return jsonify({'success': False, 'message': exc.message, 'error_code': exc.error_code}), exc.status_code

    try:
        razorpay_client = get_razorpay_client()
        receipt_seed = re.sub(r'[^A-Za-z0-9]', '', checkout_draft['email'].split('@')[0].upper())[:10] or 'MELTIX'
        receipt = f"MX{receipt_seed}{str(time.time_ns())[-18:]}"[:40]
        order_payload = {
            'amount': checkout_draft['total_amount'] * 100,
            'currency': checkout_draft.get('currency') or 'INR',
            'receipt': receipt,
            'notes': {
                'email': checkout_draft['email'][:100],
                'phone': checkout_draft['phone'][:30],
            },
        }
        razorpay_order = razorpay_client.order.create(data=order_payload)
    except RuntimeError:
        app.logger.exception('Razorpay credentials are missing')
        return jsonify({'success': False, 'message': 'Payment gateway is not configured right now.'}), 503
    except Exception:
        app.logger.exception('Razorpay order creation failed')
        return jsonify({'success': False, 'message': GENERIC_ERROR_MESSAGE}), 502

    session['pending_checkout'] = {
        'razorpay_order_id': razorpay_order.get('id'),
        'amount_paise': int(razorpay_order.get('amount') or 0),
        'draft': checkout_draft,
    }
    session.modified = True

    return jsonify({
        'success': True,
        'key_id': get_razorpay_key_id(),
        'razorpay_order_id': razorpay_order.get('id'),
        'amount_paise': int(razorpay_order.get('amount') or 0),
        'currency': razorpay_order.get('currency') or checkout_draft.get('currency') or 'INR',
        'summary': {
            'subtotal': checkout_draft['subtotal'],
            'shipping_fee': checkout_draft['shipping_fee'],
            'discount_amount': checkout_draft['discount_amount'],
            'total': checkout_draft['total_amount'],
        },
    }), 200


@app.route('/api/payment/verify', methods=['POST'])
def verify_payment():
    data = request.get_json() or {}
    razorpay_order_id = str(data.get('razorpay_order_id') or '').strip()
    razorpay_payment_id = str(data.get('razorpay_payment_id') or '').strip()
    razorpay_signature = str(data.get('razorpay_signature') or '').strip()

    if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        return jsonify({'success': False, 'message': 'Payment verification payload is incomplete.'}), 400

    pending_checkout = session.get('pending_checkout') or {}
    if pending_checkout.get('razorpay_order_id') != razorpay_order_id:
        return jsonify({'success': False, 'message': 'Checkout session expired. Please try again.'}), 400

    try:
        razorpay_client = get_razorpay_client()
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })
    except RuntimeError:
        app.logger.exception('Razorpay credentials are missing during verification')
        return jsonify({'success': False, 'message': 'Payment gateway is not configured right now.'}), 503
    except Exception:
        app.logger.exception('Razorpay signature verification failed')
        return jsonify({'success': False, 'message': 'Payment verification failed.'}), 400

    checkout_draft = pending_checkout.get('draft') or {}

    try:
        finalized_order = finalize_checkout_order(
            checkout_draft,
            payment_context={
                'payment_id': razorpay_payment_id,
                'order_id': razorpay_order_id,
                'amount_paise': pending_checkout.get('amount_paise'),
            },
        )
        db.session.commit()
    except CheckoutError as exc:
        db.session.rollback()
        refund_result = issue_payment_refund(
            razorpay_client,
            razorpay_payment_id,
            pending_checkout.get('amount_paise'),
            exc.message,
        )
        session.pop('pending_checkout', None)
        session.modified = True
        return jsonify({
            'success': False,
            'message': exc.message,
            'error_code': exc.error_code,
            'refund_initiated': refund_result.get('success', False),
            'refund_id': refund_result.get('refund_id'),
            'refund_status': refund_result.get('status'),
        }), exc.status_code
    except Exception:
        db.session.rollback()
        app.logger.exception('Order finalization after payment failed')
        refund_result = issue_payment_refund(
            razorpay_client,
            razorpay_payment_id,
            pending_checkout.get('amount_paise'),
            'Unexpected checkout finalization failure',
        )
        session.pop('pending_checkout', None)
        session.modified = True
        return jsonify({
            'success': False,
            'message': GENERIC_ERROR_MESSAGE,
            'refund_initiated': refund_result.get('success', False),
            'refund_id': refund_result.get('refund_id'),
            'refund_status': refund_result.get('status'),
        }), 500

    session.pop('pending_checkout', None)
    session['last_order_id'] = finalized_order['order_record'].order_code
    session.modified = True

    return jsonify({
        'success': True,
        'message': 'Payment verified and order placed successfully.',
        'order': serialize_order(finalized_order['order_record']),
        'success_url': url_for('order_success', order_id=finalized_order['order_record'].order_code),
        'subtotal': finalized_order['subtotal'],
        'shipping_fee': finalized_order['shipping_fee'],
        'discount_amount': finalized_order['discount_amount'],
        'discount_code': finalized_order['discount_code'],
        'total': finalized_order['total_amount'],
        'remaining_stock': finalized_order['remaining_stock'],
    }), 200


@app.route('/api/orders/place', methods=['POST'])
def place_order():
    try:
        data = request.get_json() or {}
        checkout_draft = build_checkout_draft(data)
        finalized_order = finalize_checkout_order(checkout_draft)
        finalized_order['order_record'].payment_status = 'Paid'
        finalized_order['order_record'].paid_at = datetime.utcnow()
        db.session.commit()
        session['last_order_id'] = finalized_order['order_record'].order_code
        session.modified = True
        return jsonify({
            'success': True,
            'order': serialize_order(finalized_order['order_record']),
            'success_url': url_for('order_success', order_id=finalized_order['order_record'].order_code),
            'subtotal': finalized_order['subtotal'],
            'shipping_fee': finalized_order['shipping_fee'],
            'discount_amount': finalized_order['discount_amount'],
            'discount_code': finalized_order['discount_code'],
            'total': finalized_order['total_amount'],
            'remaining_stock': finalized_order['remaining_stock'],
        }), 201
    except CheckoutError as exc:
        db.session.rollback()
        return jsonify({'success': False, 'message': exc.message, 'error_code': exc.error_code}), exc.status_code
    except Exception:
        db.session.rollback()
        app.logger.exception('Order placement failed')
        return jsonify({'success': False, 'message': GENERIC_ERROR_MESSAGE}), 500


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
    app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')

