from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from ..auth.store import AuthStore
    from ..session.registry import SessionRegistry
    from ..session.game_session import GameSession


def get_registry(context: ContextTypes.DEFAULT_TYPE) -> "SessionRegistry":
    return context.bot_data["registry"]  # type: ignore[return-value]


def get_settings(context: ContextTypes.DEFAULT_TYPE):  # type: ignore[return-value]
    return context.bot_data["settings"]


def get_auth_store(context: ContextTypes.DEFAULT_TYPE) -> "AuthStore":
    return context.bot_data["auth_store"]  # type: ignore[return-value]


def is_allowed_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if chat is None:
        return False
    settings = get_settings(context)
    return chat.type in settings.allowed_chat_types


def get_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    user = update.effective_user
    if user is None:
        return "en"
    registry = get_registry(context)
    # Synchronous peek — sessions already exist at this point in most paths.
    # Falls back to "en" if no session found.
    session = registry._sessions.get(user.id)
    return session.language if session is not None else "en"


async def get_or_create_session(
    user_id: int,
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> "GameSession":
    registry = get_registry(context)
    return await registry.get_or_create(user_id, chat_id, context.bot)
