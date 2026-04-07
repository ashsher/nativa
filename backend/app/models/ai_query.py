"""
app/models/ai_query.py — AIQuery ORM model.

Logs every Gemini grammar-explanation request so we can track usage,
enforce per-user daily limits, and debug AI responses.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AIQuery(Base):
    """
    A single AI explanation query made by a user.

    Table name: ai_queries
    """

    __tablename__ = "ai_queries"

    # Auto-incremented primary key.
    query_id = Column(Integer, primary_key=True, autoincrement=True)

    # The user who made this query.
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The input text (word, phrase, or sentence) submitted by the user.
    input_text = Column(Text, nullable=False)

    # The explanation text returned by Gemini.
    response_text = Column(Text, nullable=True)

    # Number of tokens consumed by this query (input + output).
    # Used for cost monitoring.
    token_count = Column(Integer, nullable=True)

    # Timestamp when the query was made.
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user = relationship("User", back_populates="ai_queries")

    def __repr__(self) -> str:
        return (
            f"<AIQuery query_id={self.query_id} "
            f"user_id={self.user_id}>"
        )
