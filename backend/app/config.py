"""
app/config.py — centralised application configuration.

All values are loaded from environment variables (or a .env file).
Never hard-code secrets; rely entirely on this module throughout the project.
"""

from __future__ import annotations

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings resolved from environment variables."""

    model_config = SettingsConfigDict(
        # Automatically load a .env file from the working directory if present.
        env_file=".env",
        env_file_encoding="utf-8",
        # Allow extra fields without raising validation errors (useful during dev).
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    DATABASE_URL: str = Field(
        ...,
        description=(
            "Async PostgreSQL connection string used by SQLAlchemy. "
            "Must use the 'postgresql+asyncpg' scheme, e.g. "
            "postgresql+asyncpg://user:pass@host:5432/dbname"
        ),
    )

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description=(
            "Redis connection URL used for caching translations, TTS URLs, "
            "daily quota counters, and general key-value storage."
        ),
    )

    # -------------------------------------------------------------------------
    # Telegram
    # -------------------------------------------------------------------------
    TELEGRAM_BOT_TOKEN: str = Field(
        ...,
        description=(
            "Secret token obtained from @BotFather. "
            "Used to validate Telegram WebApp InitData via HMAC-SHA256."
        ),
    )

    # -------------------------------------------------------------------------
    # Google / Gemini
    # -------------------------------------------------------------------------
    GOOGLE_API_KEY: str = Field(
        ...,
        description=(
            "Google Cloud API key that enables Cloud Translation and "
            "Cloud Text-to-Speech services."
        ),
    )

    GEMINI_API_KEY: str = Field(
        ...,
        description=(
            "API key for Google Generative AI (Gemini 1.5 Flash). "
            "Used by the AI grammar explanation service."
        ),
    )

    YOUTUBE_API_KEY: str = Field(
        ...,
        description=(
            "YouTube Data API v3 key. Used to fetch video metadata "
            "(title, duration) when processing YouTube URLs."
        ),
    )

    # -------------------------------------------------------------------------
    # Firebase
    # -------------------------------------------------------------------------
    FIREBASE_CREDENTIALS: str = Field(
        ...,
        description=(
            "Absolute path to the Firebase Admin SDK service-account JSON file. "
            "Used to initialise Firestore for real-time speaking-match signalling."
        ),
    )

    # -------------------------------------------------------------------------
    # Cloudflare R2 (S3-compatible object storage)
    # -------------------------------------------------------------------------
    R2_ACCOUNT_ID: str = Field(
        ...,
        description="Cloudflare account ID — forms part of the R2 endpoint URL.",
    )

    R2_ACCESS_KEY_ID: str = Field(
        ...,
        description="R2 API token access key ID (S3-compatible credential).",
    )

    R2_SECRET_ACCESS_KEY: str = Field(
        ...,
        description="R2 API token secret access key (S3-compatible credential).",
    )

    R2_BUCKET_NAME: str = Field(
        ...,
        description="Name of the R2 bucket where TTS audio files are stored.",
    )

    R2_PUBLIC_URL: str = Field(
        ...,
        description=(
            "Public base URL for the R2 bucket, e.g. https://cdn.example.com. "
            "Returned to clients so they can play audio directly."
        ),
    )

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    SECRET_KEY: str = Field(
        ...,
        description=(
            "Random secret used for signing internal tokens or any future "
            "session-based auth. Generate with: openssl rand -hex 32"
        ),
    )

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    CORS_ORIGINS: List[str] = Field(
        default=["https://web.telegram.org"],
        description=(
            "List of allowed CORS origins. Telegram WebApp runs inside "
            "web.telegram.org, so that origin is whitelisted by default. "
            "Add your custom frontend domain in production."
        ),
    )


# Module-level singleton — import this throughout the project.
settings = Settings()
