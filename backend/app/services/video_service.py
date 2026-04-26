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
from urllib.parse import urlparse, parse_qs

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.language import Language
from app.models.sessions import VideoSession
from app.utils.tokeniser import tokenise_text

_VIDEO_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')


def _extract_video_id(url: str) -> str:
    """
    Extract the 11-character YouTube video ID from any recognised URL format.

    Handles:
      - https://www.youtube.com/watch?v=ID
      - https://www.youtube.com/watch?feature=share&v=ID  (params before v=)
      - https://m.youtube.com/watch?v=ID
      - https://youtu.be/ID
      - https://youtube.com/shorts/ID
      - https://youtube.com/embed/ID
      - https://youtube.com/live/ID

    Raises:
        HTTPException 400 if no valid video ID can be extracted.
    """
    try:
        parsed = urlparse(url.strip())
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Noto'g'ri YouTube havolasi. Iltimos, to'g'ri URL kiriting.",
        )

    hostname = (parsed.hostname or '').lower()
    is_youtube = hostname == 'youtu.be' or hostname.endswith('youtube.com')
    if not is_youtube:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Noto'g'ri YouTube havolasi. Iltimos, to'g'ri URL kiriting.",
        )

    # ?v= query parameter — works for any param order (e.g. ?feature=share&v=ID)
    params = parse_qs(parsed.query)
    if 'v' in params:
        vid = params['v'][0]
        if _VIDEO_ID_RE.match(vid):
            return vid

    # Path-based formats: /shorts/ID, /embed/ID, /live/ID, /v/ID
    path_parts = [p for p in parsed.path.split('/') if p]
    for i, part in enumerate(path_parts):
        if part in ('shorts', 'embed', 'live', 'v') and i + 1 < len(path_parts):
            candidate = path_parts[i + 1]
            if _VIDEO_ID_RE.match(candidate):
                return candidate
        # youtu.be/ID — video ID is the first path segment
        if hostname == 'youtu.be' and i == 0:
            if _VIDEO_ID_RE.match(part):
                return part

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Noto'g'ri YouTube havolasi. Iltimos, to'g'ri URL kiriting.",
    )


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
# InnerTube client definitions
# ---------------------------------------------------------------------------

# Public InnerTube API key (stable, used by yt-dlp and subtitle tools).
_INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"

# Android app client — bypasses many VPS IP restrictions.
_ANDROID_CLIENT = {
    "clientName": "ANDROID",
    "clientVersion": "19.09.37",
    "androidSdkVersion": 30,
    "userAgent": (
        "com.google.android.youtube/19.09.37 "
        "(Linux; U; Android 11; en_US; sdk_gphone_x86 Build/RSR1.210722.013.A6) "
        "gzip"
    ),
    "hl": "en",
    "gl": "US",
}
# X-YouTube-Client-Name value for each client
_INNERTUBE_CLIENT_IDS = {
    "ANDROID": "3",
    "TVHTML5_SIMPLY_EMBEDDED_PLAYER": "85",
}

# TV embedded player client — different fingerprint from Android;
# YouTube applies different bot-detection rules to it.
_TV_EMBEDDED_CLIENT = {
    "clientName": "TVHTML5_SIMPLY_EMBEDDED_PLAYER",
    "clientVersion": "2.0",
    "userAgent": (
        "Mozilla/5.0 (PlayStation 4 3.11) AppleWebKit/537.73 "
        "(KHTML, like Gecko)"
    ),
    "hl": "en",
    "gl": "US",
}


def _score_caption_track(lang_code: str, preferred: list[str]) -> int:
    """Return a lower score for higher-priority language matches."""
    lc = lang_code.lower()
    for idx, p in enumerate(preferred):
        if lc == p:
            return idx
        if lc.startswith(p + "-") or p.startswith(lc + "-"):
            return idx + 100
    return 10_000


