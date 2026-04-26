"""
app/models/user.py — User and UserLanguage ORM models.

User is the central entity in Nativa.  UserLanguage is a join table that
tracks which languages a user is actively studying.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    """
    Represents a Telegram WebApp user.

    Table name: users
    """

    __tablename__ = "users"

    # Auto-incremented internal primary key.
    user_id = Column(Integer, primary_key=True, autoincrement=True)

    # Telegram user ID — unique and never changes; used as external identifier.
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)

    # Telegram first name — may be null if the user has no first name set.
    first_name = Column(String(100), nullable=True)

    # Telegram @username — nullable because not all accounts have one.
    username = Column(String(100), nullable=True)

    # Self-reported city for the speaking-match feature (geolocation fallback).
    city = Column(String(100), nullable=True)

    # Self-reported country code (ISO 3166-1 alpha-2 recommended).
    country = Column(String(100), nullable=True)

    # PostgreSQL native array of free-text interest tags, e.g. ["music","travel"].
    interests = Column(ARRAY(Text), nullable=True, default=list)

    # PostgreSQL native array of free-text hobby tags, e.g. ["chess","cooking"].
    hobbies = Column(ARRAY(Text), nullable=True, default=list)

    # Whether the user appears in other users' speaking-partner search results.
    # Set to False for users who prefer not to be contacted.
    is_discoverable = Column(Boolean, default=True, nullable=False)

    # Whether the user currently holds an active premium subscription.
    is_premium = Column(Boolean, default=False, nullable=False)

    # UTC timestamp when the premium subscription expires; null for free users.
    premium_expires_at = Column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Account creation timestamp — set automatically by the DB server.
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    # Languages the user is studying.
    languages = relationship(
        "UserLanguage", back_populates="user", cascade="all, delete-orphan"
    )

    # Vocabulary cards belonging to this user.
    vocabulary = relationship(
        "UserVocabulary", back_populates="user", cascade="all, delete-orphan"
    )

    # YouTube video study sessions.
    video_sessions = relationship(
        "VideoSession", back_populates="user", cascade="all, delete-orphan"
    )

    # Article reading sessions.
    reading_sessions = relationship(
        "ReadingSession", back_populates="user", cascade="all, delete-orphan"
    )

    # AI grammar explanation queries.
    ai_queries = relationship(
        "AIQuery", back_populates="user", cascade="all, delete-orphan"
    )

    # Daily usage quota records.
    usage_quotas = relationship(
        "UsageQuota", back_populates="user", cascade="all, delete-orphan"
    )

    # Payment / subscription records.
    payments = relationship(
        "Payment", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User telegram_id={self.telegram_id} username={self.username}>"


class UserLanguage(Base):
    """
    Join table tracking which language(s) a user is studying.

    Table name: user_languages
    """

    __tablename__ = "user_languages"

    # Auto-incremented primary key for this enrolment record.
    user_language_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key back to the user.
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Foreign key to the language being studied.
    language_id = Column(
        Integer,
        ForeignKey("languages.language_id", ondelete="RESTRICT"),
        nullable=False,
    )

    # When the user started studying this language.
    started_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Allows a user to pause a language without losing their history.
    is_active = Column(Boolean, default=True, nullable=False)

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user = relationship("User", back_populates="languages")
    language = relationship("Language")

    def __repr__(self) -> str:
        return (
            f"<UserLanguage user_id={self.user_id} "
            f"language_id={self.language_id}>"
        )
