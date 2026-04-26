"""
app/routers/user.py - User profile endpoints.

GET  /api/users/me  - Return the current user's full profile.
PUT  /api/users/me  - Update the current user's profile fields.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User, UserLanguage
from app.schemas.user import UserResponse, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["users"])


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


async def _get_current_user(request: Request, db: AsyncSession) -> User:
    """
    Load the full User ORM object from DB using authenticated Telegram ID.
    """
    telegram_id: int = request.state.user["id"]

    result = await db.execute(
        select(User)
        .options(selectinload(User.languages).selectinload(UserLanguage.language))
        .where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = await auth_service.upsert_user(db, request.state.user)
        result = await db.execute(
            select(User)
            .options(selectinload(User.languages).selectinload(UserLanguage.language))
            .where(User.user_id == user.user_id)
        )
        user = result.scalar_one()

    return user


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Joriy foydalanuvchi profilini olish",
)
async def get_me(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await _get_current_user(request, db)
    return _to_user_response(user)


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Foydalanuvchi profilini yangilash",
)
async def update_me(
    payload: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await _get_current_user(request, db)

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()

    result = await db.execute(
        select(User)
        .options(selectinload(User.languages).selectinload(UserLanguage.language))
        .where(User.user_id == user.user_id)
    )
    user_loaded = result.scalar_one()

    return _to_user_response(user_loaded)
