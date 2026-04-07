"""
app/models/payment.py — Payment ORM model.

Tracks Telegram Stars premium subscription payments so we can verify,
audit, and replay them if needed.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Payment(Base):
    """
    A single premium subscription payment via Telegram Stars.

    Table name: payments
    """

    __tablename__ = "payments"

    # Auto-incremented primary key.
    payment_id = Column(Integer, primary_key=True, autoincrement=True)

    # The user who made the payment.
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Telegram Stars transaction reference returned by the payment provider.
    transaction_ref = Column(String(200), unique=True, nullable=False)

    # Number of Telegram Stars paid.
    stars_amount = Column(Numeric(10, 2), nullable=False)

    # Current payment status: "pending", "verified", "failed", "refunded".
    status = Column(String(50), default="pending", nullable=False)

    # UTC timestamp of when the payment record was created.
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # UTC timestamp of when the payment was successfully verified.
    verified_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Optional note — e.g. error message from failed verification.
    notes = Column(Text, nullable=True)

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user = relationship("User", back_populates="payments")

    def __repr__(self) -> str:
        return (
            f"<Payment payment_id={self.payment_id} "
            f"status={self.status} user_id={self.user_id}>"
        )
