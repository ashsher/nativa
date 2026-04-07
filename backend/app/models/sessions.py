"""
app/models/sessions.py — VideoSession and ReadingSession ORM models.

These tables record the media-study sessions a user has completed so that
session history can be displayed and analytics can be computed.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class VideoSession(Base):
    """
    Records a single YouTube video processed by a user.

    Table name: video_sessions
    """

    __tablename__ = "video_sessions"

    # Auto-incremented primary key.
    session_id = Column(Integer, primary_key=True, autoincrement=True)

    # The user who initiated this session.
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Language the user is studying in this session.
    language_id = Column(
        Integer,
        ForeignKey("languages.language_id", ondelete="RESTRICT"),
        nullable=False,
    )

    # YouTube video ID (11-character string), e.g. "dQw4w9WgXcQ".
    youtube_video_id = Column(String(20), nullable=False)

    # Title of the YouTube video at processing time.
    title = Column(String(500), nullable=True)

    # Video duration in seconds as reported by the YouTube Data API.
    duration_seconds = Column(Integer, nullable=True)

    # Full structured subtitle payload: list of segment objects with tokens.
    # Stored as JSONB so it can be queried and indexed if needed.
    subtitles_json = Column(JSONB, nullable=True)

    # Timestamp when this session was created.
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user = relationship("User", back_populates="video_sessions")
    language = relationship("Language")

    def __repr__(self) -> str:
        return (
            f"<VideoSession session_id={self.session_id} "
            f"video_id={self.youtube_video_id}>"
        )


class ReadingSession(Base):
    """
    Records a single article reading session for a user.

    Table name: reading_sessions
    """

    __tablename__ = "reading_sessions"

    # Auto-incremented primary key.
    session_id = Column(Integer, primary_key=True, autoincrement=True)

    # The user who initiated this session.
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Language the article is in.
    language_id = Column(
        Integer,
        ForeignKey("languages.language_id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Source URL of the article, or null when plain text was submitted directly.
    source_url = Column(Text, nullable=True)

    # Article headline / title extracted from the HTML <title> or <h1>.
    title = Column(String(500), nullable=True)

    # Structured tokenised content: list of paragraph objects.
    content_json = Column(JSONB, nullable=True)

    # Timestamp when this session was created.
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user = relationship("User", back_populates="reading_sessions")
    language = relationship("Language")

    def __repr__(self) -> str:
        return (
            f"<ReadingSession session_id={self.session_id} "
            f"url={self.source_url!r}>"
        )
