"""
app/models/language.py — Language catalogue ORM model.

Stores the languages that Nativa supports.  Each user learning session is
associated with one of these entries.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer, String

from app.database import Base


class Language(Base):
    """
    Represents a supported learning language.

    Table name: languages
    """

    __tablename__ = "languages"

    # Primary key — auto-incremented integer.
    language_id = Column(Integer, primary_key=True, autoincrement=True)

    # ISO 639-1 two-letter language code (e.g. "en", "de", "fr").
    # Unique so we can safely look up by code.
    code = Column(String(10), unique=True, nullable=False)

    # Human-readable name in English (e.g. "English", "German").
    name_en = Column(String(100), nullable=False)

    # Human-readable name in Uzbek — shown in the app's Uzbek UI.
    name_uz = Column(String(100), nullable=False)

    # Soft-delete flag: set False to hide a language without removing data.
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Language code={self.code} name_en={self.name_en}>"
