"""
app/services/video_service.py — YouTube video processing service.

Fetches timed subtitles via yt-dlp (primary) with youtube-transcript-api as
fallback, tokenises each segment, retrieves metadata (title, duration) from
YouTube Data API v3, persists a VideoSession record to the database, and
returns a structured JSON payload.
"""

from __future__ import annotations

import asyncio
import html
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.language import Language
from app.models.sessions import VideoSession
from app.utils.tokeniser import tokenise_text

# ---------------------------------------------------------------------------
# Regex that matches any common YouTube URL format and captures the video ID.
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

        duration_str: str = item.get("contentDetails", {}).get("duration", "")
        duration_seconds = _parse_iso8601_duration(duration_str)

        return {"title": title, "duration_seconds": duration_seconds}
    except Exception:
        return {"title": None, "duration_seconds": None}


def _parse_iso8601_duration(duration: str) -> Optional[int]:
    """Convert ISO 8601 duration string to total seconds."""
    pattern = re.compile(
        r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    )
    match = pattern.match(duration)
    if not match:
        return None
    days, hours, minutes, seconds = (int(v) if v else 0 for v in match.groups())
    return days * 86_400 + hours * 3_600 + minutes * 60 + seconds


def _normalise_transcript_items(items: list[Any]) -> list[dict[str, Any]]:
    """Convert transcript items (object or dict) to a consistent dict format."""
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


# ---------------------------------------------------------------------------
# PRIMARY: yt-dlp subtitle fetcher
# ---------------------------------------------------------------------------

def _parse_json3_subtitles(data: dict) -> list[dict[str, Any]]:
    """
    Parse YouTube JSON3 subtitle format into the standard list-of-dicts format.

    JSON3 events look like:
      {"tStartMs": 1234, "dDurationMs": 2000, "segs": [{"utf8": "Hello "}]}
    """
    items: list[dict[str, Any]] = []
    for event in data.get("events", []):
        segs = event.get("segs")
        if not segs:
            continue

        start_ms = event.get("tStartMs", 0)
        dur_ms = event.get("dDurationMs", 2000)

        text = "".join(seg.get("utf8", "") for seg in segs)
        text = text.replace("\n", " ").strip()

        if not text:
            continue

        items.append(
            {
                "text": text,
                "start": start_ms / 1000.0,
                "duration": dur_ms / 1000.0,
            }
        )
    return items


async def _fetch_subtitles_ytdlp(
    video_id: str,
    preferred_langs: list[str],
) -> list[dict[str, Any]]:
    """
    Fetch subtitles using yt-dlp.

    yt-dlp uses YouTube's internal TV/Android clients which bypass the bot
    detection that blocks youtube-transcript-api on VPS IP addresses.

    Returns a list of subtitle dicts (text, start, duration) or [] on failure.
    """
    try:
        import yt_dlp  # noqa: PLC0415
    except ImportError:
        return []

    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        # iOS client uses the YouTube iOS app API — most reliable on VPS IPs
        "extractor_args": {"youtube": {"player_client": ["ios", "tv_embedded", "web"]}},
    }

    def _extract() -> dict:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        info = await asyncio.get_event_loop().run_in_executor(None, _extract)
    except Exception:
        return []

    # Try manual subtitles first, then auto-generated captions.
    for sub_key in ("subtitles", "automatic_captions"):
        subs: dict = info.get(sub_key) or {}

        for lang in preferred_langs:
            # Exact match first, then language prefix match (e.g. "en" → "en-US").
            matched_lang: str | None = None
            if lang in subs:
                matched_lang = lang
            else:
                for available in subs:
                    if available.lower().startswith(lang.lower()):
                        matched_lang = available
                        break

            if not matched_lang:
                continue

            formats: list[dict] = subs[matched_lang]
            if not formats:
                continue

            # Prefer json3 — easiest to parse.
            fmt_url: str | None = None
            for fmt in formats:
                if fmt.get("ext") == "json3":
                    fmt_url = fmt.get("url")
                    break
            if not fmt_url:
                fmt_url = formats[0].get("url")

            if not fmt_url:
                continue

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(fmt_url)
                    resp.raise_for_status()
                    data = resp.json()
                result = _parse_json3_subtitles(data)
                if result:
                    return result
            except Exception:
                continue

    return []


