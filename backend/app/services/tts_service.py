"""
app/services/tts_service.py — Text-to-Speech synthesis with R2 storage and Redis caching.

Generates pronunciation audio for vocabulary words using Google Cloud TTS
(WaveNet voices for natural-sounding output), stores the MP3 in Cloudflare R2,
and caches the resulting URL in Redis so subsequent requests are instant.
"""

from __future__ import annotations

import hashlib
import asyncio
from typing import Optional

from app.config import settings
from app.utils.redis_client import get_cache, set_cache
from app.utils.r2_client import upload_file

# Redis cache key prefix and TTL.
_CACHE_PREFIX = "tts:"
_CACHE_TTL = 30 * 24 * 3_600  # 30 days in seconds


def _word_hash(word: str) -> str:
    """
    Generate a short, safe filename-friendly hash for a word.

    Uses SHA-256 of the lowercase word, truncated to 16 hex characters.
    """
    return hashlib.sha256(word.lower().encode()).hexdigest()[:16]


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
    cache_key = f"{_CACHE_PREFIX}{word.lower()}"

    # --- Step 1: Check Redis cache ---
    cached_url = await get_cache(cache_key)
    if cached_url:
        return cached_url

    # --- Step 3: Call Google Cloud TTS ---
    try:
        from google.cloud import texttospeech

        # Initialise the async TTS client.
        client = texttospeech.TextToSpeechAsyncClient()

        # Build the synthesis input with the word as plain text.
        synthesis_input = texttospeech.SynthesisInput(text=word)

        # Select a WaveNet voice for natural-sounding output.
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
            # WaveNet voices provide the highest quality pronunciation.
            name=f"{language_code}-Wavenet-D",
        )

        # Request MP3 output — universally supported by browsers.
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # Execute the synthesis RPC.
        response = await client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        mp3_bytes: bytes = response.audio_content

    except Exception:
        # TTS failure is non-fatal — the app can function without audio.
        return None

    # --- Step 4: Upload MP3 to Cloudflare R2 ---
    r2_key = f"audio/{_word_hash(word)}.mp3"
    public_url = await upload_file(r2_key, mp3_bytes, "audio/mpeg")

    # --- Step 5: Cache the public URL ---
    await set_cache(cache_key, public_url, _CACHE_TTL)

    # --- Step 6: Return the URL ---
    return public_url
