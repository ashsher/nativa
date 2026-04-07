"""
app/schemas/vocabulary.py — Pydantic schemas for vocabulary and SRS endpoints.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class VocabularyCreate(BaseModel):
    """Payload sent when adding a new word to the vocabulary deck."""

    # Internal language ID the word belongs to.
    language_id: int = Field(..., description="ID of the language being studied")

    # The target-language word to memorise (stored lowercase).
    word: str = Field(..., max_length=200, description="Word in the target language")

    # Native-language translation (Uzbek).
    translation: str = Field(..., description="Translation in the user's native language")

    # Example sentences — each entry has 'sentence' and 'translation' keys.
    example_sentences: Optional[List[Dict[str, Any]]] = Field(
        None, description="Optional list of example sentence objects"
    )


class SRSReviewRequest(BaseModel):
    """Payload sent when the user submits their recall quality rating."""

    # ID of the vocabulary card being reviewed.
    vocab_id: int = Field(..., description="Primary key of the vocabulary card")

    # SM-2 recall quality: 0 = complete blackout, 5 = perfect recall.
    rating: int = Field(..., ge=0, le=5, description="SM-2 quality rating 0–5")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class VocabularyResponse(BaseModel):
    """A single vocabulary card as returned by the API."""

    # Primary key.
    vocab_id: int

    # Language ID this word belongs to.
    language_id: int

    # The target-language word.
    word: str

    # Native-language translation.
    translation: str

    # URL to the MP3 pronunciation file on Cloudflare R2.
    pronunciation_url: Optional[str] = None

    # List of example sentence objects.
    example_sentences: Optional[List[Dict[str, Any]]] = None

    # Current SM-2 ease factor.
    ease_factor: float

    # Current interval in days.
    interval_days: int

    # Date of next scheduled review.
    next_review_date: date

    # Total successful review count.
    repetition_count: int

    class Config:
        from_attributes = True


class SRSReviewResponse(BaseModel):
    """Result returned after a successful SRS review submission."""

    # The updated vocabulary card.
    vocab: VocabularyResponse

    # Human-readable message in Uzbek confirming the review result.
    message: str
