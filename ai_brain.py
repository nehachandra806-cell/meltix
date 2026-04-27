from flask import current_app, url_for
import json
import re

try:
    from litellm import completion as litellm_completion
except ModuleNotFoundError:
    litellm_completion = None


AI_BRAIN_EXTENSION_KEY = "meltix_ai_brain"
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
BOT_TOOLS = [
    {
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
    },
    {
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
    },
    {
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
    }
]
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
    "acha", "achha", "are", "arre", "bata", "batao", "batau", "bhai", "bhaiya", "bolo", "chaiye",
    "chahiye", "dekh", "dekhna", "dena", "hona", "hoon", "hu", "kafi", "kaisa", "kaise", "kar",
    "karna", "karo", "koi", "kr", "krna", "krta", "krte", "kya", "kyu", "kyun", "lena", "mai",
    "main", "mera", "mere", "mood", "mujhe", "nhi", "nahi", "pasand", "raha", "rha", "sahi",
    "samjha", "suno", "tha", "thoda", "toh", "tum", "tumhe", "wala", "wali", "yar", "yaar"
)
BOT_CONTEXT_LABELS = {
    "shop": "main shop",
    "hidden-message": "Hidden Message collection page",
    "story-candle": "Story Candle collection page",
    "zodiac-candle": "Zodiac Candle collection page",
    "break-to-reveal": "Break to Reveal collection page",
    "candle-date-kit": "Candle Date Kit collection page",
}
BOT_REDIRECT_DESTINATIONS = [
    {"keywords": ("hidden message", "hidden-message", "hidden"), "endpoint": "hidden_message", "label": "Hidden Message"},
    {"keywords": ("story candle", "story-candle", "story"), "endpoint": "story_candle", "label": "Story Candle"},
    {"keywords": ("zodiac candle", "zodiac-candle", "zodiac"), "endpoint": "zodiac_candle", "label": "Zodiac Candle"},
    {"keywords": ("break to reveal", "break-to-reveal", "break reveal", "treasure hunt", "stress buster"), "endpoint": "break_to_reveal", "label": "Break to Reveal"},
    {"keywords": ("candle date kit", "candle-date-kit", "date kit", "date night"), "endpoint": "candle_date_kit", "label": "Candle Date Kit"},
    {"keywords": ("shop", "collections", "browse"), "endpoint": "shop", "label": "Shop"},
    {"keywords": ("gift sets", "gift set", "gifts"), "endpoint": "gift_sets", "label": "Gift Sets"},
    {"keywords": ("profile", "account", "my profile"), "endpoint": "profile", "label": "Profile"},
    {"keywords": ("cart", "bag", "basket", "checkout bag"), "endpoint": "shop", "label": "Cart", "query": {"open_cart": "1"}},
    {"keywords": ("meltix studio", "craft studio", "studio"), "endpoint": "craft_studio", "label": "Meltix Studio"},
    {"keywords": ("suggestions", "suggestion", "recommendations", "recommendation"), "endpoint": "suggestions", "label": "Suggestions"},
    {"keywords": ("another section", "head to", "navigation"), "endpoint": "head_to", "label": "Another Section"},
    {"keywords": ("feedback", "review page"), "endpoint": "feedback", "label": "Feedback"},
    {"keywords": ("bug report", "bug", "issue"), "endpoint": "bug_report", "label": "Bug Report"},
]


def configure_ai_brain(app, *, find_products, build_product_card, normalize_catalog_category):
    app.extensions[AI_BRAIN_EXTENSION_KEY] = {
        "find_products": find_products,
        "build_product_card": build_product_card,
        "normalize_catalog_category": normalize_catalog_category,
    }


def _get_services():
    services = current_app.extensions.get(AI_BRAIN_EXTENSION_KEY)
    if not services:
        raise RuntimeError("AI brain has not been configured.")
    return services


def _normalize_max_price(value):
    try:
        return max(0, int(value or 100000))
    except (TypeError, ValueError):
        return 100000


def normalize_bot_history(raw_history):
    if not isinstance(raw_history, list):
        return []

    normalized = []
    for entry in raw_history[-BOT_MAX_HISTORY:]:
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(entry.get("text") or entry.get("content") or "").strip()
        if not content:
            continue
        normalized.append({"role": role, "content": content[:3000]})
    return normalized[-BOT_MAX_HISTORY:]


