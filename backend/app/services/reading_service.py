"""
app/services/reading_service.py — Article reading session processing service.

Accepts either a URL (fetches and parses HTML) or plain text, tokenises the
content paragraph-by-paragraph, persists a ReadingSession, and returns a
structured JSON payload ready for the interactive reader.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sessions import ReadingSession
from app.utils.tokeniser import tokenise_text

# ---------------------------------------------------------------------------
# HTML tags whose contents should be discarded during extraction.
# These typically contain navigation, ads, or non-article content.
# ---------------------------------------------------------------------------
_NOISE_TAGS = [
    "nav", "header", "footer", "aside", "script",
    "style", "noscript", "form", "button", "iframe",
    "figure", "figcaption", "advertisement",
]

# Minimum length of a paragraph to be included in the output.
# Filters out very short fragments like section headings or metadata lines.
_MIN_PARAGRAPH_LENGTH = 40


async def _fetch_article(url: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Fetch a URL with httpx and extract the main article text using BeautifulSoup.

    Returns:
        Tuple of (plain_text, title, source_url).
        plain_text is the cleaned article body (multi-paragraph string).
        title is the page title (may be None).
        source_url is the final URL after redirects.
    """
    # ---------------------------------------------------------------------------
    # URL allowlist: only http and https schemes are permitted to prevent
    # SSRF attacks targeting internal services via file://, ftp://, etc.
    # ---------------------------------------------------------------------------
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat http yoki https manbalari qo'llab-quvvatlanadi.",
        )
    if not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Noto'g'ri URL manzil.",
        )

    # --- Fetch the page HTML ---
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NativaBot/1.0)"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Maqolani yuklab bo'lmadi: {exc}",
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Veb-sahifadan xato javob: {exc.response.status_code}",
        )

    # --- Parse HTML with BeautifulSoup ---
    soup = BeautifulSoup(response.text, "lxml")

    # Extract the page title for display.
    title_tag = soup.find("title")
    title: Optional[str] = title_tag.get_text(strip=True) if title_tag else None

    # --- Remove noise elements in-place ---
    for tag_name in _NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # --- Try to find the <article> element first; fall back to <body> ---
    article_node = soup.find("article") or soup.find("main") or soup.body
    if article_node is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sahifadan matn ajratib bo'lmadi.",
        )

    # --- Extract paragraphs ---
    paragraphs: List[str] = []
    for p_tag in article_node.find_all("p"):
        text = p_tag.get_text(separator=" ", strip=True)
        if len(text) >= _MIN_PARAGRAPH_LENGTH:
            paragraphs.append(text)

    plain_text = "\n\n".join(paragraphs)
    return plain_text, title, str(response.url)


def _is_url(content: str) -> bool:
    """Return True if *content* looks like an http/https URL."""
    return content.startswith("http://") or content.startswith("https://")


def _tokenise_paragraphs(text: str) -> List[Dict[str, Any]]:
    """
    Split *text* into paragraphs and tokenise each one.

    Returns a list of paragraph objects matching ParagraphSchema.
    """
    result: List[Dict[str, Any]] = []
    # Split on blank lines (double newline) to get paragraph boundaries.
    raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    for idx, paragraph in enumerate(raw_paragraphs):
        tokens = tokenise_text(paragraph)
        result.append(
            {
                "paragraph_index": idx,
                "text": paragraph,
                "tokens": tokens,
            }
        )
    return result


async def process_reading(
    content: str,
    language_id: int,
    user_id: int,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Full pipeline for processing an article URL or plain text.

    Steps:
      1. Determine whether content is a URL or plain text.
      2. If URL: fetch and extract article text via BeautifulSoup.
      3. If plain text: use directly.
      4. Split into paragraphs and tokenise each paragraph.
      5. Persist ReadingSession to the database.
      6. Return structured payload.

    Args:
        content:     URL (http/https) or raw article text.
        language_id: ID of the language being studied.
        user_id:     Internal user ID for DB persistence.
        db:          Async database session.

    Returns:
        Dict matching ReadingProcessResponse schema.
    """
    title: Optional[str] = None
    source_url: Optional[str] = None

    # --- Step 1 & 2: Fetch if URL ---
    if _is_url(content):
        plain_text, title, source_url = await _fetch_article(content)
    else:
        # --- Step 3: Use plain text directly ---
        plain_text = content

    # Sanity check — make sure we have something to work with.
    if not plain_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Matn bo'sh. Iltimos, maqola yoki matn kiriting.",
        )

    # --- Step 4: Tokenise paragraphs ---
    paragraphs = _tokenise_paragraphs(plain_text)

    # --- Step 5: Persist ReadingSession ---
    session = ReadingSession(
        user_id=user_id,
        language_id=language_id,
        source_url=source_url,
        title=title,
        content_json=paragraphs,
    )
    db.add(session)
    await db.flush()  # Populate session_id.

    # --- Step 6: Return structured payload ---
    return {
        "session_id": session.session_id,
        "source_url": source_url,
        "title": title,
        "paragraphs": paragraphs,
    }
