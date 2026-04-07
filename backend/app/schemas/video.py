"""
app/schemas/video.py — Pydantic schemas for YouTube video processing endpoints.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# Nested schemas
# ---------------------------------------------------------------------------

class TokenSchema(BaseModel):
    """A single tokenised word within a subtitle segment."""

    # Canonical lowercase word with punctuation stripped — used for lookups.
    word: str = Field(..., description="Lookup form of the word (lowercase, no punctuation)")

    # The original display form as it appears in the subtitle text.
    display: str = Field(..., description="Original display form including punctuation")

    # Zero-based position of this token within its parent segment.
    index: int = Field(..., description="Token position within the segment")


class SegmentSchema(BaseModel):
    """A single subtitle cue (timed segment) from a YouTube video."""

    # Start time in seconds relative to the beginning of the video.
    start: float = Field(..., description="Segment start time in seconds")

    # Duration of this segment in seconds.
    duration: float = Field(..., description="Segment duration in seconds")

    # Raw subtitle text before tokenisation.
    text: str = Field(..., description="Original subtitle text")

    # List of tokens extracted from the subtitle text.
    tokens: List[TokenSchema] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class VideoProcessRequest(BaseModel):
    """Request body for POST /api/video/process."""

    # Full YouTube URL submitted by the user.
    url: str = Field(..., description="YouTube video URL")

    # Language ID the user is studying (determines which subtitle track to use).
    language_id: int = Field(..., description="ID of the target learning language")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class VideoProcessResponse(BaseModel):
    """Full response after processing a YouTube video."""

    # Internal DB primary key of the newly created VideoSession.
    session_id: int

    # YouTube video ID (11-character string).
    youtube_video_id: str

    # Video title from YouTube Data API v3.
    title: Optional[str] = None

    # Total video duration in seconds.
    duration_seconds: Optional[int] = None

    # All subtitle segments with tokenised words.
    segments: List[SegmentSchema] = Field(default_factory=list)
