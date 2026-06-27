from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from .. import render

if TYPE_CHECKING:
    from telegram import Bot, Message
    from telegram.ext import CallbackContext

    from ..session.registry import SessionRegistry
    from ..session.game_session import GameSession
    from ..usage_store import UsageStore

LOGGER = logging.getLogger(__name__)


def get_registry(context: ContextTypes.DEFAULT_TYPE) -> "SessionRegistry":
    return context.bot_data["registry"]  # type: ignore[return-value]


def get_settings(context: ContextTypes.DEFAULT_TYPE):  # type: ignore[return-value]
    return context.bot_data["settings"]


def get_usage_store(context: ContextTypes.DEFAULT_TYPE) -> "UsageStore":
    return context.bot_data["usage_store"]  # type: ignore[return-value]


async def enforce_daily_game_limit(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Returns True if user_id may start a new game right now (and records the attempt).

    A generous abuse guard, not a billing system — see usage_store.py.
    """
    usage_store = get_usage_store(context)
    settings = get_settings(context)
    allowed, count = await usage_store.record_game_start(
        user_id, settings.max_games_per_day_per_user
    )
    if allowed and count == 1:
        LOGGER.info("user=%d first game start of the day", user_id)
    elif not allowed:
        LOGGER.info("user=%d daily game limit reached (%d)", user_id, count)
    return allowed


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
    display_name: str = "",
) -> "GameSession":
    registry = get_registry(context)
    session = await registry.get_or_create(user_id, chat_id, context.bot)
    if display_name:
        session._display_name = display_name
    return session


def _prepare_system_send(text: str, lang: str) -> tuple[str | None, str]:
    """Return (html_text_or_None, plain_fallback_text).

    html_text is None when the rendered HTML would exceed Telegram's message
    length limit — in that case callers should send the truncated plain
    fallback directly rather than risk truncating valid HTML mid-tag.
    """
    html_text = render.render_system_text(text, lang)
    plain_fallback = render.truncate_plain(text)
    if len(html_text) > render.TELEGRAM_MAX_MESSAGE_LENGTH:
        return None, plain_fallback
    return html_text, plain_fallback


async def reply_system(message: "Message", text: str, lang: str, **kwargs: object) -> None:
    """Reply with the [System]-styled rendering, falling back to plain text.

    Use for every instructional/error/confirmation string sourced from i18n
    copy — keeps these visually distinct (lighter) from player dialogue.
    """
    html_text, plain_fallback = _prepare_system_send(text, lang)
    if html_text is None:
        await message.reply_text(plain_fallback, **kwargs)
        return
    try:
        await message.reply_text(html_text, parse_mode=ParseMode.HTML, **kwargs)
    except BadRequest as exc:
        LOGGER.warning("System message rejected as HTML, falling back to plain: %s", exc)
        await message.reply_text(plain_fallback, **kwargs)


async def edit_system(target, text: str, lang: str, **kwargs: object) -> None:
    """Edit a message in place with the [System]-styled rendering.

    `target` is anything exposing `edit_message_text` (a `CallbackQuery` or a
    `Message`).
    """
    html_text, plain_fallback = _prepare_system_send(text, lang)
    if html_text is None:
        await target.edit_message_text(plain_fallback, **kwargs)
        return
    try:
        await target.edit_message_text(html_text, parse_mode=ParseMode.HTML, **kwargs)
    except BadRequest as exc:
        LOGGER.warning("System edit rejected as HTML, falling back to plain: %s", exc)
        await target.edit_message_text(plain_fallback, **kwargs)


async def send_system(bot: "Bot", chat_id: int, text: str, lang: str, **kwargs: object) -> None:
    """Send a standalone [System]-styled message to a chat, with plain-text fallback."""
    html_text, plain_fallback = _prepare_system_send(text, lang)
    if html_text is None:
        await bot.send_message(chat_id, plain_fallback, **kwargs)
        return
    try:
        await bot.send_message(chat_id, html_text, parse_mode=ParseMode.HTML, **kwargs)
    except BadRequest as exc:
        LOGGER.warning("System send rejected as HTML, falling back to plain: %s", exc)
        await bot.send_message(chat_id, plain_fallback, **kwargs)
