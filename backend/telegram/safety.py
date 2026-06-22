from __future__ import annotations

import re
import unicodedata

from ..app.word_utils import clue_mentions_word, is_valid_word, normalize_word, starts_with_prefix
from ..app.schemas import Language

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

MAX_WORD_LENGTH = 50
MAX_CLUE_LENGTH = 500


def sanitize_text(text: str, max_length: int) -> tuple[str, str | None]:
    """Return (cleaned_text, error_key). error_key is None on success."""
    text = unicodedata.normalize("NFC", text)
    text = _CONTROL_CHARS_RE.sub("", text)
    text = text.strip()
    if not text:
        return "", "word_empty"
    if len(text) > max_length:
        return "", "word_too_long" if max_length == MAX_WORD_LENGTH else "clue_too_long"
    return text, None


def validate_word_input(
    raw: str,
    language: Language,
    current_prefix: str,
    used_words: list[str],
) -> tuple[str, str | None]:
    """Return (normalized_word, error_key). error_key is None on success."""
    cleaned, err = sanitize_text(raw, MAX_WORD_LENGTH)
    if err:
        return "", err

    if not is_valid_word(cleaned, language):
        return "", "word_invalid_chars"

    normalized = normalize_word(cleaned, language)

    if not starts_with_prefix(normalized, current_prefix, language):
        return "", "word_wrong_prefix"

    normalized_used = [normalize_word(w, language) for w in used_words]
    if normalized in normalized_used:
        return "", "word_already_used"

    return normalized, None


def validate_clue_input(
    raw: str,
    intended_word: str,
    language: Language,
    max_length: int = MAX_CLUE_LENGTH,
) -> tuple[str, str | None]:
    """Return (cleaned_clue, error_key). error_key is None on success."""
    cleaned, err = sanitize_text(raw, max_length)
    if err:
        return "", err

    if not cleaned:
        return "", "clue_empty"

    if clue_mentions_word(cleaned, intended_word, language):
        return "", "clue_contains_word"

    return cleaned, None
