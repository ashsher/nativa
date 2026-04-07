"""
app/models/vocabulary.py — UserVocabulary ORM model.

Stores flash-card vocabulary items per user.  Each row embeds the SM-2
spaced-repetition fields (ease_factor, interval_days, next_review_date,
repetition_count) so the SRS algorithm can operate directly on the model.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UserVocabulary(Base):
    """
    A single vocabulary flash-card belonging to a user.

    Table name: user_vocabulary
    """

    __tablename__ = "user_vocabulary"

    # Auto-incremented primary key.
    vocab_id = Column(Integer, primary_key=True, autoincrement=True)

    # Owning user — cascade delete so cards are removed when the user is deleted.
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Language this word belongs to (determines the TTS voice, etc.).
    language_id = Column(
        Integer,
        ForeignKey("languages.language_id", ondelete="RESTRICT"),
        nullable=False,
    )

    # The target-language word being studied (stored lowercase for consistency).
    word = Column(String(200), nullable=False)

    # Translation of the word in the user's native language (Uzbek).
    translation = Column(Text, nullable=False)

    # Public URL of the MP3 pronunciation file stored in Cloudflare R2.
    # Null until the TTS service generates it.
    pronunciation_url = Column(Text, nullable=True)

    # JSONB array of example sentences: [{"sentence": "...", "translation": "..."}]
    example_sentences = Column(JSONB, nullable=True, default=list)

    # SM-2 ease factor — starts at 2.5 and adjusts after each review.
    # Higher = card appears less frequently.
    ease_factor = Column(Float, default=2.5, nullable=False)

    # SM-2 interval — number of days until the next scheduled review.
    interval_days = Column(Integer, default=1, nullable=False)

    # The date when this card is next due for review.
    next_review_date = Column(Date, server_default=func.current_date(), nullable=False)

    # Total number of times this card has been reviewed successfully (rating >= 3).
    repetition_count = Column(Integer, default=0, nullable=False)

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user = relationship("User", back_populates="vocabulary")
    language = relationship("Language")

    def __repr__(self) -> str:
        return f"<UserVocabulary word={self.word} user_id={self.user_id}>"
