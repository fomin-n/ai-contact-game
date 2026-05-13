from __future__ import annotations

import re

Language = str

_SURROUNDING_QUOTES = re.compile(r"^[\s\"'`“”‘’«»]+|[\s\"'`“”‘’«»]+$")


def normalize_word(word: object, language: Language) -> str:
    normalized = _SURROUNDING_QUOTES.sub("", str(word or "").strip()).lower()
    return normalized.replace("ё", "е") if language == "ru" else normalized


def word_validation_failure_reason(word: object, language: Language, field_name: str = "word") -> str:
    normalized = normalize_word(word, language)
    if not normalized:
        return f"{field_name} is empty or malformed."
    if re.search(r"\s", normalized):
        return f"{field_name} must be one single word with no spaces."
    if re.search(r"[-‐‑‒–—]", normalized):
        return f"{field_name} must not contain hyphens or dashes."
    if re.search(r"\d", normalized):
        return f"{field_name} must not contain digits."

    pattern = r"^[а-я]+$" if language == "ru" else r"^[a-z]+$"
    if re.fullmatch(pattern, normalized) is None:
        letters = "Russian Cyrillic letters а-я or ё" if language == "ru" else "English letters a-z"
        return (
            f"{field_name} must contain only {letters}; "
            "no punctuation, symbols, emoji, spaces, hyphens, or other characters."
        )
    return ""


def is_valid_word(word: object, language: Language) -> bool:
    return not word_validation_failure_reason(word, language)


def starts_with_prefix(word: object, prefix: object, language: Language) -> bool:
    normalized_word = normalize_word(word, language)
    normalized_prefix = normalize_word(prefix, language)
    return is_valid_word(normalized_word, language) and normalized_word.startswith(normalized_prefix)


def same_word(a: object, b: object, language: Language) -> bool:
    return normalize_word(a, language) == normalize_word(b, language)


def first_letters(word: str, count: int) -> str:
    return word[:count]


def clue_mentions_word(clue: str, word: str, language: Language) -> bool:
    normalized_word = normalize_word(word, language)
    text = clue.lower().replace("ё", "е")
    pattern = r"[а-я]+" if language == "ru" else r"[a-z]+"
    return normalized_word in re.findall(pattern, text)
