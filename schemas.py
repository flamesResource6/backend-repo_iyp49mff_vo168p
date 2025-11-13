"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogpost" collection
- ContactMessage -> "contactmessage" collection
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

# ------------------------
# Auth/User Schema
# ------------------------
class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    password_hash: str = Field(..., description="Hashed password with salt")
    password_salt: str = Field(..., description="Per-user salt used for hashing")
    avatar_url: Optional[str] = Field(None, description="Profile avatar URL")
    role: str = Field("user", description="Role of the user: user/admin")
    sessions: List[dict] = Field(default_factory=list, description="Active sessions with tokens and timestamps")
    is_active: bool = Field(True, description="Whether user is active")

# ------------------------
# Blog Schema
# ------------------------
class BlogPost(BaseModel):
    title: str = Field(..., description="Post title")
    slug: str = Field(..., description="URL-friendly slug")
    excerpt: Optional[str] = Field(None, description="Short summary")
    content: str = Field(..., description="Markdown or HTML content")
    author_name: Optional[str] = Field(None, description="Author display name")
    tags: List[str] = Field(default_factory=list, description="Tags for filtering")
    published: bool = Field(True, description="Publication status")
    published_at: datetime = Field(default_factory=datetime.utcnow, description="Publication timestamp")

# ------------------------
# Contact Form Schema
# ------------------------
class ContactMessage(BaseModel):
    name: str = Field(..., description="Sender name")
    email: EmailStr = Field(..., description="Sender email")
    message: str = Field(..., description="Message body")
    status: str = Field("new", description="new | read | archived")
