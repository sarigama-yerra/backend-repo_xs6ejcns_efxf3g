import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="Shopping AI Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Utils ----------
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


def to_public(doc: Dict[str, Any]):
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    # Convert nested ObjectIds if any
    for k, v in list(d.items()):
        if isinstance(v, ObjectId):
            d[k] = str(v)
    return d


# ---------- Schemas ----------
class CreateSession(BaseModel):
    title: str

class MessageIn(BaseModel):
    session_id: str
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str
    meta: Optional[Dict[str, Any]] = None

class WishlistIn(BaseModel):
    product_id: str
    user_email: Optional[str] = None

class CartIn(BaseModel):
    product_id: str
    quantity: int = 1
    user_email: Optional[str] = None


# ---------- Seed Data ----------
import random

def seed_products():
    if db is None:
        return
    if db["product"].count_documents({}) > 0:
        return

    categories = ["Laptops", "Headphones", "Smart Home", "Fitness", "Photography"]
    sample_features = [
        ["Lightweight", "All-day battery", "Retina display"],
        ["Noise-cancelling", "Bluetooth 5.3", "30h battery"],
        ["Matter-ready", "Voice control", "Energy saver"],
        ["GPS", "Heart-rate", "Waterproof"],
        ["4K video", "Stabilization", "Fast autofocus"],
    ]

    for i in range(18):
        cat = random.choice(categories)
        price = round(random.uniform(39, 1999), 2)
        rating = round(random.uniform(3.9, 4.9), 1)
        features = random.choice(sample_features)
        retailers = [
            {"name": "Amazon", "price": price, "url": "https://amazon.com"},
            {"name": "BestBuy", "price": round(price * random.uniform(0.95, 1.05), 2), "url": "https://bestbuy.com"},
            {"name": "Walmart", "price": round(price * random.uniform(0.9, 1.1), 2), "url": "https://walmart.com"},
        ]
        p = {
            "title": f"Product {i+1} {cat}",
            "description": f"Premium {cat.lower()} item with modern features.",
            "price": price,
            "category": cat,
            "in_stock": True,
            "image": f"https://picsum.photos/seed/{i+341}/600/400",
            "rating": rating,
            "features": features,
            "retailers": retailers,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        db["product"].insert_one(p)

    # Seed price history per product
    products = list(db["product"].find())
    now = datetime.utcnow()
    for p in products:
        history = []
        base = p.get("price", 100.0)
        for d in range(30):
            day = now - timedelta(days=29 - d)
            delta = random.uniform(-0.05, 0.05)
            base = max(5, round(base * (1 + delta), 2))
            history.append({"date": day, "price": base})
        db["pricehistory"].insert_one({"product_id": p["_id"], "history": history})


seed_products()

# ---------- Basic ----------
@app.get("/")
def root():
    return {"message": "Shopping AI Assistant API"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available" if db is None else "✅ Connected",
        "collections": []
    }
    if db is not None:
        try:
            response["collections"] = db.list_collection_names()
        except Exception as e:
            response["database"] = f"⚠️ Error {str(e)[:80]}"
    return response

# ---------- Sessions & Messages ----------
@app.post("/api/sessions")
def create_session(payload: CreateSession):
    if db is None:
        raise HTTPException(500, "Database not configured")
    doc = {
        "title": payload.title,
        "created_at": datetime.utcnow(),
    }
    _id = db["chatsession"].insert_one(doc).inserted_id
    return {"id": str(_id), **doc}

@app.get("/api/sessions")
def list_sessions(limit: int = 20):
    if db is None:
        return []
    items = list(db["chatsession"].find().sort("created_at", -1).limit(limit))
    return [to_public(i) for i in items]

@app.get("/api/sessions/recent")
def recent_sessions(limit: int = 7):
    return list_sessions(limit)

@app.get("/api/sessions/{session_id}/messages")
def get_messages(session_id: str):
    if db is None:
        return []
    items = list(db["message"].find({"session_id": session_id}).sort("created_at", 1))
    return [to_public(i) for i in items]

@app.post("/api/messages")
def post_message(msg: MessageIn):
    if db is None:
        raise HTTPException(500, "Database not configured")
    doc = {
        "session_id": msg.session_id,
        "role": msg.role,
        "content": msg.content,
        "meta": msg.meta or {},
        "created_at": datetime.utcnow(),
    }
    db["message"].insert_one(doc)
    return {"status": "ok"}

# ---------- Products & Discovery ----------
@app.get("/api/products/search")
def search_products(q: str = Query(""), limit: int = 20):
    if db is None:
        return []
    query = {"$or": [
        {"title": {"$regex": q, "$options": "i"}},
        {"description": {"$regex": q, "$options": "i"}},
        {"category": {"$regex": q, "$options": "i"}},
    ]} if q else {}
    items = list(db["product"].find(query).limit(limit))
    return [to_public(i) for i in items]

@app.get("/api/products/trending")
def trending_products(limit: int = 8):
    if db is None:
        return []
    items = list(db["product"].find().sort("rating", -1).limit(limit))
    return [to_public(i) for i in items]

@app.get("/api/products/essentials")
def essentials_products(limit: int = 8):
    if db is None:
        return []
    items = list(db["product"].find().sort("price", 1).limit(limit))
    return [to_public(i) for i in items]

@app.get("/api/products/favorites")
def favorites_products(limit: int = 8):
    if db is None:
        return []
    # Mock favorites by sorting by recent created_at desc
    items = list(db["product"].find().sort("created_at", -1).limit(limit))
    return [to_public(i) for i in items]

@app.get("/api/products/{product_id}/price-history")
def price_history(product_id: str):
    if db is None:
        return {"history": []}
    rec = db["pricehistory"].find_one({"product_id": ObjectId(product_id)})
    if not rec:
        return {"history": []}
    hist = [{"date": h["date"].isoformat(), "price": h["price"]} for h in rec.get("history", [])]
    return {"history": hist}

# ---------- Wishlist & Cart ----------
@app.post("/api/wishlist")
def add_wishlist(item: WishlistIn):
    if db is None:
        raise HTTPException(500, "Database not configured")
    doc = {
        "product_id": ObjectId(item.product_id),
        "user_email": item.user_email,
        "created_at": datetime.utcnow(),
    }
    db["wishlist"].insert_one(doc)
    return {"status": "added"}

@app.delete("/api/wishlist/{product_id}")
def remove_wishlist(product_id: str):
    if db is None:
        raise HTTPException(500, "Database not configured")
    db["wishlist"].delete_many({"product_id": ObjectId(product_id)})
    return {"status": "removed"}

@app.post("/api/cart")
def add_cart(item: CartIn):
    if db is None:
        raise HTTPException(500, "Database not configured")
    doc = {
        "product_id": ObjectId(item.product_id),
        "quantity": item.quantity,
        "user_email": item.user_email,
        "created_at": datetime.utcnow(),
    }
    db["cart"].insert_one(doc)
    return {"status": "added"}

# ---------- AI-like Chat Assist ----------
@app.post("/api/chat")
def chat(session_id: str, query: str):
    """Simple heuristic recommendation + comparison.
    Returns: assistant message, suggested products, comparison fields, why recommended.
    """
    if db is None:
        raise HTTPException(500, "Database not configured")

    # store user message
    db["message"].insert_one({
        "session_id": session_id,
        "role": "user",
        "content": query,
        "created_at": datetime.utcnow(),
    })

    # Basic parsing: look for category and budget
    import re
    budget = None
    m = re.search(r"\$(\d{2,5})", query.replace(",", ""))
    if m:
        budget = float(m.group(1))

    # Keyword search
    q = query
    items = list(db["product"].find({"$or": [
        {"title": {"$regex": q, "$options": "i"}},
        {"description": {"$regex": q, "$options": "i"}},
        {"category": {"$regex": q, "$options": "i"}},
    ]}).limit(8))

    if not items:
        items = list(db["product"].find().sort("rating", -1).limit(5))

    if budget:
        under = [p for p in items if p.get("price", 0) <= budget]
        items = under or items

    # Choose top 3 for comparison
    recs = items[:3]

    reasons = []
    if budget:
        reasons.append(f"Fits your budget around ${int(budget)}")
    if recs:
        cats = {p.get("category") for p in recs}
        reasons.append(f"Popular picks in {', '.join(cats)} with strong ratings")

    assistant_text = (
        "Here are a few options I think you'll like. I've compared core specs, pricing across retailers, and highlighted why each stands out."
    )

    # store assistant message
    db["message"].insert_one({
        "session_id": session_id,
        "role": "assistant",
        "content": assistant_text,
        "meta": {"recommendations": [str(p["_id"]) for p in recs], "reasons": reasons},
        "created_at": datetime.utcnow(),
    })

    return {
        "message": assistant_text,
        "reasons": reasons,
        "products": [to_public(p) for p in recs],
        "compare_on": ["price", "rating", "key_features"],
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
