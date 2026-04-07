"""
app/routers/video.py — YouTube video processing endpoint.

POST /api/video/process — Accept a YouTube URL, fetch and tokenise subtitles,
store a VideoSession, and return the structured subtitle payload.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.video import VideoProcessRequest, VideoProcessResponse
from app.services import video_service

router = APIRouter(prefix="/video", tags=["video"])


async def _get_user_id(request: Request, db: AsyncSession) -> int:
    """Resolve the internal user_id from the authenticated Telegram user."""
    telegram_id: int = request.state.user["id"]
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        from app.services import auth_service
        user = await auth_service.upsert_user(db, request.state.user)
    return user.user_id


@router.post(
    "/process",
    response_model=VideoProcessResponse,
    summary="YouTube videosini qayta ishlash va subtitrlarni tokenizatsiya qilish",
)
async def process_video(
    payload: VideoProcessRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> VideoProcessResponse:
    """
    Process a YouTube video URL and return tokenised subtitles.

    Steps:
      1. Validate the URL and extract the YouTube video ID.
      2. Fetch timed subtitles via YouTubeTranscriptApi.
      3. Tokenise each subtitle segment.
      4. Retrieve video title and duration from YouTube Data API v3.
      5. Persist a VideoSession to the database.
      6. Return the structured VideoProcessResponse.

    Raises:
        400 if the URL is not a valid YouTube URL.
        422 if subtitles are disabled or unavailable for the video.
        502 if the YouTube API returns an error.
    """
    # Resolve the internal user ID from the authenticated Telegram session.
    user_id = await _get_user_id(request, db)

    # Delegate all processing logic to the service layer.
    result = await video_service.process_video(
        url=payload.url,
        language_id=payload.language_id,
        user_id=user_id,
        db=db,
    )

    return result  # type: ignore[return-value]
