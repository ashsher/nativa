"""
app/routers/ai.py — AI grammar explanation endpoint.

POST /api/ai/explain — Submit text, receive a Gemini-generated Uzbek explanation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.ai import AIExplainRequest, AIExplainResponse
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["ai"])


async def _get_user(request: Request, db: AsyncSession) -> User:
    """Load the full User ORM object for the authenticated request."""
    telegram_id: int = request.state.user["id"]
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        from app.services import auth_service
        user = await auth_service.upsert_user(db, request.state.user)
    return user


@router.post(
    "/explain",
    response_model=AIExplainResponse,
    summary="So'z yoki iborani o'zbek tilida grammatik tushuntirish",
)
async def explain(
    payload: AIExplainRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AIExplainResponse:
    """
    Generate a Gemini 1.5 Flash grammar explanation in Uzbek.

    The explanation covers:
      - Grammatical category (noun, verb, adjective, etc.)
      - Core meaning
      - Usage example (English + Uzbek translation)
      - Optional additional notes

    Daily quota: free users get 10 AI explanations per day.
    Premium users have unlimited access.

    Raises:
        429 if the free-tier daily AI quota has been exceeded.
        502 if the Gemini API returns an error.
    """
    # Load the authenticated user so we can check premium status.
    user = await _get_user(request, db)

    # Delegate to the AI service layer.
    explanation, token_count = await ai_service.explain(
        text=payload.text,
        context=payload.context,
        language_code=payload.language_code,
        user_id=user.user_id,
        is_premium=user.is_premium,
        db=db,
    )

    return AIExplainResponse(
        explanation=explanation,
        token_count=token_count,
    )