def search_store_products(search_term="", max_price=100000):
    services = _get_services()
    clean_term = str(search_term or "").strip()
    if not clean_term:
        return "System info: Search term missing."

    normalized_max_price = _normalize_max_price(max_price)

    try:
        products = services["find_products"](
            search_term=clean_term,
            max_price=normalized_max_price,
            limit=5,
        )
    except Exception as exc:
        current_app.logger.warning("Bot product search failed: %s", exc)
        return f"Database Error: {exc}"

    if not products:
        return f"System info: No products found for '{clean_term}' under INR {normalized_max_price}."

    result_lines = ["Items found in database:"]
    for product in products:
        result_lines.append(
            f"- {product.name} | {product.collection_label} | {product.group_name} (Price: INR {max(0, int(product.price or 0))})"
        )
    return "\n".join(result_lines)


def suggest_product_card(search_term="", max_price=100000):
    services = _get_services()
    normalized_max_price = _normalize_max_price(max_price)

    try:
        products = services["find_products"](
            search_term=str(search_term or "").strip(),
            max_price=normalized_max_price,
            limit=1,
        )
    except Exception as exc:
        current_app.logger.warning("Bot product card search failed: %s", exc)
        return f"Database Error: {exc}", None

    product = products[0] if products else None
    if not product:
        return "No suitable product card found for that request.", None

    tool_text = (
        f"Suggested product card ready: {product.name} | {product.collection_label} | "
        f"{product.group_name or product.collection_slug}"
    )
    return tool_text, services["build_product_card"](product)


