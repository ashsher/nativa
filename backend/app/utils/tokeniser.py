"""
app/utils/tokeniser.py — Word-level tokeniser for article and subtitle text.

The tokeniser splits text into tokens while preserving the original display
form of each token (including surrounding punctuation) alongside a normalised
lookup form (lowercase, punctuation stripped) that is used for dictionary
and translation API calls.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Regular expression that matches one "word unit":
#   - One or more Unicode word characters (\w includes letters, digits, _)
#   - Optionally followed by an apostrophe + more word chars (e.g. "it's", "don't")
# This keeps contractions together as a single token.
# ---------------------------------------------------------------------------
_WORD_RE = re.compile(r"\w+(?:'\w+)*", re.UNICODE)


def _strip_punctuation(text: str) -> str:
    """
    Remove leading/trailing punctuation and whitespace from a string.

    We use unicodedata to handle multi-script punctuation correctly rather
    than a hard-coded ASCII character list.
    """
    # Strip characters whose Unicode category starts with 'P' (punctuation)
    # or 'S' (symbol), or which are whitespace.
    result = []
    for ch in text:
        cat = unicodedata.category(ch)
        # Keep letters (L*), digits (N*), and the modifier letter apostrophe.
        if cat.startswith("L") or cat.startswith("N") or ch == "'":
            result.append(ch)
    return "".join(result)


def tokenise_text(text: str) -> List[Dict[str, Any]]:
    """
    Split *text* into word-level tokens.

    Each token is a dict with:
        word    (str)  — lowercase lookup form, punctuation stripped
        display (str)  — original substring as it appears in the source text
        index   (int)  — zero-based position of this token in the token list

    Non-word characters (spaces, punctuation, numbers-only fragments) are
    silently skipped — they are not included in the returned list.

    Example
    -------
    >>> tokenise_text("Hello, world!")
    [
        {"word": "hello", "display": "Hello", "index": 0},
        {"word": "world", "display": "world", "index": 1},
    ]
    """
    tokens: List[Dict[str, Any]] = []

    # Use a dedicated counter that only increments when a token is actually
    # kept.  This ensures index values are contiguous in the output list
    # even when some regex matches are discarded (empty word after stripping).
    token_index: int = 0

    for match in _WORD_RE.finditer(text):
        # The matched string as it appears in the source.
        display: str = match.group()

        # Normalised lookup form: lowercase, punctuation stripped.
        word: str = _strip_punctuation(display).lower()

        # Skip tokens that reduce to an empty string after stripping
        # (e.g. a bare apostrophe or a pure-digit sequence used as a number).
        if not word:
            continue

        tokens.append(
            {
                "word": word,
                "display": display,
                "index": token_index,
            }
        )
        token_index += 1

    return tokens
