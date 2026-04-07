"""
app/routers/reading.py — Article reading and word translation endpoints.

POST /api/reading/process  — Process a URL or plain text into tokenised paragraphs.
GET  /api/reading/translate — Translate a single word with Redis cache.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.reading import ReadingProcessRequest, ReadingProcessResponse
from app.services import reading_service, translation_service

router = APIRouter(prefix="/reading", tags=["reading"])


async def _get_user_id(request: Request, db: AsyncSession) -> int:
    """Resolve the internal user_id from the authenticated Telegram user."""
    telegram_id: int = request.state.user["id"]
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        from app.services import auth_service
        user = await auth_service.upsert_user(db, request.state.user)
    return user.user_id


@router.post(
    "/process",
    response_model=ReadingProcessResponse,
    summary="Maqola yoki matnni tokenizatsiya qilish",
)
async def process_reading(
    payload: ReadingProcessRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ReadingProcessResponse:
    """
    Process an article URL or plain text and return tokenised paragraphs.

    If *content* starts with 'http://' or 'https://', the service fetches
    and parses the page HTML.  Otherwise it treats the value as plain text.

    Steps:
      1. Fetch and parse HTML (if URL) or use plain text directly.
      2. Strip navigation, headers, footers, and scripts.
      3. Split into paragraphs and tokenise each one.
      4. Persist a ReadingSession.
      5. Return structured response.
    """
    user_id = await _get_user_id(request, db)

    result = await reading_service.process_reading(
        content=payload.content,
        language_id=payload.language_id,
        user_id=user_id,
        db=db,
    )

    return result  # type: ignore[return-value]


@router.get(
    "/translate",
    summary="Bitta so'zni tarjima qilish (keshli)",
)
async def translate_word(
    word: str = Query(..., min_length=1, max_length=200, description="Tarjima qilinadigan so'z"),
    lang_code: str = Query(default="en", max_length=10, description="So'z tili kodi (ISO 639-1)"),
) -> dict:
    """
    Translate a single word from the target language to Uzbek.

    Results are cached in Redis for 7 days to minimise Google Translate API costs.
    The response also includes a pronunciation audio URL and example sentences.

    Returns:
        Dict with keys: word, translation, pronunciation_url, examples.
    """
    # Delegate to the translation service which handles cache + API call.
    result = await translation_service.translate_word(word=word, lang_code=lang_code)
    return result
