"""
app/models/quota.py — UsageQuota ORM model.

Stores the daily quota counters for free-tier users.  Redis is the primary
store for live enforcement (fast), while this table provides an audit trail
and a fallback when Redis is unavailable.
"""

from __future__ import annotations

from sqlalchemy import Column, Date, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UsageQuota(Base):
    """
    Daily usage counters for a single user.

    Table name: usage_quotas
    """

    __tablename__ = "usage_quotas"

    # Composite primary key: one row per user per calendar day.
    quota_id = Column(Integer, primary_key=True, autoincrement=True)

    # The user these counts belong to.
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Calendar date this row covers (server default = today in UTC).
    date = Column(Date, server_default=func.current_date(), nullable=False)

    # Number of SRS flash-card reviews performed today.
    srs_count = Column(Integer, default=0, nullable=False)

    # Number of AI grammar explanation queries performed today.
    ai_count = Column(Integer, default=0, nullable=False)

    # Number of speaking-partner connection attempts today.
    speaking_count = Column(Integer, default=0, nullable=False)

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user = relationship("User", back_populates="usage_quotas")

    def __repr__(self) -> str:
        return (
            f"<UsageQuota user_id={self.user_id} date={self.date} "
            f"srs={self.srs_count} ai={self.ai_count} "
            f"speaking={self.speaking_count}>"
        )
