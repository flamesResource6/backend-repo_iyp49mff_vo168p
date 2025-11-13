import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

from database import db, create_document, get_documents
from schemas import User, BlogPost, ContactMessage

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------
# Helpers for simple token auth (no external deps)
# ------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-dev-key")
TOKEN_TTL_MINUTES = 60 * 24


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), password_hash)


# ------------------------
# Schemas for requests
# ------------------------
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    token: str
    user: dict


class CreatePostRequest(BaseModel):
    title: str
    content: str
    tags: Optional[List[str]] = []
    author_name: Optional[str] = None


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    message: str


# ------------------------
# Utility functions
# ------------------------

def collection(name: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    return db[name]


def generate_token() -> str:
    return secrets.token_urlsafe(32)


# ------------------------
# Public routes
# ------------------------
@app.get("/")
def root():
    return {"ok": True, "service": "SaaS API"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected"
            response["collections"] = db.list_collection_names()[:10]
    except Exception as e:
        response["database"] = f"⚠️  Error: {str(e)[:120]}"
    return response


# ------------------------
# Auth endpoints (email+password, token stored server-side)
# ------------------------
@app.post("/auth/signup", response_model=TokenResponse)
def signup(payload: SignupRequest):
    users = list(collection("user").find({"email": payload.email}))
    if users:
        raise HTTPException(status_code=400, detail="Email already registered")

    salt = secrets.token_hex(16)
    pwd_hash = hash_password(payload.password, salt)

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=pwd_hash,
        password_salt=salt,
        role="user",
        sessions=[],
        is_active=True,
    )
    user_id = create_document("user", user)

    token = generate_token()
    session = {
        "token": token,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES),
    }
    collection("user").update_one({"_id": collection("user").find_one({"_id": {"$eq": collection("user").find_one({"email": payload.email})["_id"]}})["_id"]}, {"$push": {"sessions": session}})

    user_doc = collection("user").find_one({"email": payload.email})
    user_doc["_id"] = str(user_doc["_id"])  # serialize
    return {"token": token, "user": {k: v for k, v in user_doc.items() if k != "password_hash" and k != "password_salt"}}


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    user = collection("user").find_one({"email": payload.email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user.get("password_salt", ""), user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = generate_token()
    session = {
        "token": token,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES),
    }
    collection("user").update_one({"_id": user["_id"]}, {"$push": {"sessions": session}})

    user["_id"] = str(user["_id"])  # serialize
    return {"token": token, "user": {k: v for k, v in user.items() if k != "password_hash" and k != "password_salt"}}


# ------------------------
# Blog endpoints
# ------------------------
@app.get("/blog", response_model=List[dict])
def list_posts():
    posts = list(collection("blogpost").find({"published": True}).sort("published_at", -1))
    for p in posts:
        p["_id"] = str(p["_id"])  # serialize
    return posts


@app.post("/blog", response_model=dict)
def create_post(payload: CreatePostRequest):
    slug = payload.title.lower().strip().replace(" ", "-")
    post = BlogPost(
        title=payload.title,
        slug=slug,
        excerpt=(payload.content[:160] + "...") if len(payload.content) > 160 else payload.content,
        content=payload.content,
        author_name=payload.author_name or "Team",
        tags=payload.tags or [],
        published=True,
    )
    post_id = create_document("blogpost", post)
    doc = collection("blogpost").find_one({"_id": {"$eq": collection("blogpost").find_one({"_id": {"$eq": post_id}})}})
    return {"id": post_id}


# ------------------------
# Contact form
# ------------------------
@app.post("/contact", response_model=dict)
def submit_contact(payload: ContactRequest):
    msg = ContactMessage(name=payload.name, email=payload.email, message=payload.message)
    msg_id = create_document("contactmessage", msg)
    return {"id": msg_id, "ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
