"""
app/services/video_service.py — YouTube video processing service.

Fetches timed subtitles via youtube-transcript-api, tokenises each segment,
retrieves metadata (title, duration) from YouTube Data API v3, persists a
VideoSession record to the database, and returns a structured JSON payload.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

from app.config import settings
from app.models.language import Language
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


def _normalise_transcript_items(items: list[Any]) -> list[dict[str, Any]]:
    """
    Convert transcript items to a consistent dict format.
    """
    normalised: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            normalised.append(
                {
                    "text": item.get("text", ""),
                    "start": float(item.get("start", 0.0)),
                    "duration": float(item.get("duration", 0.0)),
                }
            )
            continue

        normalised.append(
            {
                "text": getattr(item, "text", "") or "",
                "start": float(getattr(item, "start", 0.0) or 0.0),
                "duration": float(getattr(item, "duration", 0.0) or 0.0),
            }
        )
    return normalised


def _fetch_best_available_transcript(
    video_id: str,
    preferred_lang_codes: list[str],
) -> list[dict[str, Any]]:
    """
    Fetch transcript with robust fallback order:
      1) preferred manual transcript,
      2) preferred generated transcript,
      3) any available transcript.
    """
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

    for finder in (
        transcript_list.find_transcript,
        transcript_list.find_generated_transcript,
    ):
        try:
            transcript = finder(preferred_lang_codes)
            return _normalise_transcript_items(transcript.fetch())
        except Exception:
            pass

    # Final fallback: first available transcript in any language.
    for transcript in transcript_list:
        try:
            return _normalise_transcript_items(transcript.fetch())
        except Exception:
            continue

    return []


async def _fetch_timedtext_fallback(
    video_id: str,
    preferred_lang_codes: list[str],
) -> list[dict[str, Any]]:
    """
    Fallback caption retrieval using YouTube timedtext endpoints.

    This helps in cases where youtube-transcript-api cannot resolve tracks
    even though captions exist.
    """
    list_url = "https://www.youtube.com/api/timedtext"

    async with httpx.AsyncClient(timeout=12.0) as client:
        list_resp = await client.get(list_url, params={"type": "list", "v": video_id})
        list_resp.raise_for_status()
        if not list_resp.text.strip():
            return []

        try:
            root = ET.fromstring(list_resp.text)
        except ET.ParseError:
            return []

        tracks: list[dict[str, str]] = []
        for track in root.findall("track"):
            lang = (track.attrib.get("lang_code") or "").strip()
            if not lang:
                continue
            tracks.append(
                {
                    "lang": lang,
                    "name": (track.attrib.get("name") or "").strip(),
                    "kind": (track.attrib.get("kind") or "").strip(),
                }
            )

        if not tracks:
            return []

        preferred = [p.lower() for p in preferred_lang_codes if p]

        def score(item: dict[str, str]) -> int:
            lang = item["lang"].lower()
            best = 10_000
            for idx, p in enumerate(preferred):
                if lang == p:
                    return idx
                if lang.startswith(f"{p}-") or p.startswith(f"{lang}-"):
                    best = min(best, idx + 100)
            return best

        tracks.sort(key=score)
        chosen = tracks[0]

        params: dict[str, str] = {"v": video_id, "lang": chosen["lang"]}
        if chosen["name"]:
            params["name"] = chosen["name"]
        if chosen["kind"]:
            params["kind"] = chosen["kind"]

        cap_resp = await client.get(list_url, params=params)
        cap_resp.raise_for_status()
        if not cap_resp.text.strip():
            return []

        try:
            cap_root = ET.fromstring(cap_resp.text)
        except ET.ParseError:
            return []

        items: list[dict[str, Any]] = []
        for node in cap_root.findall("text"):
            text_raw = (node.text or "").strip()
            text = html.unescape(text_raw).replace("\n", " ").strip()
            if not text:
                continue

            try:
                start = float(node.attrib.get("start", "0") or "0")
            except ValueError:
                start = 0.0

            try:
                duration = float(node.attrib.get("dur", "0") or "0")
            except ValueError:
                duration = 0.0

            if duration <= 0:
                duration = 2.0

            items.append(
                {
                    "text": text,
                    "start": start,
                    "duration": duration,
                }
            )

        return items


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

    # --- Step 2: Resolve preferred language code for subtitle search ---
    lang_result = await db.execute(
        select(Language.code).where(Language.language_id == language_id)
    )
    preferred_code = lang_result.scalar_one_or_none() or "en"

    preferred_langs = [preferred_code, "en", "en-US", "en-GB", "ru", "uz"]
    # Keep order while removing duplicates.
    preferred_langs = list(dict.fromkeys(preferred_langs))

    # --- Step 3: Fetch timed subtitles ---
    # YouTubeTranscriptApi is synchronous; run in default thread pool.
    import asyncio

    transcript_error: str | None = None
    try:
        transcript_list = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _fetch_best_available_transcript(video_id, preferred_langs),
        )
    except TranscriptsDisabled:
        transcript_error = "disabled"
        transcript_list = []
    except NoTranscriptFound:
        transcript_error = "not_found"
        transcript_list = []
    except Exception as exc:
        transcript_error = str(exc)
        transcript_list = []

    # Step 3b: timedtext fallback for videos where transcript API misses captions.
    if not transcript_list:
        try:
            transcript_list = await _fetch_timedtext_fallback(video_id, preferred_langs)
        except Exception:
            transcript_list = []

    if not transcript_list:
        if transcript_error == "disabled":
            detail = "Bu video uchun subtitrlar o'chirib qo'yilgan."
        else:
            detail = "Bu video uchun subtitrlar topilmadi yoki o'qib bo'lmadi."
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )

    # --- Step 4: Tokenise each subtitle segment ---
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

    # --- Step 5: Fetch video metadata ---
    metadata = await _fetch_video_metadata(video_id)

    # --- Step 6: Persist VideoSession to the database ---
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

    # --- Step 7: Return structured payload ---
    return {
        "session_id": session.session_id,
        "youtube_video_id": video_id,
        "title": metadata["title"],
        "duration_seconds": metadata["duration_seconds"],
        "segments": segments,
    }
