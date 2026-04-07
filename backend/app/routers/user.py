"""
app/routers/user.py — User profile endpoints.

GET  /api/users/me  — Return the current user's full profile.
PUT  /api/users/me  — Update the current user's profile fields.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["users"])


async def _get_current_user(
    request: Request, db: AsyncSession
) -> User:
    """
    Dependency helper that loads the full User ORM object from the database
    using the Telegram user ID stored in request.state.user by AuthMiddleware.
    """
    # The middleware attaches a dict with at least {"id": <telegram_id>}.
    telegram_id: int = request.state.user["id"]

    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        # The user passed auth but doesn't exist yet — create them.
        user = await auth_service.upsert_user(db, request.state.user)

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
    """
    Return the full profile for the currently authenticated user.

    The user is identified via the Telegram ID in request.state.user,
    which was populated by AuthMiddleware.
    """
    # Load the user from DB.
    user = await _get_current_user(request, db)

    # Eagerly load language enrolments within the session context.
    await db.refresh(user, attribute_names=["languages"])
    for ul in user.languages:
        _ = ul.language

    return user  # type: ignore[return-value]


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
    """
    Update mutable profile fields: city, country, interests, hobbies.

    Only fields included in the request body are updated (partial update).
    """
    # Load the user.
    user = await _get_current_user(request, db)

    # Apply only the fields that were explicitly provided in the payload.
    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    # Flush to DB (commit happens in get_db dependency).
    await db.flush()

    # Reload relationships for the response.
    await db.refresh(user, attribute_names=["languages"])
    for ul in user.languages:
        _ = ul.language

    return user  # type: ignore[return-value]