async def _fetch_subtitles_innertube(
    video_id: str,
    preferred_langs: list[str],
    client_ctx: dict | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch subtitles via YouTube's InnerTube API.

    Accepts an optional client_ctx to switch between Android and TV-embedded
    fingerprints — YouTube applies different bot-detection rules to each.

    Returns a list of caption dicts (text, start, duration) or [] on failure.
    """
    ctx = client_ctx or _ANDROID_CLIENT
    payload = {
        "context": {"client": ctx},
        "videoId": video_id,
    }
    client_id_str = _INNERTUBE_CLIENT_IDS.get(ctx.get("clientName", ""), "3")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": ctx.get("userAgent", _ANDROID_CLIENT["userAgent"]),
        "X-YouTube-Client-Name": client_id_str,
        "X-YouTube-Client-Version": ctx.get("clientVersion", _ANDROID_CLIENT["clientVersion"]),
        "Origin": "https://www.youtube.com",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"https://www.youtube.com/youtubei/v1/player?key={_INNERTUBE_KEY}",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    # Extract caption track list from the player response.
    captions_renderer = (
        data.get("captions", {})
        .get("playerCaptionsTracklistRenderer", {})
    )
    tracks: list[dict] = captions_renderer.get("captionTracks", [])
    if not tracks:
        return []

    preferred_lower = [p.lower() for p in preferred_langs]

    # Sort tracks by language preference score (lower = better).
    tracks.sort(
        key=lambda t: _score_caption_track(
            t.get("languageCode", ""), preferred_lower
        )
    )
    best = tracks[0]
    base_url: str = best.get("baseUrl", "")
    if not base_url:
        return []

    # Request JSON3 format for easy parsing.
    json3_url = base_url + "&fmt=json3"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            cap_resp = await client.get(json3_url)
            cap_resp.raise_for_status()
            cap_data = cap_resp.json()
    except Exception:
        return []

    return _parse_json3_subtitles(cap_data)


# ---------------------------------------------------------------------------
# PRIMARY: youtube-transcript-api (new instance-based API, >=0.6.3)
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
        # android_creator (YouTube Studio app) is least affected by datacenter
        # IP bot-detection in 2025; mweb and ios are additional fallbacks.
        "extractor_args": {
            "youtube": {
                "player_client": ["android_creator", "android", "ios", "mweb", "tv_embedded"],
            }
        },
        "http_headers": {
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    def _extract() -> dict:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        # Hard 50-second timeout so a hung yt-dlp call doesn't block the request.
        info = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, _extract),
            timeout=50.0,
        )
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
# FALLBACK 1: youtube-transcript-api (new instance API, >=0.6.3)
# ---------------------------------------------------------------------------

def _fetch_best_available_transcript(
    video_id: str,
    preferred_lang_codes: list[str],
) -> list[dict[str, Any]]:
    """
    Fetch transcript using youtube-transcript-api's new instance-based API
    (introduced in >=0.6.3).  The new API uses an internal mechanism that
    bypasses YouTube's bot detection, unlike the old static-method API (0.6.2).

    Priority order:
      1) Preferred language match (exact or prefix)
      2) Any available transcript
    """
    from youtube_transcript_api import YouTubeTranscriptApi  # noqa: PLC0415

    api = YouTubeTranscriptApi()
    # Convert to list so we can iterate multiple times for language matching.
    transcripts = list(api.list(video_id))

    preferred = [p.lower() for p in preferred_lang_codes]

    # 1. Try preferred languages first.
    for lang in preferred:
        for t in transcripts:
            code = t.language_code.lower()
            if code == lang or code.startswith(lang + "-") or lang.startswith(code + "-"):
                try:
                    return _normalise_transcript_items(t.fetch())
                except Exception:
                    continue

    # 2. Fall back to first available transcript in any language.
    for t in transcripts:
        try:
            return _normalise_transcript_items(t.fetch())
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

    # --- Step 1b: DB cache — serve from existing VideoSession if available ---
    cached_result = await db.execute(
        select(VideoSession)
        .where(VideoSession.youtube_video_id == video_id)
        .limit(1)
    )
    cached = cached_result.scalar_one_or_none()
    if cached and cached.subtitles_json:
        return {
            "session_id": cached.session_id,
            "youtube_video_id": video_id,
            "title": cached.title,
            "duration_seconds": cached.duration_seconds,
            "segments": cached.subtitles_json,
        }

    # --- Step 2: Resolve preferred language ---
    lang_result = await db.execute(
        select(Language.code).where(Language.language_id == language_id)
    )
    preferred_code = lang_result.scalar_one_or_none() or "en"

    preferred_langs = [preferred_code, "en", "en-US", "en-GB", "ru", "uz"]
    preferred_langs = list(dict.fromkeys(preferred_langs))  # dedup, preserve order

    # --- Step 3: Fetch subtitles with cascading fallbacks ---
    # Order: yt-dlp (most maintained, best client variety) → InnerTube Android
    # → InnerTube TV-embedded (different bot-detection bucket) →
    # youtube-transcript-api → legacy timedtext.

    # 3a. yt-dlp with android_creator/ios/mweb clients.
    transcript_list = await _fetch_subtitles_ytdlp(video_id, preferred_langs)

    # 3b. InnerTube Android client (pure httpx, no extra package).
    if not transcript_list:
        transcript_list = await _fetch_subtitles_innertube(video_id, preferred_langs)

    # 3c. InnerTube TV-embedded client (different fingerprint / bot-detection bucket).
    if not transcript_list:
        transcript_list = await _fetch_subtitles_innertube(
            video_id, preferred_langs, _TV_EMBEDDED_CLIENT
        )

    # 3d. youtube-transcript-api instance API (>=0.6.3).
    if not transcript_list:
        try:
            transcript_list = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: _fetch_best_available_transcript(video_id, preferred_langs),
                ),
                timeout=30.0,
            )
        except Exception:
            transcript_list = []

    # 3e. Last resort: legacy timedtext endpoint.
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
