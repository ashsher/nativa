"""
app/services/srs_service.py — SM-2 Spaced Repetition System algorithm.

Implements the SuperMemo 2 (SM-2) algorithm for scheduling vocabulary flash-card
reviews.  SM-2 adjusts the review interval and ease factor based on how well
the user recalled the card (rating 0–5).

Reference: https://www.supermemo.com/en/blog/application-of-a-computer-to-improve-the-results-obtained-in-working-with-the-supermemo-method
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocabulary import UserVocabulary
from app.services import quota_service

# SM-2 constants.
_MIN_EASE_FACTOR = 1.3   # Ease factor is clamped to this minimum.
_DEFAULT_EASE_FACTOR = 2.5


async def review(
    vocab_id: int,
    rating: int,
    user_id: int,
    is_premium: bool,
    db: AsyncSession,
) -> UserVocabulary:
    """
    Apply the SM-2 algorithm to a vocabulary card and persist the result.

    SM-2 Algorithm Steps:
      1. Load the vocabulary card; verify it belongs to the requesting user.
      2. Enforce daily SRS quota via quota_service.
      3. If rating < 3: the user failed to recall — reset interval to 1 day
         and repetition_count to 0 (card will be shown again soon).
      4. If rating >= 3: the user recalled successfully —
         a. Determine new interval based on repetition_count:
            - 1st successful review  → 1 day
            - 2nd successful review  → 6 days
            - Subsequent reviews     → round(previous_interval × ease_factor)
         b. Update ease_factor using the SM-2 formula:
            EF' = EF + (0.1 - (5 - rating) × (0.08 + (5 - rating) × 0.02))
         c. Clamp ease_factor to a minimum of 1.3.
         d. Increment repetition_count.
      5. Set next_review_date = today + new interval.
      6. Persist changes.
      7. Return the updated card.

    Args:
        vocab_id:   Primary key of the card to review.
        rating:     SM-2 quality score 0–5 (0 = blackout, 5 = perfect).
        user_id:    Internal user ID (ownership check).
        is_premium: Whether the user holds an active premium subscription.
        db:         Async database session.

    Returns:
        The updated UserVocabulary ORM object.
    """
    # --- Step 1: Load and verify card ownership ---
    result = await db.execute(
        select(UserVocabulary).where(
            UserVocabulary.vocab_id == vocab_id,
            UserVocabulary.user_id == user_id,
        )
    )
    card: UserVocabulary | None = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="So'z kartochkasi topilmadi.",
        )

    # --- Step 2: Check and increment SRS daily quota ---
    await quota_service.check_and_increment(user_id, "srs_count", is_premium)

    today = date.today()

    if rating < 3:
        # --- Step 3: Failed recall — reset schedule ---
        # The card goes back to the beginning of the schedule.
        card.interval_days = 1
        card.repetition_count = 0
        # Keep the current ease_factor — it will be penalised on the next pass.

    else:
        # --- Step 4a: Calculate new interval ---
        if card.repetition_count == 0:
            # First ever successful review.
            new_interval = 1
        elif card.repetition_count == 1:
            # Second successful review.
            new_interval = 6
        else:
            # Subsequent reviews — multiply previous interval by ease factor.
            new_interval = round(card.interval_days * card.ease_factor)

        card.interval_days = new_interval

        # --- Step 4b: Update ease factor with SM-2 formula ---
        # This formula rewards ratings close to 5 and penalises lower ratings.
        new_ef = (
            card.ease_factor
            + (0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02))
        )

        # --- Step 4c: Clamp ease_factor to minimum ---
        card.ease_factor = max(_MIN_EASE_FACTOR, new_ef)

        # --- Step 4d: Increment successful repetition counter ---
        card.repetition_count += 1

    # --- Step 5: Set next review date ---
    card.next_review_date = today + timedelta(days=card.interval_days)

    # --- Step 6: Persist ---
    # The session commit happens in get_db(); flush here so we can read
    # the updated state before the response is sent.
    await db.flush()

    # --- Step 7: Return updated card ---
    return card
