from __future__ import annotations

import dataclasses
import json
import logging
import logging.handlers
import os
import re
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE = LOG_DIR / "ai-contact-game.jsonl"
MAX_STRING_LENGTH = int(os.getenv("AI_CONTACT_LOG_MAX_STRING_LENGTH", "20000"))
MAX_LOG_BYTES = int(os.getenv("AI_CONTACT_LOG_MAX_BYTES", str(20 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.getenv("AI_CONTACT_LOG_BACKUP_COUNT", "5"))
REDACTED = "[REDACTED]"
SENSITIVE_KEY_NAMES = {
    "apikey",
    "authorization",
    "bearer",
    "password",
    "token",
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "clientsecret",
    "privatekey",
    "credential",
    "credentials",
}
SECRET_ENV_NAMES = (
    "OPENAI_API_KEY",
    "MISTRAL_API_KEY",
    "ANTHROPIC_API_KEY",
    "AI_API_KEY",
)

LOG_DIR.mkdir(parents=True, exist_ok=True)

# A dedicated, non-propagating logger backed by a RotatingFileHandler. The
# handler already serializes concurrent writes internally (its own lock), so
# no extra locking is needed here. The formatter emits only the raw JSONL
# line — no timestamps/levels added — so on-disk format is unchanged.
_event_logger = logging.getLogger("ai_contact.event_log")
_event_logger.setLevel(logging.INFO)
_event_logger.propagate = False
if not _event_logger.handlers:
    _handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _event_logger.addHandler(_handler)


def _is_sensitive_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return normalized in SENSITIVE_KEY_NAMES


def _secret_env_values() -> list[str]:
    values = []
    for name in SECRET_ENV_NAMES:
        value = os.getenv(name)
        if value and len(value) >= 8:
            values.append(value)
    return values


def _truncate(value: str) -> str:
    if MAX_STRING_LENGTH <= 0 or len(value) <= MAX_STRING_LENGTH:
        return value
    return f"{value[:MAX_STRING_LENGTH]}... [truncated {len(value) - MAX_STRING_LENGTH} chars]"


def _redact_string(value: str) -> str:
    redacted = value
    for secret in _secret_env_values():
        redacted = redacted.replace(secret, REDACTED)
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]{12,}", f"Bearer {REDACTED}", redacted)
    redacted = re.sub(r"sk-[A-Za-z0-9_-]{16,}", REDACTED, redacted)
    redacted = re.sub(r"AKIA[0-9A-Z]{16}", REDACTED, redacted)
    redacted = re.sub(r"ghp_[A-Za-z0-9_]{20,}", REDACTED, redacted)
    redacted = re.sub(r"github_pat_[A-Za-z0-9_]{20,}", REDACTED, redacted)
    redacted = re.sub(r"xox[baprs]-[A-Za-z0-9-]{10,}", REDACTED, redacted)
    return redacted


def to_loggable(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return _truncate(_redact_string(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, BaseException):
        return {
            "type": type(value).__name__,
            "message": str(value),
            "traceback": traceback.format_exception(type(value), value, value.__traceback__),
        }
    if dataclasses.is_dataclass(value):
        return to_loggable(dataclasses.asdict(value))
    if hasattr(value, "model_dump"):
        return to_loggable(value.model_dump())
    if hasattr(value, "dict"):
        return to_loggable(value.dict())
    if isinstance(value, dict):
        return {
            str(key): REDACTED if _is_sensitive_key(key) else to_loggable(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple | set):
        return [to_loggable(item) for item in value]
    return _truncate(str(value))


def write_event(event_type: str, **payload: Any) -> None:
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "time": time.time(),
        "eventType": event_type,
        **to_loggable(payload),
    }
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    _event_logger.info(line)
