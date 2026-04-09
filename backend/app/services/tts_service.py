"""
app/services/tts_service.py — Text-to-Speech synthesis with R2 storage and Redis caching.

Generates pronunciation audio for vocabulary words using Google Cloud TTS
(WaveNet voices for natural-sounding output), stores the MP3 in Cloudflare R2,
and caches the resulting URL in Redis so subsequent requests are instant.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Optional

import httpx

from app.config import settings
from app.utils.redis_client import get_cache, set_cache
from app.utils.r2_client import upload_file

# Redis cache key prefix and TTL.
_CACHE_PREFIX = "tts:v2:"
_CACHE_TTL = 30 * 24 * 3_600  # 30 days in seconds

logger = logging.getLogger(__name__)

# Common ISO 639-1 to BCP-47 defaults for better voice compatibility.
_LANG_CODE_MAP = {
    "en": "en-US",
    "uz": "uz-UZ",
    "ru": "ru-RU",
    "tr": "tr-TR",
    "de": "de-DE",
    "fr": "fr-FR",
    "es": "es-ES",
    "it": "it-IT",
    "pt": "pt-PT",
    "ko": "ko-KR",
    "ja": "ja-JP",
}


def _normalise_language_code(language_code: str) -> str:
    """
    Convert short language codes (en, ru, uz) to BCP-47.
    """
    if not language_code:
        return "en-US"

    value = language_code.strip()
    if "-" in value:
        return value

    return _LANG_CODE_MAP.get(value.lower(), "en-US")


def _word_hash(word: str, language_code: str) -> str:
    """
    Generate a short, safe filename-friendly hash for a word.

    Uses SHA-256 of the lowercase word, truncated to 16 hex characters.
    """
    return hashlib.sha256(f"{language_code}:{word.lower()}".encode()).hexdigest()[:16]


def _as_data_url(mp3_bytes: bytes) -> str:
    """
    Build an inline audio data URL fallback when object storage URL is unavailable.
    """
    b64 = base64.b64encode(mp3_bytes).decode("ascii")
    return f"data:audio/mpeg;base64,{b64}"


async def _synthesise_via_rest(word: str, language_code: str) -> Optional[bytes]:
    """
    Generate MP3 via Google Cloud TTS REST API using GOOGLE_API_KEY.
    """
    if not settings.GOOGLE_API_KEY:
        return None

    endpoint = "https://texttospeech.googleapis.com/v1/text:synthesize"
    payload = {
        "input": {"text": word},
        "voice": {
            "languageCode": language_code,
            "ssmlGender": "NEUTRAL",
        },
        "audioConfig": {"audioEncoding": "MP3"},
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                endpoint,
                params={"key": settings.GOOGLE_API_KEY},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        audio_b64 = data.get("audioContent")
        if not audio_b64:
            return None
        return base64.b64decode(audio_b64)
    except Exception as exc:
        logger.warning("Google TTS REST failed: %s", exc)
        return None


async def _synthesise_via_client(word: str, language_code: str) -> Optional[bytes]:
    """
    Fallback synthesis using google-cloud-texttospeech + ADC credentials.
    """
    try:
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechAsyncClient()
        synthesis_input = texttospeech.SynthesisInput(text=word)
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        response = await client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        return response.audio_content
    except Exception as exc:
        logger.warning("Google TTS client fallback failed: %s", exc)
        return None


async def synthesise(word: str, language_code: str = "en-US") -> Optional[str]:
    """
    Return the public URL of the MP3 pronunciation for *word*.

    Pipeline:
      1. Check Redis cache key "tts:{word_lower}".
      2. If cached: return the stored URL immediately.
      3. If not cached: call Google Cloud TTS (WaveNet, MP3 format).
      4. Upload the raw MP3 bytes to Cloudflare R2 as "audio/{hash}.mp3".
      5. Cache the resulting public URL in Redis with a 30-day TTL.
      6. Return the public URL.

    Args:
        word:          The word to synthesise.
        language_code: BCP-47 language code for the TTS voice (default en-US).

    Returns:
        Public URL string, or None if synthesis fails.
    """
    language_code = _normalise_language_code(language_code)
    cache_key = f"{_CACHE_PREFIX}{language_code}:{word.lower()}"

    # --- Step 1: Check Redis cache ---
    cached_url = await get_cache(cache_key)
    if cached_url:
        return cached_url

    # --- Step 3: Call Google Cloud TTS ---
    mp3_bytes = await _synthesise_via_rest(word, language_code)
    if not mp3_bytes:
        mp3_bytes = await _synthesise_via_client(word, language_code)
    if not mp3_bytes:
        return None

    # --- Step 4: Upload MP3 to Cloudflare R2 ---
    r2_key = f"audio/{_word_hash(word, language_code)}.mp3"
    try:
        public_url = await upload_file(r2_key, mp3_bytes, "audio/mpeg")
    except Exception as exc:
        logger.warning("R2 upload failed for '%s': %s; using inline audio URL", word, exc)
        public_url = _as_data_url(mp3_bytes)
    else:
        # Verify URL is reachable. If not, fall back to inline data URL.
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                probe = await client.get(public_url)
            if probe.status_code >= 400:
                logger.warning(
                    "R2 URL probe failed (%s) for '%s'; using inline audio URL",
                    probe.status_code,
                    word,
                )
                public_url = _as_data_url(mp3_bytes)
        except Exception as exc:
            logger.warning("R2 URL probe error for '%s': %s; using inline audio URL", word, exc)
            public_url = _as_data_url(mp3_bytes)

    # --- Step 5: Cache the public URL ---
    await set_cache(cache_key, public_url, _CACHE_TTL)

    # --- Step 6: Return the URL ---
    return public_url
