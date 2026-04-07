"""
app/schemas/payment.py — Pydantic schemas for premium subscription / payment endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PaymentStatusResponse(BaseModel):
    """Response for GET /api/payment/status — returns the user's current plan."""

    # Whether the user currently holds an active premium subscription.
    is_premium: bool

    # When the premium subscription expires; null if the user is on the free tier.
    premium_expires_at: Optional[datetime] = None

    # Human-readable plan label shown in the UI ("Free" or "Premium").
    plan: str = Field(..., description="'free' or 'premium'")


class PaymentVerifyRequest(BaseModel):
    """Request body for POST /api/payment/verify."""

    # Telegram Stars transaction reference provided by the client after payment.
    transaction_ref: str = Field(
        ...,
        max_length=200,
        description="Unique transaction reference from Telegram Stars",
    )

    # Number of Telegram Stars the user claims to have paid.
    stars_amount: float = Field(
        ...,
        gt=0,
        description="Amount of Telegram Stars paid",
    )


class PaymentVerifyResponse(BaseModel):
    """Response returned after verifying a Telegram Stars payment."""

    # Whether the payment was successfully verified.
    success: bool

    # Internal payment record ID.
    payment_id: int

    # Updated premium status after verification.
    is_premium: bool

    # Updated expiry timestamp.
    premium_expires_at: Optional[datetime] = None

    # Confirmation or error message in Uzbek.
    message: str
