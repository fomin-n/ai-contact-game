from __future__ import annotations

import hashlib
import secrets

# Alphabet excludes visually ambiguous chars: 0/O, 1/I
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_CHARS = 20


def generate_code() -> str:
    """Return a random 20-char access code formatted as XXXXX-XXXXX-XXXXX-XXXXX."""
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_CHARS))
    return f"{raw[0:5]}-{raw[5:10]}-{raw[10:15]}-{raw[15:20]}"


def normalize(raw: str) -> str:
    """Strip separators and uppercase — accept any delimiter the user typed."""
    return raw.upper().replace("-", "").replace(" ", "").replace(".", "")


def code_to_hash(raw: str) -> str:
    """SHA-256 hex digest of the normalized code."""
    return hashlib.sha256(normalize(raw).encode()).hexdigest()
