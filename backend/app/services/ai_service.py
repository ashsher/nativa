"""
app/services/ai_service.py — Gemini-powered grammar explanation service.

Sends user-submitted text to Gemini 1.5 Flash with an Uzbek-language prompt
that asks for a clear, beginner-friendly grammatical explanation.  Logs each
query to the AIQuery table and enforces daily usage quotas via quota_service.
"""

from __future__ import annotations

from typing import Tuple

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ai_query import AIQuery
from app.services import quota_service

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------
# The prompt is written in Uzbek so the explanation is returned in Uzbek
# without any extra instructions needed.
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
    Render the prompt template with the user's input.

    Args:
        text:          Word or phrase to explain.
        context:       Optional surrounding sentence for context.
        language_code: Language code (included for future multilingual support).

    Returns:
        Formatted prompt string.
    """
    context_line = f'Kontekst jumlasi: "{context}"' if context.strip() else ""
    return _PROMPT_TEMPLATE.format(text=text, context_line=context_line)


async def explain(
    text: str,
    context: str,
    language_code: str,
    user_id: int,
    is_premium: bool,
    db: AsyncSession,
) -> Tuple[str, int]:
    """
    Generate a Gemini grammar explanation for *text* in Uzbek.

    Steps:
      1. Enforce daily AI quota via quota_service.
      2. Build the Uzbek-language prompt.
      3. Call Gemini 1.5 Flash via google-generativeai.
      4. Extract explanation text and token count from the response.
      5. Log the query to the AIQuery table.
      6. Return (explanation_text, token_count).

    Args:
        text:          Input text to explain.
        context:       Optional context sentence.
        language_code: ISO 639-1 code of the target language.
        user_id:       Internal user ID for quota and logging.
        is_premium:    Whether the user has an active premium subscription.
        db:            Async database session.

    Returns:
        Tuple of (explanation string, total token count).
    """
    # --- Step 1: Check and increment daily AI quota ---
    await quota_service.check_and_increment(user_id, "ai_count", is_premium)

    # --- Step 2: Build prompt ---
    prompt = _build_prompt(text, context, language_code)

    # --- Step 3: Call Gemini 1.5 Flash ---
    try:
        import google.generativeai as genai

        # Configure the SDK with the API key from settings.
        genai.configure(api_key=settings.GEMINI_API_KEY)

        # Use Gemini 1.5 Flash — fast and cost-effective for short explanations.
        model = genai.GenerativeModel("gemini-1.5-flash")

        response = model.generate_content(prompt)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI xizmati bilan bog'liq xato: {exc}",
        )

    # --- Step 4: Extract explanation and token count ---
    explanation: str = response.text or ""
    # usage_metadata may be None if the API doesn't return it.
    token_count: int = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        token_count = (
            getattr(response.usage_metadata, "total_token_count", 0) or 0
        )

    # --- Step 5: Log to AIQuery table ---
    query_log = AIQuery(
        user_id=user_id,
        input_text=text,
        response_text=explanation,
        token_count=token_count,
    )
    db.add(query_log)
    await db.flush()

    # --- Step 6: Return results ---
    return explanation, token_count
