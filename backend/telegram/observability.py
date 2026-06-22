from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from .config import TelegramBotSettings

LOGGER = logging.getLogger(__name__)

_CONFIGURED = False
_ENABLED = False


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool | None]:
    safe: dict[str, str | int | float | bool | None] = {}
    for key, value in metadata.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            safe[key] = value
        else:
            safe[key] = str(value)
    return safe


def setup_tracing(settings: TelegramBotSettings) -> bool:
    global _CONFIGURED, _ENABLED

    if not settings.enable_phoenix_tracing:
        _ENABLED = False
        return False

    if _CONFIGURED:
        return _ENABLED

    try:
        from phoenix.otel import register

        register(
            project_name=settings.phoenix_project_name,
            endpoint=settings.phoenix_collector_endpoint,
        )
        _ENABLED = True
        LOGGER.info(
            "Phoenix tracing enabled for project %s at %s",
            settings.phoenix_project_name,
            settings.phoenix_collector_endpoint,
        )
    except Exception as exc:
        LOGGER.warning("Phoenix tracing setup failed; continuing without traces: %s", exc)
        _ENABLED = False
    finally:
        _CONFIGURED = True

    return _ENABLED


def is_tracing_enabled() -> bool:
    return _CONFIGURED and _ENABLED


@contextmanager
def trace_update(
    user_id: int | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[None]:
    if not is_tracing_enabled():
        yield
        return

    try:
        from phoenix.otel import using_metadata, using_session, using_user

        from contextlib import ExitStack

        with ExitStack() as stack:
            if user_id is not None:
                import hashlib
                hashed = hashlib.sha256(str(user_id).encode()).hexdigest()[:16]
                stack.enter_context(using_user(hashed))
            if session_id is not None:
                stack.enter_context(using_session(session_id=session_id))
            if metadata:
                stack.enter_context(using_metadata(_safe_metadata(metadata)))
            yield
    except Exception as exc:
        LOGGER.warning("Phoenix trace context failed: %s", exc)
        yield
