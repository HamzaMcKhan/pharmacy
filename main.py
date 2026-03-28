from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
from pathlib import Path
import os

from openai import OpenAI

app = FastAPI(title="The Pharmacy Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_NAME = "gpt-4.1-mini"
DATA_FILE = Path("data/products.json")

PURPOSE_KEYWORDS = {
    "immunity": ["immunity", "immune", "immune support", "cold", "flu", "defence", "defense"],
    "joints": ["joint", "joints", "mobility", "stiffness", "glucosamine"],
    "sleep": ["sleep", "bed", "bedtime", "rest", "wind down", "calm at night", "insomnia"],
    "stress": ["stress", "stressed", "calm", "anxiety", "adaptogen", "resilience", "relax"],
    "gut_health": ["gut", "digestion", "digestive", "bloating", "probiotic", "stomach"],
    "heart_health": ["heart", "cardio", "cholesterol", "omega", "fish oil"],
    "energy": ["energy", "tired", "fatigue", "focus", "b12", "iron"],
    "beauty": ["skin", "hair", "nails", "beauty", "glow", "collagen"],
    "muscle_recovery": ["muscle", "recovery", "cramps", "tension", "magnesium"]
}


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    matched_product: Optional[str] = None


def load_products():
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def money(value: float) -> str:
    return f"${value:.2f}"


def normalize_text(text: str) -> str:
    return (text or "").lower().strip()


def find_best_sale(products):
    sale_products = [p for p in products if p["on_sale"]]
    if not sale_products:
        return None
    return max(sale_products, key=lambda p: p["rrp"] - p["current_price"])


def detect_product_type(message: str):
    msg = normalize_text(message)

    if any(word in msg for word in ["fragrance", "perfume", "cologne", "scent"]):
        return "fragrance"

    if any(word in msg for word in ["vitamin", "supplement", "magnesium", "gummies", "fish oil", "collagen", "probiotic"]):
        return "vitamin"

    return None


def detect_gender(message: str):
    msg = normalize_text(message)

    if any(word in msg for word in ["women", "woman", "female", "ladies"]):
        return "women"

    if any(word in msg for word in ["men", "man", "male", "gents"]):
        return "men"

    if "unisex" in msg:
        return "unisex"

    return None


def detect_sale_only(message: str):
    msg = normalize_text(message)
    return any(word in msg for word in ["sale", "deal", "discount", "cheapest", "best price", "on sale"])


def detect_purpose(message: str):
    msg = normalize_text(message)

    for purpose, keywords in PURPOSE_KEYWORDS.items():
        if any(keyword in msg for keyword in keywords):
            return purpose

    return None


def product_matches_purpose(product: dict, purpose: str) -> bool:
    if not purpose:
        return True

    searchable_text = " ".join([
        normalize_text(product.get("name")),
        normalize_text(product.get("general_info")),
        normalize_text(product.get("ingredients")),
        normalize_text(product.get("directions")),
        normalize_text(product.get("warnings"))
    ])

    for keyword in PURPOSE_KEYWORDS.get(purpose, []):
        if keyword in searchable_text:
            return True

    return False


def filter_products(message: str, products: list):
    product_type = detect_product_type(message)
    gender = detect_gender(message)
    sale_only = detect_sale_only(message)
    purpose = detect_purpose(message)

    filtered = products

    if product_type:
        filtered = [p for p in filtered if p["type"] == product_type]

    if gender:
        filtered = [p for p in filtered if p["gender"] == gender]

    if sale_only:
        filtered = [p for p in filtered if p["on_sale"]]

    if purpose:
        filtered = [p for p in filtered if product_matches_purpose(p, purpose)]

    return filtered


def find_product_mentioned(message: str, products: list):
    msg = normalize_text(message)

    for product in products:
        if normalize_text(product["product_id"]) in msg:
            return product

    for product in products:
        name_words = normalize_text(product["name"]).split()
        key_words = [word for word in name_words[:4] if len(word) > 2]
        if key_words and any(word in msg for word in key_words):
            return product

    return None


def build_structured_context(user_message: str, products: list):
    msg = normalize_text(user_message)

    if len(msg) > 300:
        return {
            "mode": "too_long",
            "matched_product": None,
            "payload": {
                "message": "User message too long for this demo."
            }
        }

    if "best deal" in msg or "biggest discount" in msg:
        best = find_best_sale(products)
        if best:
            saving = best["rrp"] - best["current_price"]
            return {
                "mode": "best_deal",
                "matched_product": best["name"],
                "payload": {
                    "product": best,
                    "saving": round(saving, 2)
                }
            }

    if "store hour" in msg or "open" in msg or "closing time" in msg:
        return {
            "mode": "store_hours",
            "matched_product": None,
            "payload": {
                "message": "For this prototype, store hours are not connected to live branch data yet."
            }
        }

    mentioned_product = find_product_mentioned(msg, products)

    if "ingredients" in msg and mentioned_product:
        return {
            "mode": "ingredients",
            "matched_product": mentioned_product["name"],
            "payload": {"product": mentioned_product}
        }

    if ("directions" in msg or "how do i use" in msg) and mentioned_product:
        return {
            "mode": "directions",
            "matched_product": mentioned_product["name"],
            "payload": {"product": mentioned_product}
        }

    if ("warning" in msg or "warnings" in msg) and mentioned_product:
        return {
            "mode": "warnings",
            "matched_product": mentioned_product["name"],
            "payload": {"product": mentioned_product}
        }

    filtered = filter_products(msg, products)

    if filtered:
        return {
            "mode": "product_list",
            "matched_product": filtered[0]["name"],
            "payload": {
                "products": filtered[:3],
                "purpose": detect_purpose(msg),
                "product_type": detect_product_type(msg),
                "gender": detect_gender(msg),
                "sale_only": detect_sale_only(msg)
            }
        }

    return {
        "mode": "fallback",
        "matched_product": None,
        "payload": {
            "message": "No confident product match found.",
            "purpose": detect_purpose(msg),
            "product_type": detect_product_type(msg),
            "gender": detect_gender(msg)
        }
    }


def build_prompt(user_message: str, context: dict) -> str:
    return f"""
You are a helpful online retail pharmacy assistant for a fictional website called "The Pharmacy".

Rules:
- Be concise, polished, and customer-friendly.
- Only use the information provided below.
- Do not invent products, ingredients, warnings, prices, discounts, store hours, or medical claims.
- If information is not available, say so clearly.
- Keep answers short enough for a website chat widget.
- If the user asks for a category like immunity, joints, sleep, stress, gut health, heart health, energy, beauty, or muscle recovery, recommend only from the structured context.
- Sound professional, helpful, and natural.

User question:
{user_message}

Structured context:
{json.dumps(context, indent=2)}
""".strip()


def call_llm(user_message: str, context: dict) -> str:
    prompt = build_prompt(user_message, context)

    response = client.responses.create(
        model=MODEL_NAME,
        input=prompt,
        max_output_tokens=180
    )

    return response.output_text.strip()


def fallback_answer(user_message: str, context: dict) -> str:
    mode = context["mode"]
    payload = context["payload"]

    if mode == "too_long":
        return "Please keep your question shorter for this demo."

    if mode == "best_deal":
        product = payload["product"]
        saving = payload["saving"]
        return (
            f"The best current deal is {product['name']} at {money(product['current_price'])}, "
            f"down from {money(product['rrp'])}. That saves {money(saving)}."
        )

    if mode == "store_hours":
        return (
            "Prototype answer: store hours would normally come from live store data. "
            "For this demo, the assistant would direct customers to store details or help them after hours."
        )

    if mode == "ingredients":
        product = payload["product"]
        return f"Ingredients for {product['name']}: {product['ingredients']}"

    if mode == "directions":
        product = payload["product"]
        return f"Directions for {product['name']}: {product['directions']}"

    if mode == "warnings":
        product = payload["product"]
        warning_text = product.get("warnings") or "No specific warnings listed for this product."
        return f"Warnings for {product['name']}: {warning_text}"

    if mode == "product_list":
        lines = []
        for product in payload["products"]:
            sale_text = "On sale" if product["on_sale"] else "Regular price"
            lines.append(f"{product['name']} — {money(product['current_price'])} ({sale_text})")

        purpose = payload.get("purpose")
        if purpose:
            return "Here are some matching options for that need:\n" + "\n".join(lines)

        return "Here are some matching products:\n" + "\n".join(lines)

    return (
        "I could not confidently match that yet. Try asking about fragrances, vitamins, immunity, joints, sleep, "
        "stress, gut health, heart health, ingredients, directions, or warnings."
    )


def answer_question(message: str) -> ChatResponse:
    products = load_products()
    context = build_structured_context(message, products)

    if context["mode"] == "too_long":
        return ChatResponse(
            reply="Please keep your question shorter for this demo."
        )

    try:
        reply = call_llm(message, context)
    except Exception as error:
        print(f"LLM error: {error}")
        reply = fallback_answer(message, context)

    return ChatResponse(
        reply=reply,
        matched_product=context.get("matched_product")
    )


@app.get("/")
def root():
    return {"message": "The Pharmacy Chat API is running."}


@app.get("/products")
def get_products():
    return load_products()


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    return answer_question(request.message)