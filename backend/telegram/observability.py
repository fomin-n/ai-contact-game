"""OpenTelemetry/Phoenix tracing for the Telegram bot.

Call setup_tracing(settings) once at startup. After that every module can
import and use span_for_update(), span_for_game_session(), and the record_*
helpers.  All helpers swallow their own exceptions — tracing must never
break the bot.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator, Iterator

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

if TYPE_CHECKING:
    from telegram import Update

    from .config import TelegramBotSettings
    from .session.game_session import GameSession

LOGGER = logging.getLogger(__name__)

_TRACER_NAME = "ai-contact-game-bot"
_MAX_TEXT = 300   # chars kept for any user/LLM string in span attributes/events


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _trunc(text: Any, n: int = _MAX_TEXT) -> str:
    s = str(text) if not isinstance(text, str) else text
    if len(s) <= n:
        return s
    return s[:n] + f" …[+{len(s) - n}]"


def get_tracer() -> trace.Tracer:
    return trace.get_tracer(_TRACER_NAME)


def _safe(fn: Any, *args: Any, **kwargs: Any) -> None:
    """Call fn(*args, **kwargs), swallowing all exceptions."""
    try:
        fn(*args, **kwargs)
    except Exception:
        pass


def _attrs(span: Span | None, mapping: dict[str, Any]) -> None:
    if span is None:
        return
    for k, v in mapping.items():
        try:
            span.set_attribute(k, v)
        except Exception:
            pass


def _event(span: Span | None, name: str, attrs: dict[str, Any] | None = None) -> None:
    if span is None:
        return
    try:
        span.add_event(name, attrs or {})
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def setup_tracing(settings: "TelegramBotSettings") -> bool:
    """Configure the global OTel tracer provider. Returns True if enabled."""
    if not settings.enable_phoenix_tracing:
        return False
    try:
        from phoenix.otel import register  # type: ignore[import-untyped]

        register(
            project_name=settings.phoenix_project_name,
            endpoint=settings.phoenix_collector_endpoint,
        )
        LOGGER.info(
            "Phoenix tracing enabled: project=%s endpoint=%s",
            settings.phoenix_project_name,
            settings.phoenix_collector_endpoint,
        )
        return True
    except Exception as exc:
        LOGGER.warning("Phoenix tracing setup failed, running without traces: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Attribute builders
# ---------------------------------------------------------------------------

def _user_attrs(update: "Update") -> dict[str, Any]:
    """Non-secret Telegram user/chat attributes, safe to store in spans."""
    out: dict[str, Any] = {}
    user = update.effective_user
    if user:
        out["user.id"] = str(user.id)          # Phoenix user-grouping key
        out["session.id"] = str(user.id)        # Phoenix session-grouping key
        out["tg.user.id"] = user.id
        username = user.username
        if isinstance(username, str) and username:
            out["tg.user.username"] = username
        first = user.first_name if isinstance(user.first_name, str) else ""
        last = user.last_name if isinstance(user.last_name, str) else ""
        display = " ".join(filter(None, [first, last])).strip()
        if display:
            out["tg.user.display_name"] = _trunc(display, 100)
        lang_code = user.language_code
        if isinstance(lang_code, str) and lang_code:
            out["tg.user.language_code"] = lang_code
    chat = update.effective_chat
    if chat:
        out["tg.chat.id"] = chat.id
    if update.update_id:
        out["tg.update_id"] = update.update_id
    return out


def _session_attrs(session: "GameSession") -> dict[str, Any]:
    return {
        "session.id": str(session.user_id),
        "user.id": str(session.user_id),
        "tg.user.id": session.user_id,
        "game.language": session.language,
        "game.human_role": str(session.human_role),
        "game.bot_state": session.state.name,
    }


def _incoming_event(update: "Update") -> tuple[str, dict[str, Any]]:
    """Build a 'tg.incoming' event from the update."""
    attrs: dict[str, Any] = {}
    if update.message and update.message.text:
        text = update.message.text.strip()
        attrs["type"] = "command" if text.startswith("/") else "text"
        attrs["preview"] = _trunc(text)
        attrs["char_count"] = len(text)
    elif update.callback_query:
        attrs["type"] = "callback"
        attrs["data"] = _trunc(update.callback_query.data or "", 80)
    return "tg.incoming", attrs


# ---------------------------------------------------------------------------
# Context managers for handlers
# ---------------------------------------------------------------------------

@asynccontextmanager
async def span_for_update(
    operation: str,
    update: "Update",
    session: "GameSession | None" = None,
) -> AsyncIterator[Span]:
    """Root span for one Telegram update handler.

    Sets user/session/chat attributes and adds a tg.incoming event.
    Records exceptions on the span if the handler raises.

    Usage::

        async with observability.span_for_update("command.start", update, session) as span:
            span.set_attribute("custom.key", "value")
    """
    try:
        with get_tracer().start_as_current_span(f"tg.{operation}") as span:
            _attrs(span, _user_attrs(update))
            if session:
                _attrs(span, _session_attrs(session))
            name, evt_attrs = _incoming_event(update)
            if evt_attrs:
                _event(span, name, evt_attrs)
            try:
                yield span
            except Exception as exc:
                try:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, _trunc(str(exc), 200)))
                except Exception:
                    pass
                raise
    except Exception:
        raise  # never swallow handler exceptions


@contextmanager
def span_for_game_session(
    operation: str,
    user_id: int,
    *,
    language: str = "",
    human_role: str = "",
) -> Iterator[Span]:
    """Root span for game_session.py operations (game start, dispatching)."""
    try:
        with get_tracer().start_as_current_span(f"game.{operation}") as span:
            _attrs(span, {
                "session.id": str(user_id),
                "user.id": str(user_id),
                "tg.user.id": user_id,
            })
            if language:
                _attrs(span, {"game.language": language})
            if human_role:
                _attrs(span, {"game.human_role": human_role})
            yield span
    except Exception:
        pass  # game-session spans must never raise


# ---------------------------------------------------------------------------
# Record helpers (call from anywhere; all no-ops on failure)
# ---------------------------------------------------------------------------

def record_outgoing(span: Span | None, text: str, chat_id: int | None = None) -> None:
    """Record a bot message sent to Telegram."""
    if span is None:
        return
    attrs: dict[str, Any] = {"preview": _trunc(text, 200)}
    if chat_id is not None:
        attrs["chat_id"] = chat_id
    _event(span, "tg.outgoing", attrs)


def record_validation_failure(span: Span | None, field: str, reason: str) -> None:
    """Mark the span as having a validation failure and add an event."""
    _event(span, "validation.failure", {
        "field": field,
        "reason": _trunc(reason, 200),
    })
    _attrs(span, {"validation.failed": True})


def record_auth_outcome(span: Span | None, outcome: str) -> None:
    """Record the result of an auth gate or login command."""
    _attrs(span, {"auth.outcome": outcome})
    _event(span, "auth.outcome", {"outcome": outcome})


def record_game_event(span: Span | None, event_type: str, role: str, text: str = "") -> None:
    """Record a game message dispatched to Telegram."""
    attrs: dict[str, Any] = {"event_type": event_type, "role": role}
    if text:
        attrs["preview"] = _trunc(text, 150)
    _event(span, "game.event", attrs)


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool | None]:
    """Convert a metadata dict to OTel-safe primitive values (kept for compatibility)."""
    safe: dict[str, str | int | float | bool | None] = {}
    for key, value in metadata.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            safe[key] = value
        else:
            safe[key] = str(value)
    return safe


def record_llm_attempt(
    span: Span | None,
    *,
    attempt: int,
    outcome: str,
    reason: str = "",
) -> None:
    """Add an event for one LLM call attempt (success / api_error / validation_retry)."""
    attrs: dict[str, Any] = {"attempt": attempt + 1, "outcome": outcome}
    if reason:
        attrs["reason"] = _trunc(reason, 200)
    _event(span, "llm.attempt", attrs)
