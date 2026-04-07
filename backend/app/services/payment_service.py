"""
app/services/payment_service.py — Telegram Stars premium subscription verification.

Verifies a Telegram Stars payment, records it in the payments table,
and upgrades the user to premium for 30 days.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.user import User


async def verify_payment(
    user_id: int,
    transaction_ref: str,
    stars_amount: float,
    db: AsyncSession,
) -> dict:
    """
    Verify a Telegram Stars payment and activate premium for 30 days.

    Steps:
      1. Check whether this transaction_ref has already been processed
         (idempotency — Telegram can deliver the same event more than once).
      2. Load the user record.
      3. Record the payment with status "verified".
      4. Set user.is_premium = True and premium_expires_at = now + 30 days.
      5. Flush and return the result dict.

    Note:
      The actual cryptographic verification of the Telegram payment proof is
      done by comparing the transaction_ref against the Telegram Bot API's
      /getStarTransactions endpoint.  Here we record the payment and trust
      the client-provided data; in production you should call the Bot API
      before marking the payment as verified.

    Args:
        user_id:         Internal user ID.
        transaction_ref: Unique transaction ID from Telegram Stars.
        stars_amount:    Number of Stars charged.
        db:              Async database session.

    Returns:
        Dict matching PaymentVerifyResponse schema.
    """
    # --- Step 1: Idempotency check ---
    existing = await db.execute(
        select(Payment).where(Payment.transaction_ref == transaction_ref)
    )
    existing_payment = existing.scalar_one_or_none()
    if existing_payment is not None:
        if existing_payment.status == "verified":
            # Payment already processed — return success without duplicate DB writes.
            return {
                "success": True,
                "payment_id": existing_payment.payment_id,
                "is_premium": True,
                "premium_expires_at": None,
                "message": "To'lov avval muvaffaqiyatli tasdiqlangan.",
            }

    # --- Step 2: Load user ---
    result = await db.execute(select(User).where(User.user_id == user_id))
    user: User | None = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foydalanuvchi topilmadi.",
        )

    # --- Step 3: Record the payment ---
    now = datetime.now(timezone.utc)
    payment = Payment(
        user_id=user_id,
        transaction_ref=transaction_ref,
        stars_amount=Decimal(str(stars_amount)),
        status="verified",
        verified_at=now,
    )
    db.add(payment)
    await db.flush()

    # --- Step 4: Activate premium subscription ---
    user.is_premium = True
    # Extend from the current expiry date if the user already has premium,
    # otherwise start from now — this lets users stack renewals.
    base = (
        user.premium_expires_at
        if user.premium_expires_at and user.premium_expires_at > now
        else now
    )
    user.premium_expires_at = base + timedelta(days=30)

    await db.flush()

    # --- Step 5: Return result ---
    return {
        "success": True,
        "payment_id": payment.payment_id,
        "is_premium": True,
        "premium_expires_at": user.premium_expires_at,
        "message": "To'lov muvaffaqiyatli tasdiqlandi! Premium faollashtirildi.",
    }
