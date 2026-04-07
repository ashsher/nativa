"""
app/routers/payment.py — Premium subscription payment endpoints.

GET  /api/payment/status          — Check the current user's premium status.
POST /api/payment/verify          — Verify a Telegram Stars payment and activate premium.
GET  /api/payment/create-invoice  — Create a Telegram Stars invoice link.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.payment import (
    PaymentStatusResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
)
from app.services import payment_service

router = APIRouter(prefix="/payment", tags=["payment"])


async def _get_user(request: Request, db: AsyncSession) -> User:
    """Load the full User ORM object for the authenticated request."""
    telegram_id: int = request.state.user["id"]
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        from app.services import auth_service
        user = await auth_service.upsert_user(db, request.state.user)
    return user


@router.get(
    "/status",
    response_model=PaymentStatusResponse,
    summary="Foydalanuvchining premium obuna holatini tekshirish",
)
async def get_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PaymentStatusResponse:
    """
    Return the current premium subscription status for the authenticated user.

    Also checks whether an existing premium subscription has expired and
    automatically downgrades the user to the free tier if it has.
    """
    user = await _get_user(request, db)

    # Auto-expire premium if the subscription has lapsed.
    from datetime import datetime, timezone
    if user.is_premium and user.premium_expires_at:
        if user.premium_expires_at < datetime.now(timezone.utc):
            # Subscription has expired — downgrade to free.
            user.is_premium = False
            await db.flush()

    return PaymentStatusResponse(
        is_premium=user.is_premium,
        premium_expires_at=user.premium_expires_at,
        plan="premium" if user.is_premium else "free",
    )


@router.post(
    "/verify",
    response_model=PaymentVerifyResponse,
    summary="Telegram Stars to'lovini tasdiqlash",
)
async def verify_payment(
    payload: PaymentVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PaymentVerifyResponse:
    """
    Verify a Telegram Stars payment and activate 30-day premium access.

    This endpoint is idempotent: submitting the same transaction_ref twice
    returns a success response without creating duplicate payment records.

    Steps:
      1. Look up the user.
      2. Check for duplicate transaction_ref.
      3. Record the payment.
      4. Set is_premium=True, premium_expires_at=now+30 days.
      5. Return confirmation.

    Raises:
        404 if the authenticated user is not found in the database.
    """
    user = await _get_user(request, db)

    result = await payment_service.verify_payment(
        user_id=user.user_id,
        transaction_ref=payload.transaction_ref,
        stars_amount=payload.stars_amount,
        db=db,
    )

    return result  # type: ignore[return-value]


@router.get(
    "/create-invoice",
    summary="Telegram Stars invoice linkini yaratish",
)
async def create_invoice(
    request: Request,
) -> dict:
    """
    Create a Telegram Stars payment invoice link.

    In a full production implementation this endpoint would call
    Telegram Bot API's createInvoiceLink method (via python-telegram-bot
    Application.bot.create_invoice_link()) to generate a dynamic,
    single-use invoice URL that Telegram's native payment sheet can open.

    The invoice is priced at 200 Telegram Stars (~$2 USD at current rates),
    which grants the user 30 days of Premium access.

    Returns:
        invoice_link   — URL string to pass to Telegram.WebApp.openInvoice()
        amount_stars   — number of Telegram Stars charged (200 ≈ $2)

    Note:
        The transaction_ref field is intentionally omitted here because
        the actual charge ID (telegram_payment_charge_id) is only available
        after the user completes the payment and the successful_payment
        webhook fires. The bot.py handler extracts that ID and POSTs it
        to /api/payment/verify.
    """
    # In production: call Telegram Bot API createInvoiceLink and return the URL.
    # Here we return a placeholder URL suitable for integration testing.
    return {
        # invoice_link is opened by Telegram.WebApp.openInvoice() on the frontend.
        "invoice_link": "https://t.me/invoice/placeholder",
        # 200 Telegram Stars ≈ $2 USD at the time of writing.
        "amount_stars": 200,
    }
