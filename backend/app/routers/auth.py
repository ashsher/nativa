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
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


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

    # --- Step 3 & 4: Eagerly load languages and return the user ---
    # SQLAlchemy lazy-loads relationships by default; we need to access them
    # within the session context to avoid DetachedInstanceError.
    await db.refresh(user, attribute_names=["languages"])
    for ul in user.languages:
        # Touch the language FK so it is loaded before the session closes.
        _ = ul.language

    return user  # type: ignore[return-value]
