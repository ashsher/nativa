"""
app/routers/auth.py — Authentication endpoints.

Exposes POST /api/auth/validate which accepts a Telegram WebApp InitData
string, validates its HMAC-SHA256 signature, upserts the user in the database,
and returns the full user profile.

This is the only public endpoint — all others require a valid InitData token
via AuthMiddleware.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User, UserLanguage
from app.schemas.user import UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_response(user: User) -> UserResponse:
    """
    Build a fully materialized UserResponse to avoid async lazy-load at serialize time.
    """
    languages = []
    for ul in (user.languages or []):
        lang = ul.language
        if not lang:
            continue
        languages.append(
            {
                "user_language_id": ul.user_language_id,
                "language_id": ul.language_id,
                "code": lang.code,
                "name_en": lang.name_en,
                "name_uz": lang.name_uz,
                "is_active": ul.is_active,
            }
        )

    return UserResponse(
        user_id=user.user_id,
        telegram_id=user.telegram_id,
        first_name=user.first_name,
        username=user.username,
        city=user.city,
        country=user.country,
        interests=user.interests,
        hobbies=user.hobbies,
        is_premium=user.is_premium,
        premium_expires_at=user.premium_expires_at,
        created_at=user.created_at,
        languages=languages,
    )


@router.post(
    "/validate",
    response_model=UserResponse,
    summary="Telegram InitData ni tasdiqlash va foydalanuvchini ro'yxatdan o'tkazish",
)
async def validate(
    init_data: str = Body(..., embed=True, description="Telegram WebApp initData string"),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Validate a Telegram WebApp InitData payload and upsert the user.

    Steps:
      1. Call auth_service.validate_init_data() to verify the HMAC signature
         and extract the Telegram user dict.
      2. Call auth_service.upsert_user() to create or update the user row in DB.
      3. Load the user's language enrolments for the response.
      4. Return the full UserResponse.

    Raises:
        401 if the InitData signature is invalid or the auth_date is too old.
    """
    # --- Step 1: Validate signature and extract Telegram user data ---
    telegram_user = auth_service.validate_init_data(init_data)

    # --- Step 2: Create or update user in the database ---
    user = await auth_service.upsert_user(db, telegram_user)

    # --- Step 3: Re-query with eager loading to avoid MissingGreenlet ---
    result = await db.execute(
        select(User)
        .options(selectinload(User.languages).selectinload(UserLanguage.language))
        .where(User.user_id == user.user_id)
    )
    user_loaded = result.scalar_one()

    # --- Step 4: Return fully materialized response ---
    return _to_user_response(user_loaded)
