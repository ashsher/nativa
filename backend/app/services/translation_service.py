"""
app/services/translation_service.py — Word translation with Redis caching.

Translates a word from a target language to Uzbek using Google Cloud
Translation API.  Results are cached for 7 days to minimise API costs.
After a cache miss the service also fetches example sentences and generates
a pronunciation audio URL via tts_service.
"""

from __future__ import annotations

import html
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.utils.redis_client import get_cache, set_cache
from app.services import tts_service

# Redis key pattern and TTL.
_CACHE_PREFIX = "trans:"
_CACHE_TTL = 7 * 24 * 3_600  # 7 days in seconds

# Number of example sentences to fetch per word.
_EXAMPLE_COUNT = 3

logger = logging.getLogger(__name__)


def _build_cache_key(lang_code: str, word: str) -> str:
    """Construct a deterministic Redis key for a word translation."""
    return f"{_CACHE_PREFIX}{lang_code}:{word.lower()}"


async def _translate_word_via_rest(text: str, source_lang: str) -> Optional[str]:
    """
    Call Google Translation REST API using GOOGLE_API_KEY.
    """
    if not settings.GOOGLE_API_KEY:
        return None

    try:
        endpoint = "https://translation.googleapis.com/language/translate/v2"
        payload = {
            "q": text,
            "source": source_lang,
            "target": "uz",
            "format": "text",
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                endpoint,
                params={"key": settings.GOOGLE_API_KEY},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        translated = (
            data.get("data", {})
            .get("translations", [{}])[0]
            .get("translatedText")
        )
        if not translated:
            return None
        return html.unescape(translated)
    except Exception as exc:
        logger.warning("Google Translate REST failed: %s", exc)
        return None


async def _translate_word_via_client(text: str, source_lang: str) -> Optional[str]:
    """
    Fallback translation using google-cloud-translate client + ADC credentials.
    """
    try:
        import asyncio
        from google.cloud import translate_v2 as translate

        client = translate.Client()
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.translate(
                text,
                source_language=source_lang,
                target_language="uz",
            ),
        )
        translated = result.get("translatedText")
        if not translated:
            return None
        return html.unescape(translated)
    except Exception as exc:
        logger.warning("Google Translate client fallback failed: %s", exc)
        return None


async def _translate_word(word: str, source_lang: str) -> str:
    """
    Translate *word* to Uzbek.
    """
    translated = await _translate_word_via_rest(word, source_lang)
    if translated:
        return translated

    translated = await _translate_word_via_client(word, source_lang)
    if translated:
        return translated

    return word


async def _get_example_sentences(
    word: str, lang_code: str
) -> List[Dict[str, str]]:
    """
    Generate example sentences for *word* via Google Translate.

    We construct simple template sentences and translate them to Uzbek.
    Returns a list of dicts: [{"sentence": "...", "translation": "..."}].
    """
    # Template sentences that illustrate common usage.
    templates = [
        f"I saw {word} yesterday.",
        f"She likes {word} very much.",
        f"This is a great example of {word}.",
    ]

    examples: List[Dict[str, str]] = []
    for sentence in templates[:_EXAMPLE_COUNT]:
        translation = await _translate_word_via_rest(sentence, lang_code)
        if not translation:
            translation = await _translate_word_via_client(sentence, lang_code)
        if not translation:
            translation = ""
        examples.append({"sentence": sentence, "translation": translation})

    return examples


async def translate_word(
    word: str,
    lang_code: str,
) -> Dict[str, Any]:
    """
    Translate a single *word* from *lang_code* to Uzbek with full enrichment.

    Pipeline:
      1. Build cache key "trans:{lang_code}:{word_lower}".
      2. Check Redis — return cached result if present.
      3. On cache miss: call Google Cloud Translation API.
      4. Fetch up to 3 example sentences.
      5. Generate pronunciation audio URL via tts_service.
      6. Build result object and store in Redis with 7-day TTL.
      7. Return result object.

    Args:
        word:      Word in the target language to translate.
        lang_code: ISO 639-1 code of the source language (e.g. "en").

    Returns:
        Dict with keys: word, translation, pronunciation_url, examples.
    """
    cache_key = _build_cache_key(lang_code, word)

    # --- Step 2: Check Redis cache ---
    cached = await get_cache(cache_key)
    if cached:
        return cached

    # --- Step 3: Translate via Google Cloud Translation ---
    translation = await _translate_word(word, lang_code)

    # --- Step 4: Fetch example sentences ---
    examples = await _get_example_sentences(word, lang_code)

    # --- Step 5: Generate TTS pronunciation URL ---
    try:
        pronunciation_url = await tts_service.synthesise(word, language_code=lang_code)
    except Exception as exc:
        logger.warning("TTS generation failed for '%s': %s", word, exc)
        pronunciation_url = None

    # --- Step 6: Build and cache result ---
    result: Dict[str, Any] = {
        "word": word,
        "translation": translation,
        "pronunciation_url": pronunciation_url,
        "examples": examples,
    }
    await set_cache(cache_key, result, _CACHE_TTL)

    # --- Step 7: Return ---
    return result
