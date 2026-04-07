"""
app/schemas/user.py — Pydantic request/response schemas for User endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    """
    Data required to create a new user.  Normally populated from Telegram
    InitData rather than from a direct API call.
    """

    # Telegram user ID — 64-bit integer, unique per Telegram account.
    telegram_id: int = Field(..., description="Telegram user ID")

    # User's first name as set in Telegram (optional — some accounts lack it).
    first_name: Optional[str] = Field(None, max_length=100)

    # Telegram @username without the leading '@' sign.
    username: Optional[str] = Field(None, max_length=100)


class UserUpdate(BaseModel):
    """
    Fields the user can update from their profile settings screen.
    All fields are optional — only supplied fields are updated.
    """

    # Self-reported city name used for speaking-partner discovery.
    city: Optional[str] = Field(None, max_length=100)

    # ISO 3166-1 alpha-2 country code or plain country name.
    country: Optional[str] = Field(None, max_length=100)

    # List of interest tags selected by the user (e.g. ["music", "travel"]).
    interests: Optional[List[str]] = Field(None)

    # List of hobby tags selected by the user (e.g. ["chess", "cooking"]).
    hobbies: Optional[List[str]] = Field(None)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class UserLanguageResponse(BaseModel):
    """Represents a language the user is currently studying."""

    # Internal primary key of the UserLanguage row.
    user_language_id: int

    # Internal primary key of the Language.
    language_id: int

    # ISO 639-1 code of the language (e.g. "en").
    code: str

    # English name of the language (e.g. "English").
    name_en: str

    # Uzbek name of the language (e.g. "Ingliz tili").
    name_uz: str

    # Whether this language enrolment is currently active.
    is_active: bool

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Full user profile returned by GET /api/users/me."""

    # Internal user ID.
    user_id: int

    # Telegram user ID.
    telegram_id: int

    # Display name from Telegram.
    first_name: Optional[str] = None

    # Telegram @username.
    username: Optional[str] = None

    # Self-reported city.
    city: Optional[str] = None

    # Self-reported country.
    country: Optional[str] = None

    # List of interest tags.
    interests: Optional[List[str]] = None

    # List of hobby tags.
    hobbies: Optional[List[str]] = None

    # Whether the user has an active premium subscription.
    is_premium: bool

    # When the premium subscription expires (null for free users).
    premium_expires_at: Optional[datetime] = None

    # When the account was created.
    created_at: datetime

    # Languages the user is studying.
    languages: List[UserLanguageResponse] = []

    class Config:
        from_attributes = True
