"""
app/services/auth_service.py — Telegram WebApp InitData validation and user upsert.

Telegram signs the `initData` query string that is passed to every WebApp
with an HMAC-SHA256 signature.  We re-derive the signature server-side and
compare it to the hash embedded in the data to confirm authenticity.

Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict
from urllib.parse import parse_qsl, unquote

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.language import Language
from app.models.user import User
from app.models.user import UserLanguage


async def _ensure_default_language(db: AsyncSession) -> Language:
    """
    Ensure at least one active default language exists and return it.

    Uses English ("en") as the bootstrap language because the current app
    defaults most processing pipelines to English content.
    """
    result = await db.execute(select(Language).where(Language.code == "en"))
    language = result.scalar_one_or_none()
    if language is not None:
        return language

    language = Language(
        code="en",
        name_en="English",
        name_uz="Ingliz tili",
        is_active=True,
    )
    db.add(language)
    await db.flush()
    return language


async def _ensure_user_language(db: AsyncSession, user: User) -> None:
    """
    Ensure user has at least one active language enrollment.
    """
    result = await db.execute(
        select(UserLanguage).where(
            UserLanguage.user_id == user.user_id,
            UserLanguage.is_active == True,  # noqa: E712
        )
    )
    active = result.scalar_one_or_none()
    if active is not None:
        return

    default_language = await _ensure_default_language(db)
    db.add(
        UserLanguage(
            user_id=user.user_id,
            language_id=default_language.language_id,
            is_active=True,
        )
    )
    await db.flush()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_init_data(init_data: str) -> Dict[str, Any]:
    """
    Validate Telegram WebApp InitData and return the decoded user payload.

    Steps (per official Telegram documentation):
      1. Parse the URL-encoded query string into key-value pairs.
      2. Extract and remove the 'hash' field — that is the signature we check.
      3. Sort the remaining key=value pairs alphabetically by key.
      4. Join them with a newline character to form data_check_string.
      5. Derive the secret key: HMAC-SHA256(key=b"WebAppData", msg=BOT_TOKEN).
      6. Compute expected_hash: HMAC-SHA256(key=secret_key, msg=data_check_string).
      7. Compare expected_hash with the received hash using constant-time compare.
      8. Verify auth_date is no older than 24 hours to prevent replay attacks.
      9. Parse the 'user' JSON string and return it.

    Raises:
        HTTPException 401 if the signature is invalid or the data is too old.
    """
    # --- Step 1: Parse query string into a dict ---
    # parse_qsl preserves duplicate keys but Telegram's initData has unique keys.
    params: Dict[str, str] = dict(parse_qsl(init_data, keep_blank_values=True))

    # --- Step 2: Extract hash before signing ---
    received_hash = params.pop("hash", None)
    if received_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram ma'lumotlarida imzo (hash) yo'q.",
        )

    # --- Step 3 & 4: Build the data-check string ---
    # Sort keys alphabetically, format each as "key=value", join with '\n'.
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )

    # --- Step 5: Derive secret key ---
    # HMAC(key="WebAppData", message=BOT_TOKEN) — note: key is a literal string.
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=settings.TELEGRAM_BOT_TOKEN.encode(),
        digestmod=hashlib.sha256,
    ).digest()

    # --- Step 6: Compute expected hash ---
    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    # --- Step 7: Constant-time comparison to prevent timing attacks ---
    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram ma'lumotlari noto'g'ri. Iltimos, qaytadan urinib ko'ring.",
        )

    # --- Step 8: Check auth_date freshness (max 24 hours = 86400 seconds) ---
    auth_date = int(params.get("auth_date", 0))
    if time.time() - auth_date > 86_400:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessiya muddati tugagan. Iltimos, ilovani qayta oching.",
        )

    # --- Step 9: Decode and return the user object ---
    user_json = params.get("user", "{}")
    try:
        user_data = json.loads(unquote(user_json))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Foydalanuvchi ma'lumotlari noto'g'ri formatda.",
        )

    return user_data


# ---------------------------------------------------------------------------
# User upsert
# ---------------------------------------------------------------------------

async def upsert_user(db: AsyncSession, telegram_user: Dict[str, Any]) -> User:
    """
    Create a new User or update an existing one from Telegram user data.

    Telegram provides: id, first_name, username, language_code, is_premium, etc.

    Args:
        db:            Async database session.
        telegram_user: Dict parsed from the 'user' field of Telegram InitData.

    Returns:
        The persisted User ORM object (either newly created or updated).
    """
    telegram_id: int = telegram_user["id"]

    # --- Look up existing user by Telegram ID ---
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user: User | None = result.scalar_one_or_none()

    if user is None:
        # --- Create new user ---
        user = User(
            telegram_id=telegram_id,
            first_name=telegram_user.get("first_name"),
            username=telegram_user.get("username"),
            # Telegram sends is_premium=True for Premium subscribers.
            is_premium=telegram_user.get("is_premium", False),
        )
        db.add(user)
        # Flush so the PK is populated before we return.
        await db.flush()
    else:
        # --- Update mutable fields that may change between sessions ---
        user.first_name = telegram_user.get("first_name", user.first_name)
        user.username = telegram_user.get("username", user.username)
        # Note: we only promote to premium here; demotion happens via
        # payment_service when a subscription expires.
        if telegram_user.get("is_premium"):
            user.is_premium = True

    # Ensure every authenticated user has at least one active learning language.
    await _ensure_user_language(db, user)

    return user
