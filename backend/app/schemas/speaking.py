"""
app/schemas/speaking.py — Pydantic schemas for the speaking-partner endpoints.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SpeakingMatchResponse(BaseModel):
    """A single candidate speaking partner returned by GET /api/speaking/matches."""

    # Internal user ID of the candidate partner.
    user_id: int

    # First name of the candidate (used for display in the UI).
    first_name: Optional[str] = None

    # Telegram @username of the candidate (null if they have none).
    username: Optional[str] = None

    # Jaccard similarity score (0.0–1.0) computed from shared interests/hobbies.
    # Higher is a better match.
    similarity_score: float = Field(..., ge=0.0, le=1.0)

    # Interests the two users have in common — shown in the match card.
    shared_interests: List[str] = Field(default_factory=list)

    # Hobbies the two users have in common — shown in the match card.
    shared_hobbies: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class SpeakingConnectRequest(BaseModel):
    """Request body for POST /api/speaking/connect."""

    # ID of the partner the current user wants to connect with.
    partner_user_id: int = Field(..., description="User ID of the chosen partner")

    # Language they intend to practise together.
    language_id: int = Field(..., description="Language ID for the session")


class SpeakingConnectResponse(BaseModel):
    """Response after creating a speaking match."""

    # ID of the newly created SpeakingMatch record.
    match_id: int

    # Telegram deep-link the user can share/tap to start a chat with the partner.
    # Format: https://t.me/{partner_username}
    telegram_deep_link: Optional[str] = None

    # Firestore document ID for real-time signalling (used by the WebRTC layer).
    firestore_doc_id: Optional[str] = None

    # Human-readable confirmation message in Uzbek.
    message: str
