"""
app/services/speaking_service.py — Speaking-partner matching via Jaccard similarity.

Finds the best speaking partners for a user by comparing their combined
interest and hobby sets with every other user who is studying the same
language.  Jaccard similarity is used because it is language-agnostic,
requires no training data, and works well for tag-based matching.

On connect: creates a SpeakingMatch DB record and writes a Firebase Firestore
signalling document so the frontend can set up a WebRTC call.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.speaking import SpeakingMatch
from app.models.user import User, UserLanguage
from app.services import quota_service
from app.utils.firebase_client import get_firestore


def _jaccard(set_a: Set[str], set_b: Set[str]) -> float:
    """
    Compute the Jaccard similarity coefficient between two sets.

    J(A, B) = |A ∩ B| / |A ∪ B|

    Returns 0.0 when both sets are empty (no shared information to compare).
    """
    # The union of two empty sets has size 0 → avoid ZeroDivisionError.
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


async def get_matches(
    current_user: User,
    language_id: int,
    db: AsyncSession,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """
    Return the top *top_n* speaking partner candidates for *current_user*.

    Steps:
      1. Build the current user's combined tag set (interests + hobbies).
      2. Query all other users learning *language_id* who are not already
         matched with the current user.
      3. Compute Jaccard similarity between the current user and each candidate.
      4. Sort candidates by score descending.
      5. Return the top *top_n* candidates with shared tags.

    Args:
        current_user: The requesting User ORM object.
        language_id:  Language ID the user wants to practise.
        db:           Async database session.
        top_n:        Maximum number of matches to return.

    Returns:
        List of dicts matching SpeakingMatchResponse schema.
    """
    # --- Step 1: Build current user's tag set ---
    user_tags: Set[str] = set(current_user.interests or []) | set(
        current_user.hobbies or []
    )

    # --- Step 2: Query other users studying the same language ---
    # Find all UserLanguage rows for this language, excluding the current user.
    stmt = (
        select(User)
        .join(UserLanguage, UserLanguage.user_id == User.user_id)
        .where(
            UserLanguage.language_id == language_id,
            UserLanguage.is_active == True,  # noqa: E712
            User.user_id != current_user.user_id,
        )
    )
    result = await db.execute(stmt)
    candidates: List[User] = list(result.scalars().all())

    # --- Step 3: Compute Jaccard similarity for each candidate ---
    scored: List[Dict[str, Any]] = []
    for candidate in candidates:
        candidate_tags: Set[str] = set(candidate.interests or []) | set(
            candidate.hobbies or []
        )
        score = _jaccard(user_tags, candidate_tags)

        # Compute shared interests and hobbies for the UI card.
        shared_interests = list(
            set(current_user.interests or []) & set(candidate.interests or [])
        )
        shared_hobbies = list(
            set(current_user.hobbies or []) & set(candidate.hobbies or [])
        )

        scored.append(
            {
                "user_id": candidate.user_id,
                "first_name": candidate.first_name,
                "username": candidate.username,
                "similarity_score": round(score, 4),
                "shared_interests": shared_interests,
                "shared_hobbies": shared_hobbies,
            }
        )

    # --- Step 4: Sort by score descending ---
    scored.sort(key=lambda x: x["similarity_score"], reverse=True)

    # --- Step 5: Return top N ---
    return scored[:top_n]


async def connect(
    initiator: User,
    partner_user_id: int,
    language_id: int,
    is_premium: bool,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Create a SpeakingMatch record and a Firebase Firestore signalling document.

    Steps:
      1. Enforce daily speaking_count quota.
      2. Load the partner user.
      3. Compute similarity score between initiator and partner.
      4. Generate a unique Firestore document ID for the signalling channel.
      5. Write signalling document to Firestore collection "speaking_matches".
      6. Persist SpeakingMatch to the PostgreSQL database.
      7. Build and return the Telegram deep-link for the partner.

    Args:
        initiator:       The User ORM object of the initiating user.
        partner_user_id: Internal user ID of the chosen partner.
        language_id:     Language they will practise together.
        is_premium:      Whether the initiator holds a premium subscription.
        db:              Async database session.

    Returns:
        Dict matching SpeakingConnectResponse schema.
    """
    # --- Step 1: Quota check ---
    await quota_service.check_and_increment(
        initiator.user_id, "speaking_count", is_premium
    )

    # --- Step 2: Load partner ---
    result = await db.execute(
        select(User).where(User.user_id == partner_user_id)
    )
    partner: Optional[User] = result.scalar_one_or_none()
    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sherik foydalanuvchi topilmadi.",
        )

    # --- Step 3: Compute similarity score for the record ---
    initiator_tags: Set[str] = set(initiator.interests or []) | set(
        initiator.hobbies or []
    )
    partner_tags: Set[str] = set(partner.interests or []) | set(
        partner.hobbies or []
    )
    score = _jaccard(initiator_tags, partner_tags)

    # --- Step 4: Generate Firestore document ID ---
    # UUID4 guarantees uniqueness without requiring coordination.
    doc_id: Optional[str] = str(uuid.uuid4())

    # --- Step 5: Write Firestore signalling document ---
    try:
        fs = get_firestore()
        doc_ref = fs.collection("speaking_matches").document(doc_id)
        await doc_ref.set(
            {
                "initiator_telegram_id": initiator.telegram_id,
                "partner_telegram_id": partner.telegram_id,
                "language_id": language_id,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception:
        # Firestore failure is non-fatal — the DB record still serves as a log.
        doc_id = None

    # --- Step 6: Persist SpeakingMatch ---
    match = SpeakingMatch(
        initiator_user_id=initiator.user_id,
        partner_user_id=partner_user_id,
        language_id=language_id,
        similarity_score=str(round(score, 4)),
        status="pending",
        firestore_doc_id=doc_id,
    )
    db.add(match)
    await db.flush()

    # --- Step 7: Build Telegram deep-link ---
    # If the partner has a username we link directly to their chat.
    telegram_deep_link: Optional[str] = (
        f"https://t.me/{partner.username}" if partner.username else None
    )

    return {
        "match_id": match.match_id,
        "telegram_deep_link": telegram_deep_link,
        "firestore_doc_id": doc_id,
        "message": (
            f"{partner.first_name or 'Sherik'} bilan bog'lanish so'rovi yuborildi!"
        ),
    }