# ---------------------------------------------------------------------------
# FALLBACK 1: youtube-transcript-api
# ---------------------------------------------------------------------------

def _fetch_best_available_transcript(
    video_id: str,
    preferred_lang_codes: list[str],
) -> list[dict[str, Any]]:
    """
    Fetch transcript via youtube-transcript-api with fallback order:
      1) preferred manual transcript
      2) preferred generated transcript
      3) any available transcript
    """
    from youtube_transcript_api import YouTubeTranscriptApi  # noqa: PLC0415

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

    for transcript in transcript_list:
        try:
            return _normalise_transcript_items(transcript.fetch())
        except Exception:
            continue

    return []


# ---------------------------------------------------------------------------
# FALLBACK 2: YouTube timedtext API (legacy)
# ---------------------------------------------------------------------------

async def _fetch_timedtext_fallback(
    video_id: str,
    preferred_lang_codes: list[str],
) -> list[dict[str, Any]]:
    """
    Last-resort caption retrieval using YouTube's old timedtext endpoint.
    Helps in edge cases where both yt-dlp and youtube-transcript-api fail.
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

            items.append({"text": text, "start": start, "duration": duration})

        return items


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

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
      2. Resolve preferred subtitle language.
      3. Fetch subtitles: yt-dlp → youtube-transcript-api → timedtext fallback.
      4. Tokenise each subtitle segment.
      5. Fetch video metadata from YouTube Data API v3.
      6. Persist a VideoSession record to the database.
      7. Return structured payload.
    """
    # --- Step 1: Validate URL ---
    video_id = _extract_video_id(url)

    # --- Step 2: Resolve preferred language ---
    lang_result = await db.execute(
        select(Language.code).where(Language.language_id == language_id)
    )
    preferred_code = lang_result.scalar_one_or_none() or "en"

    preferred_langs = [preferred_code, "en", "en-US", "en-GB", "ru", "uz"]
    preferred_langs = list(dict.fromkeys(preferred_langs))  # dedup, preserve order

    # --- Step 3: Fetch subtitles with cascading fallbacks ---

    # 3a. Primary: yt-dlp (uses internal YouTube clients, bypasses bot detection)
    transcript_list = await _fetch_subtitles_ytdlp(video_id, preferred_langs)

    # 3b. Fallback: youtube-transcript-api
    if not transcript_list:
        try:
            from youtube_transcript_api import (  # noqa: PLC0415
                NoTranscriptFound,
                TranscriptsDisabled,
            )

            transcript_list = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: _fetch_best_available_transcript(video_id, preferred_langs),
            )
        except Exception:
            transcript_list = []

    # 3c. Last resort: legacy timedtext endpoint
    if not transcript_list:
        try:
            transcript_list = await _fetch_timedtext_fallback(video_id, preferred_langs)
        except Exception:
            transcript_list = []

    if not transcript_list:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bu video uchun subtitrlar topilmadi yoki o'qib bo'lmadi.",
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

    # --- Step 6: Persist VideoSession ---
    session = VideoSession(
        user_id=user_id,
        language_id=language_id,
        youtube_video_id=video_id,
        title=metadata["title"],
        duration_seconds=metadata["duration_seconds"],
        subtitles_json=segments,
    )
    db.add(session)
    await db.flush()

    # --- Step 7: Return payload ---
    return {
        "session_id": session.session_id,
        "youtube_video_id": video_id,
        "title": metadata["title"],
        "duration_seconds": metadata["duration_seconds"],
        "segments": segments,
    }
