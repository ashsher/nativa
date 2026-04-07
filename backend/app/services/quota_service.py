"""
app/services/quota_service.py — Freemium daily usage quota enforcement.

Free-tier users are limited to a fixed number of actions per day.
Premium users have unlimited access.

Redis is used as the primary enforcement layer because:
  - Hash-based atomic increments are O(1) and thread-safe.
  - Per-key TTL of 86400 s (24 hours) resets counts automatically.

Free-tier daily limits:
  srs_count:      10  (SRS flash-card reviews)
  ai_count:       10  (AI grammar explanation queries)
  speaking_count:  5  (Speaking-partner connection attempts)
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status

from app.utils.redis_client import expire, hget, hincrby

# -------------------------------------------------------------------------
# Free-tier daily limits per quota type.
# -------------------------------------------------------------------------
_FREE_LIMITS: dict[str, int] = {
    "srs_count": 10,
    "ai_count": 10,
    "speaking_count": 5,
}

# How long (in seconds) the Redis hash key lives before automatic reset.
_TTL_SECONDS = 86_400  # 24 hours

# Human-readable Uzbek label map for error messages.
_QUOTA_LABELS: dict[str, str] = {
    "srs_count": "takrorlash",
    "ai_count": "AI so'rov",
    "speaking_count": "nutq mashqi",
}


def _quota_key(user_id: int) -> str:
    """
    Build the Redis hash key for today's quota for *user_id*.

    Format: "quota:{user_id}:{YYYY-MM-DD}"
    A new key is created each calendar day, which effectively resets counters.
    """
    today = date.today().isoformat()
    return f"quota:{user_id}:{today}"


async def check_and_increment(
    user_id: int,
    quota_type: str,
    is_premium: bool,
) -> int:
    """
    Check whether the user is within their daily quota and increment the counter.

    Steps:
      1. Premium users bypass all limits — increment the counter for analytics
         and return immediately.
      2. Build the Redis hash key for today: "quota:{user_id}:{date}".
      3. Atomically increment the field in the hash.
      4. Set the TTL on the key (only takes effect if the key is new, so we
         call EXPIRE after every increment to ensure it is always set).
      5. Compare the new value against the free-tier limit.
      6. If over limit: raise HTTP 429 with an Uzbek error message.
      7. Return the new counter value.

    Args:
        user_id:    Internal user ID.
        quota_type: One of "srs_count", "ai_count", "speaking_count".
        is_premium: Whether the user has an active premium subscription.

    Returns:
        The new value of the counter after the increment.

    Raises:
        HTTPException 429 if the free user has exceeded their daily limit.
    """
    key = _quota_key(user_id)

    # --- Step 1: Premium bypass ---
    if is_premium:
        # Still increment for analytics, but do not enforce limits.
        await hincrby(key, quota_type, 1)
        await expire(key, _TTL_SECONDS)
        return -1  # Sentinel: unlimited.

    # --- Step 2 & 3: Atomically increment the counter ---
    new_value = await hincrby(key, quota_type, 1)

    # --- Step 4: Ensure the key expires at the end of the day ---
    await expire(key, _TTL_SECONDS)

    # --- Step 5: Retrieve the free-tier limit ---
    limit = _FREE_LIMITS.get(quota_type, 0)
    label = _QUOTA_LABELS.get(quota_type, quota_type)

    # --- Step 6: Enforce limit ---
    if new_value > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Bugungi {label} limitingiz tugadi ({limit} ta). "
                "Cheksiz foydalanish uchun Premium obunasini oling."
            ),
        )

    # --- Step 7: Return new count ---
    return new_value


async def get_quota_status(user_id: int) -> dict[str, int]:
    """
    Return the current usage counts for today without incrementing.

    Useful for displaying remaining quota to the user in the UI.

    Returns:
        Dict with keys matching _FREE_LIMITS and their current usage values.
    """
    key = _quota_key(user_id)
    result: dict[str, int] = {}
    for quota_type in _FREE_LIMITS:
        raw = await hget(key, quota_type)
        result[quota_type] = int(raw) if raw else 0
    return result
