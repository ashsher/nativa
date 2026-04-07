"""
app/schemas/ai.py — Pydantic schemas for the AI grammar explanation endpoint.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AIExplainRequest(BaseModel):
    """Request body for POST /api/ai/explain."""

    # The word, phrase, or sentence the user wants explained in Uzbek.
    text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Text to be explained grammatically in Uzbek",
    )

    # Context sentence in which the word or phrase appears (optional).
    # Providing context allows Gemini to give a more accurate explanation.
    context: str = Field(
        default="",
        max_length=2000,
        description="Optional surrounding sentence for better accuracy",
    )

    # Language code of the text being explained (e.g. "en", "de").
    language_code: str = Field(
        default="en",
        max_length=10,
        description="ISO 639-1 code of the target language",
    )


class AIExplainResponse(BaseModel):
    """Response returned by the AI explanation endpoint."""

    # The Gemini-generated explanation text in Uzbek.
    explanation: str = Field(..., description="Grammar explanation in Uzbek")

    # Total tokens consumed by this query (input + output combined).
    # Useful for the client to display cost information.
    token_count: int = Field(
        default=0,
        description="Total tokens used (prompt + completion)",
    )