def resolve_bot_redirect(destination):
    services = _get_services()
    clean_destination = str(destination or "").strip().lower()
    if not clean_destination:
        return None

    for target in BOT_REDIRECT_DESTINATIONS:
        if any(keyword in clean_destination for keyword in target["keywords"]):
            endpoint = target["endpoint"]
            query = target.get("query") or {}
            return {
                "label": target["label"],
                "redirect_url": url_for(endpoint, **query),
            }

    normalized_category = services["normalize_catalog_category"](clean_destination)
    if normalized_category:
        endpoint_map = {
            "hidden-message": "hidden_message",
            "story-candle": "story_candle",
            "zodiac-candle": "zodiac_candle",
            "break-to-reveal": "break_to_reveal",
            "candle-date-kit": "candle_date_kit",
            "gift-sets": "gift_sets",
        }
        endpoint_name = endpoint_map.get(normalized_category)
        if endpoint_name:
            return {
                "label": normalized_category.replace("-", " ").title(),
                "redirect_url": url_for(endpoint_name),
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
    opener = ""
    for entry in prior_history:
        if entry.get("role") == "user" and entry.get("content"):
            opener = str(entry.get("content") or "").strip()
            if opener:
                break
    if not opener:
        opener = str(user_message or "").strip()

    if re.search(r"[\u0900-\u097F]", opener):
        return "hindi"

    words = re.findall(r"[a-z]+", opener.lower())
    if any(word in BOT_ROMAN_HINDI_MARKERS for word in words):
        return "hinglish"

    return "english"


def build_bot_system_prompt(prior_history, user_message, bot_context):
    language_style = detect_bot_language_style(prior_history, user_message)
    context_label = BOT_CONTEXT_LABELS.get(str(bot_context or "").strip().lower(), "general browsing")
    return (
        f"{BOT_SYSTEM_PROMPT}\n\n"
        f"[SESSION LOCK]\n"
        f"- The user started in {language_style}. Reply only in {language_style} unless the user clearly switches.\n"
        f"- Current page context: {context_label}.\n"
        f"- Your first goal in this session is to move the user toward a product, recommendation, budget, or collection choice."
    )


def get_bot_static_message(language_style, key):
    language = str(language_style or "english").strip().lower()
    copy = {
        "busy": {
            "english": "Meltix Bot is busy right now. Try again in a moment.",
            "hinglish": "Meltix Bot abhi busy hai. Thodi der mein phir try karo.",
            "hindi": "मेल्टिक्स बॉट अभी व्यस्त है। थोड़ी देर में फिर कोशिश करें।",
        },
        "empty": {
            "english": "Welcome. Looking for a gift, a candle, or a quick suggestion?",
            "hinglish": "Welcome. Gift, candle, ya quick suggestion chahiye?",
            "hindi": "स्वागत है। गिफ्ट, कैंडल, या कोई quick suggestion चाहिए?",
        }
    }
    return copy.get(key, {}).get(language) or copy.get(key, {}).get("english", "")


def finalize_bot_reply(raw_text, language_style, fallback_key="empty"):
    text = re.sub(r"\s+", " ", str(raw_text or "")).strip()
    if not text:
        text = get_bot_static_message(language_style, fallback_key)

    parts = [part.strip() for part in re.split(r"(?<=[.!?\u0964])\s+|\n+", text) if part.strip()]
    concise = " ".join(parts[:3]) if parts else text

    if len(concise) > 260:
        concise = concise[:257].rsplit(" ", 1)[0].rstrip(" ,;:-") + "..."

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
                current_app.logger.warning(
                    "%s returned malformed tool-call text instead of structured tool_calls.",
                    model,
                )
                continue
            return response, model
        except Exception as exc:
            current_app.logger.warning("Bot model %s failed: %s", model, exc)
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


def generate_bot_response(user_message, page_context, history=None):
    try:
        _get_services()
    except RuntimeError as exc:
        current_app.logger.warning("AI brain unavailable: %s", exc)
        return {
            "success": False,
            "message": "Meltix Bot is unavailable right now. Please try again shortly.",
            "_status": 503,
        }

    prior_history = normalize_bot_history(history)
    bot_context = str(page_context or "general").strip().lower()
    language_style = detect_bot_language_style(prior_history, user_message)
    system_prompt = build_bot_system_prompt(prior_history, user_message, bot_context)
    messages = [{"role": "system", "content": system_prompt}] + prior_history + [{
        "role": "user",
        "content": str(user_message or "")[:3000],
    }]

    ai_response, used_model = get_bot_completion(messages, use_tools=True)
    if not ai_response:
        return {
            "success": False,
            "message": get_bot_static_message(language_style, "busy"),
            "_status": 503,
        }

    response_message = ai_response.choices[0].message
    reply_text = (response_message.content or "").strip()
    product_card = None
    redirect_url = None

    if getattr(response_message, "tool_calls", None):
        followup_messages = messages + [
            make_bot_assistant_message(reply_text, getattr(response_message, "tool_calls", None))
        ]

        for tool_call in response_message.tool_calls:
            tool_name = str(tool_call.function.name or "").strip()
            tool_args = parse_bot_tool_arguments(tool_call.function.arguments)
            tool_output = "Tool unavailable."

            if tool_name == "search_store_products":
                tool_output = search_store_products(
                    search_term=tool_args.get("search_term", ""),
                    max_price=tool_args.get("max_price", 100000),
                )
            elif tool_name == "suggest_product_card":
                tool_output, suggested_card = suggest_product_card(
                    search_term=tool_args.get("search_term", ""),
                    max_price=tool_args.get("max_price", 100000),
                )
                if suggested_card:
                    product_card = suggested_card
            elif tool_name == "redirect_user":
                tool_output, redirect_payload = redirect_user(
                    destination=tool_args.get("destination", ""),
                )
                if redirect_payload:
                    redirect_url = redirect_payload.get("redirect_url")

            followup_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": tool_output,
            })

        final_response, final_model = get_bot_completion(followup_messages, use_tools=False)
        final_text = finalize_bot_reply(
            ((final_response.choices[0].message.content or "").strip()) if final_response else reply_text,
            language_style,
        )

        return {
            "success": True,
            "reply": final_text,
            "product_card": product_card,
            "redirect_url": redirect_url,
            "model": final_model or used_model,
            "used_tool": True,
            "_status": 200,
        }

    return {
        "success": True,
        "reply": finalize_bot_reply(reply_text, language_style),
        "product_card": None,
        "redirect_url": None,
        "model": used_model,
        "used_tool": False,
        "_status": 200,
    }
