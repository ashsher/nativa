"""
app/services/translation_service.py — Word translation with Redis caching.

Translates a word from a target language to Uzbek using Google Cloud
Translation API.  Results are cached for 7 days to minimise API costs.
After a cache miss the service also fetches example sentences and generates
a pronunciation audio URL via tts_service.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.utils.redis_client import get_cache, set_cache
from app.services import tts_service

# Redis key pattern and TTL.
_CACHE_PREFIX = "trans:"
_CACHE_TTL = 7 * 24 * 3_600  # 7 days in seconds

# Number of example sentences to fetch per word.
_EXAMPLE_COUNT = 3


def _build_cache_key(lang_code: str, word: str) -> str:
    """Construct a deterministic Redis key for a word translation."""
    return f"{_CACHE_PREFIX}{lang_code}:{word.lower()}"


async def _translate_word(word: str, source_lang: str) -> str:
    """
    Call Google Cloud Translation API to translate *word* to Uzbek ('uz').

    Returns the translated string, or the original word on failure.
    """
    try:
        from google.cloud import translate_v2 as translate

        # Initialise a synchronous client (v2 does not have a native async client).
        import asyncio
        client = translate.Client()
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.translate(
                word,
                source_language=source_lang,
                target_language="uz",
            ),
        )
        return result.get("translatedText", word)
    except Exception:
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
    try:
        from google.cloud import translate_v2 as translate
        import asyncio
        client = translate.Client()

        for sentence in templates[:_EXAMPLE_COUNT]:
            # Translate each template from the source language to Uzbek.
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda s=sentence: client.translate(
                    s,
                    source_language=lang_code,
                    target_language="uz",
                ),
            )
            examples.append(
                {
                    "sentence": sentence,
                    "translation": result.get("translatedText", ""),
                }
            )
    except Exception:
        # Example sentences are supplementary — don't fail the request.
        pass

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
    # BCP-47 code: "en" → "en-US", "de" → "de-DE", etc.
    bcp47 = f"{lang_code}-{lang_code.upper()}" if len(lang_code) == 2 else lang_code
    pronunciation_url = await tts_service.synthesise(word, language_code=bcp47)

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
