"""
app/models/__init__.py

Import every ORM model here so that:
  1. Alembic's autogenerate can discover all tables.
  2. app/main.py startup can call Base.metadata.create_all in a single import.
"""

from app.models.language import Language  # noqa: F401
from app.models.user import User, UserLanguage  # noqa: F401
from app.models.vocabulary import UserVocabulary  # noqa: F401
from app.models.sessions import VideoSession, ReadingSession  # noqa: F401
from app.models.ai_query import AIQuery  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.quota import UsageQuota  # noqa: F401
from app.models.speaking import SpeakingMatch  # noqa: F401
