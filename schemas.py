"""
Database Schemas

Pydantic models that map to MongoDB collections. Each class name lowercased
is used as the collection name.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

class User(BaseModel):
    name: str = Field(...)
    email: str = Field(...)
    address: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=120)
    is_active: bool = True

class ProductRetailer(BaseModel):
    name: str
    price: float
    url: Optional[str] = None

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
    image: Optional[str] = None
    rating: Optional[float] = Field(4.5, ge=0, le=5)
    features: Optional[List[str]] = []
    retailers: Optional[List[ProductRetailer]] = []

class ChatSession(BaseModel):
    title: str
    created_at: Optional[datetime] = None

class Message(BaseModel):
    session_id: str
    role: str = Field(..., description="user or assistant")
    content: str
    meta: Optional[Dict] = None

class WishlistItem(BaseModel):
    user_email: Optional[str] = None
    product_id: str

class CartItem(BaseModel):
    user_email: Optional[str] = None
    product_id: str
    quantity: int = 1
