"""
app/routers/vocabulary.py — Vocabulary deck and SRS review endpoints.

GET    /api/vocabulary/          — Return the user's full vocabulary deck.
POST   /api/vocabulary/          — Add a new word to the deck.
DELETE /api/vocabulary/{vocab_id} — Remove a word from the deck.
GET    /api/vocabulary/review    — Get cards due for review today.
POST   /api/vocabulary/review    — Submit an SM-2 recall rating.
"""

from __future__ import annotations

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.vocabulary import UserVocabulary
from app.schemas.vocabulary import (
    SRSReviewRequest,
    SRSReviewResponse,
    VocabularyCreate,
    VocabularyResponse,
)
from app.services import srs_service, translation_service

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _get_user(request: Request, db: AsyncSession) -> User:
    """Load the full User ORM object for the authenticated request."""
    telegram_id: int = request.state.user["id"]
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        from app.services import auth_service
        user = await auth_service.upsert_user(db, request.state.user)
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=List[VocabularyResponse],
    summary="Foydalanuvchining barcha lug'at kartochkalarini olish",
)
async def get_vocabulary(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> List[VocabularyResponse]:
    """
    Return all vocabulary cards in the authenticated user's deck.

    Ordered by most recently added (highest vocab_id) first.
    """
    user = await _get_user(request, db)

    result = await db.execute(
        select(UserVocabulary)
        .where(UserVocabulary.user_id == user.user_id)
        .order_by(UserVocabulary.vocab_id.desc())
    )
    cards = list(result.scalars().all())
    return cards  # type: ignore[return-value]


@router.post(
    "/",
    response_model=VocabularyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Lug'atga yangi so'z qo'shish",
)
async def add_word(
    payload: VocabularyCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> VocabularyResponse:
    """
    Add a new vocabulary card to the user's deck.

    Also triggers async TTS pronunciation generation in the background
    by delegating to the translation service (which calls tts_service).
    The pronunciation_url may be null on the first request and populated
    on subsequent fetches once TTS has finished.
    """
    user = await _get_user(request, db)

    # Enrich the card with pronunciation URL via translation service.
    # If translation/TTS fails we still create the card - pronunciation_url stays null.
    translation_data = {}
    try:
        translation_data = await translation_service.translate_word(
            word=payload.word,
            lang_code="en",  # Default; caller can specify a different language.
        )
    except Exception:
        translation_data = {}

    card = UserVocabulary(
        user_id=user.user_id,
        language_id=payload.language_id,
        word=payload.word.lower(),
        translation=payload.translation,
        pronunciation_url=translation_data.get("pronunciation_url"),
        example_sentences=payload.example_sentences,
    )
    db.add(card)
    await db.flush()

    return card  # type: ignore[return-value]


@router.delete(
    "/{vocab_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Lug'atdan so'zni o'chirish",
)
async def delete_word(
    vocab_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Remove a vocabulary card from the user's deck.

    Only the owning user can delete their own cards.  Returns 404 if the
    card does not exist or belongs to a different user.
    """
    user = await _get_user(request, db)

    result = await db.execute(
        select(UserVocabulary).where(
            UserVocabulary.vocab_id == vocab_id,
            UserVocabulary.user_id == user.user_id,
        )
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kartochka topilmadi.",
        )

    await db.delete(card)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/review",
    response_model=List[VocabularyResponse],
    summary="Bugun takrorlanishi kerak bo'lgan kartochkalarni olish",
)
async def get_due_cards(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> List[VocabularyResponse]:
    """
    Return all vocabulary cards due for review today or earlier.

    Cards are considered due when next_review_date <= today.
    Results are ordered by next_review_date ascending (oldest due first).
    """
    user = await _get_user(request, db)
    today = date.today()

    result = await db.execute(
        select(UserVocabulary)
        .where(
            UserVocabulary.user_id == user.user_id,
            UserVocabulary.next_review_date <= today,
        )
        .order_by(UserVocabulary.next_review_date.asc())
    )
    due_cards = list(result.scalars().all())
    return due_cards  # type: ignore[return-value]


@router.post(
    "/review",
    response_model=SRSReviewResponse,
    summary="SM-2 baholash natijasini yuborish",
)
async def submit_review(
    payload: SRSReviewRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SRSReviewResponse:
    """
    Submit a recall quality rating (0–5) for a vocabulary card.

    The SM-2 algorithm updates the card's interval, ease factor, and
    next review date based on the supplied rating.  Daily SRS quota is
    enforced via quota_service (free users: 10 reviews/day).
    """
    user = await _get_user(request, db)

    # Apply the SM-2 algorithm and persist the result.
    updated_card = await srs_service.review(
        vocab_id=payload.vocab_id,
        rating=payload.rating,
        user_id=user.user_id,
        is_premium=user.is_premium,
        db=db,
    )

    # Build a human-readable feedback message in Uzbek.
    if payload.rating >= 4:
        message = "Zo'r! Kartochka yaxshi eslab qolindi. 🎉"
    elif payload.rating >= 2:
        message = "Yaxshi! Davom eting. 👍"
    else:
        message = "Xavotir olmang, yana bir marta ko'ring. 💪"

    return SRSReviewResponse(
        vocab=updated_card,  # type: ignore[arg-type]
        message=message,
    )
