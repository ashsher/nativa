"""
app/models/speaking.py — SpeakingMatch ORM model.

Records a speaking-partner pairing between two users learning the same
language.  The actual signalling (call setup) happens via Firebase Firestore;
this table provides a persistent audit trail.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SpeakingMatch(Base):
    """
    A speaking partner match between two Nativa users.

    Table name: speaking_matches
    """

    __tablename__ = "speaking_matches"

    # Auto-incremented primary key.
    match_id = Column(Integer, primary_key=True, autoincrement=True)

    # The user who initiated the match request.
    initiator_user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The user who was matched (the partner).
    partner_user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The language they are matched to practise together.
    language_id = Column(
        Integer,
        ForeignKey("languages.language_id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Jaccard similarity score that led to this pairing (0.0 – 1.0).
    # Stored as a string to avoid float precision issues in display.
    similarity_score = Column(String(10), nullable=True)

    # Current status of the match: "pending", "active", "ended", "declined".
    status = Column(String(50), default="pending", nullable=False)

    # Firestore document ID for the signalling channel between the two users.
    firestore_doc_id = Column(String(200), nullable=True)

    # When this match record was created.
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    initiator = relationship(
        "User", foreign_keys=[initiator_user_id]
    )
    partner = relationship(
        "User", foreign_keys=[partner_user_id]
    )
    language = relationship("Language")

    def __repr__(self) -> str:
        return (
            f"<SpeakingMatch match_id={self.match_id} "
            f"initiator={self.initiator_user_id} "
            f"partner={self.partner_user_id}>"
        )
