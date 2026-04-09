"""
app/services/ai_service.py - Gemini-powered grammar explanation service.

Generates Uzbek grammar explanations and logs each query.
"""

from __future__ import annotations

import logging
from typing import Tuple

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ai_query import AIQuery
from app.services import quota_service

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
Siz ingliz tili o'qituvchisisiz. Quyidagi so'z yoki iborani o'zbek tilida \
tushunarli va qisqa tarzda tushuntiring.

So'z/ibora: "{text}"
{context_line}

Quyidagilarni o'z ichiga olgan tushuntirish bering:
1. Grammatik tur (ot, fe'l, sifat, ravish va h.k.)
2. Asosiy ma'nosi
3. Qo'llanish misoli (inglizcha + o'zbekcha tarjimasi)
4. Qo'shimcha foydali ma'lumot (ixtiyoriy)

Javobni faqat o'zbek tilida bering. Qisqa va tushunarli yozing.
"""


def _build_prompt(text: str, context: str, language_code: str) -> str:
    """
    Render the prompt template with user input.
    """
    _ = language_code
    context_line = f'Kontekst jumlasi: "{context}"' if context.strip() else ""
    return _PROMPT_TEMPLATE.format(text=text, context_line=context_line)


def _candidate_models(genai) -> list[str]:
    """
    Resolve an ordered list of model IDs that support generateContent.
    """
    preferred = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
    ]

    configured = getattr(settings, "GEMINI_MODEL", None)
    candidates: list[str] = []
    if configured:
        candidates.append(configured)
    candidates.extend(preferred)

    try:
        available: list[str] = []
        for m in genai.list_models():
            methods = getattr(m, "supported_generation_methods", []) or []
            if "generateContent" not in methods:
                continue
            name = getattr(m, "name", "") or ""
            if name.startswith("models/"):
                name = name.split("/", 1)[1]
            if name:
                available.append(name)

        if not available:
            return list(dict.fromkeys(candidates))

        ordered = [c for c in candidates if c in available]
        ordered.extend([a for a in available if "flash" in a and a not in ordered])
        ordered.extend([a for a in available if a not in ordered])
        return ordered
    except Exception as exc:
        logger.warning("Could not enumerate Gemini models, using fallback list: %s", exc)
        return list(dict.fromkeys(candidates))


async def explain(
    text: str,
    context: str,
    language_code: str,
    user_id: int,
    is_premium: bool,
    db: AsyncSession,
) -> Tuple[str, int]:
    """
    Generate a grammar explanation for text in Uzbek.
    """
    await quota_service.check_and_increment(user_id, "ai_count", is_premium)

    prompt = _build_prompt(text, context, language_code)

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)

        response = None
        chosen_model = None
        last_exc: Exception | None = None

        for model_name in _candidate_models(genai):
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                chosen_model = model_name
                break
            except Exception as exc:
                last_exc = exc
                continue

        if response is None:
            raise last_exc or RuntimeError("No compatible Gemini model available.")

        logger.info("AI explanation generated with model: %s", chosen_model)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI xizmati bilan bog'liq xato: {exc}",
        )

    explanation: str = response.text or ""
    token_count: int = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        token_count = getattr(response.usage_metadata, "total_token_count", 0) or 0

    query_log = AIQuery(
        user_id=user_id,
        input_text=text,
        response_text=explanation,
        token_count=token_count,
    )
    db.add(query_log)
    await db.flush()

    return explanation, token_count
