"""
app/services/video_service.py — YouTube video processing service.

Fetches timed subtitles via youtube-transcript-api, tokenises each segment,
retrieves metadata (title, duration) from YouTube Data API v3, persists a
VideoSession record to the database, and returns a structured JSON payload.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

from app.config import settings
from app.models.sessions import VideoSession
from app.utils.tokeniser import tokenise_text

# ---------------------------------------------------------------------------
# Regex that matches any common YouTube URL format and captures the video ID.
# Supported formats:
#   https://www.youtube.com/watch?v=VIDEO_ID
#   https://youtu.be/VIDEO_ID
#   https://youtube.com/shorts/VIDEO_ID
# ---------------------------------------------------------------------------
_YT_URL_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def _extract_video_id(url: str) -> str:
    """
    Extract the 11-character YouTube video ID from a URL string.

    Raises:
        HTTPException 400 if the URL does not match a recognised YouTube format.
    """
    match = _YT_URL_RE.search(url)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Noto'g'ri YouTube havolasi. Iltimos, to'g'ri URL kiriting.",
        )
    return match.group(1)


async def _fetch_video_metadata(video_id: str) -> Dict[str, Any]:
    """
    Call YouTube Data API v3 to retrieve video title and duration.

    Returns a dict with keys 'title' and 'duration_seconds'.
    Falls back to empty values on API errors rather than aborting the request.
    """
    # YouTube Data API v3 videos.list endpoint.
    api_url = (
        "https://www.googleapis.com/youtube/v3/videos"
        f"?id={video_id}&part=snippet,contentDetails&key={settings.YOUTUBE_API_KEY}"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(api_url)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", [])
        if not items:
            return {"title": None, "duration_seconds": None}

        item = items[0]
        title: Optional[str] = item.get("snippet", {}).get("title")

        # Parse ISO 8601 duration string (e.g. "PT4M13S") into total seconds.
        duration_str: str = item.get("contentDetails", {}).get("duration", "")
        duration_seconds = _parse_iso8601_duration(duration_str)

        return {"title": title, "duration_seconds": duration_seconds}
    except Exception:
        # Non-fatal: return empty metadata rather than failing the whole request.
        return {"title": None, "duration_seconds": None}


def _parse_iso8601_duration(duration: str) -> Optional[int]:
    """
    Convert an ISO 8601 duration string to total seconds.

    E.g. "PT1H2M3S" → 3723, "PT4M13S" → 253.
    Returns None if the string cannot be parsed.
    """
    pattern = re.compile(
        r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    )
    match = pattern.match(duration)
    if not match:
        return None
    days, hours, minutes, seconds = (int(v) if v else 0 for v in match.groups())
    return days * 86_400 + hours * 3_600 + minutes * 60 + seconds


async def process_video(
    url: str,
    language_id: int,
    user_id: int,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Full pipeline for processing a YouTube video URL.

    Steps:
      1. Validate URL and extract video ID.
      2. Fetch timed subtitles via YouTubeTranscriptApi.
      3. Tokenise each subtitle segment.
      4. Fetch video metadata from YouTube Data API v3.
      5. Persist a VideoSession record to the database.
      6. Return structured payload.

    Args:
        url:         YouTube URL submitted by the user.
        language_id: ID of the language the user is studying.
        user_id:     Internal user ID for DB persistence.
        db:          Async database session.

    Returns:
        Dict matching the VideoProcessResponse schema.
    """
    # --- Step 1: Validate URL and extract video ID ---
    video_id = _extract_video_id(url)

    # --- Step 2: Fetch timed subtitles ---
    # YouTubeTranscriptApi is synchronous; run in default thread pool.
    import asyncio

    try:
        transcript_list = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: YouTubeTranscriptApi.get_transcript(video_id),
        )
    except TranscriptsDisabled:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bu video uchun subtitrlar o'chirib qo'yilgan.",
        )
    except NoTranscriptFound:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bu video uchun subtitrlar topilmadi.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"YouTube API xatosi: {exc}",
        )

    # --- Step 3: Tokenise each subtitle segment ---
    segments: List[Dict[str, Any]] = []
    for entry in transcript_list:
        tokens = tokenise_text(entry["text"])
        segments.append(
            {
                "start": entry["start"],
                "duration": entry.get("duration", 0.0),
                "text": entry["text"],
                "tokens": tokens,
            }
        )

    # --- Step 4: Fetch video metadata ---
    metadata = await _fetch_video_metadata(video_id)

    # --- Step 5: Persist VideoSession to the database ---
    session = VideoSession(
        user_id=user_id,
        language_id=language_id,
        youtube_video_id=video_id,
        title=metadata["title"],
        duration_seconds=metadata["duration_seconds"],
        subtitles_json=segments,
    )
    db.add(session)
    await db.flush()  # Populate session_id before returning.

    # --- Step 6: Return structured payload ---
    return {
        "session_id": session.session_id,
        "youtube_video_id": video_id,
        "title": metadata["title"],
        "duration_seconds": metadata["duration_seconds"],
        "segments": segments,
    }
