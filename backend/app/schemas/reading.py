"""
app/schemas/reading.py — Pydantic schemas for article reading endpoints.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Nested schemas
# ---------------------------------------------------------------------------

class WordTokenSchema(BaseModel):
    """A single tokenised word within a paragraph."""

    # Canonical lowercase form with punctuation stripped — used for API lookups.
    word: str = Field(..., description="Lookup form (lowercase, stripped punctuation)")

    # Original display form preserving capitalisation and surrounding punctuation.
    display: str = Field(..., description="Original display form")

    # Zero-based position of this token within its parent paragraph.
    index: int = Field(..., description="Token position within the paragraph")


class ParagraphSchema(BaseModel):
    """A single paragraph extracted from the article."""

    # Zero-based index of this paragraph within the article.
    paragraph_index: int = Field(..., description="Paragraph position in the article")

    # Raw paragraph text before tokenisation.
    text: str = Field(..., description="Full paragraph text")

    # List of tokenised words within this paragraph.
    tokens: List[WordTokenSchema] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ReadingProcessRequest(BaseModel):
    """Request body for POST /api/reading/process."""

    # Either a URL to fetch or raw article text — the service inspects the value.
    # If it looks like a URL (starts with http), the service fetches it; otherwise
    # it is treated as plain text.
    content: str = Field(
        ...,
        description="Article URL (http/https) or plain text to tokenise"
    )

    # Language ID so the session can be attributed to the correct language.
    language_id: int = Field(..., description="ID of the target learning language")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ReadingProcessResponse(BaseModel):
    """Full response after processing an article."""

    # Internal DB primary key of the newly created ReadingSession.
    session_id: int

    # Source URL if the content was fetched from the web; null for plain text.
    source_url: Optional[str] = None

    # Article title extracted from <title> or <h1> (null for plain text input).
    title: Optional[str] = None

    # Tokenised paragraphs ready for the interactive reader.
    paragraphs: List[ParagraphSchema] = Field(default_factory=list)
