"""
app/routers/speaking.py — Speaking-partner matching endpoints.

GET  /api/speaking/matches  — Return ranked list of partner candidates.
POST /api/speaking/connect  — Create a match and return a Telegram deep-link.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.speaking import (
    SpeakingConnectRequest,
    SpeakingConnectResponse,
    SpeakingMatchResponse,
)
from app.services import speaking_service

router = APIRouter(prefix="/speaking", tags=["speaking"])


async def _get_user(request: Request, db: AsyncSession) -> User:
    """Load the full User ORM object for the authenticated request."""
    telegram_id: int = request.state.user["id"]
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        from app.services import auth_service
        user = await auth_service.upsert_user(db, request.state.user)
    return user


@router.get(
    "/matches",
    response_model=List[SpeakingMatchResponse],
    summary="Mos nutq mashqi sheriklari ro'yxatini olish",
)
async def get_matches(
    request: Request,
    language_id: int = Query(..., description="O'rganilayotgan til IDsi"),
    db: AsyncSession = Depends(get_db),
) -> List[SpeakingMatchResponse]:
    """
    Return the top 10 speaking partner candidates for the authenticated user.

    Matching algorithm: Jaccard similarity over combined interests + hobbies.
    Only users currently learning the same language are considered.

    Returns results sorted by similarity score descending (best match first).
    """
    user = await _get_user(request, db)

    matches = await speaking_service.get_matches(
        current_user=user,
        language_id=language_id,
        db=db,
    )

    return matches  # type: ignore[return-value]


@router.post(
    "/connect",
    response_model=SpeakingConnectResponse,
    summary="Nutq mashqi sherigi bilan bog'lanish",
)
async def connect(
    payload: SpeakingConnectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SpeakingConnectResponse:
    """
    Initiate a speaking-partner connection with the chosen user.

    Steps:
      1. Enforce daily speaking_count quota (free: 5/day, premium: unlimited).
      2. Load the partner user record.
      3. Create a SpeakingMatch DB record.
      4. Write a Firebase Firestore signalling document for WebRTC setup.
      5. Return the Telegram deep-link and Firestore doc ID.

    Raises:
        404 if the chosen partner user does not exist.
        429 if the free-tier speaking quota has been exceeded.
    """
    user = await _get_user(request, db)

    result = await speaking_service.connect(
        initiator=user,
        partner_user_id=payload.partner_user_id,
        language_id=payload.language_id,
        is_premium=user.is_premium,
        db=db,
    )

    return result  # type: ignore[return-value]
