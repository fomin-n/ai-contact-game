from __future__ import annotations

import logging

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ...app.schemas import StartGameRequest
from ..i18n import copy as i18n
from ..session.bot_state import BotState
from ._helpers import get_or_create_session, is_allowed_chat

LOGGER = logging.getLogger(__name__)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    if not is_allowed_chat(update, context):
        if query.message:
            await query.message.reply_text(i18n.get("private_only"))
        return

    data = query.data or ""
    session = await get_or_create_session(user.id, chat.id, context)

    if data.startswith("lang:"):
        await _handle_language(query, session, data[5:])
    elif data.startswith("role:"):
        await _handle_role(query, session, data[5:], context)
    elif data == "newgame":
        await _handle_newgame(query, session)
    else:
        LOGGER.warning("Unknown callback data: %s", data)


async def _handle_language(query: CallbackQuery, session, lang_code: str) -> None:
    if lang_code not in ("en", "ru"):
        return
    async with session.lock:
        if session.state != BotState.SELECTING_LANGUAGE:
            return
        session.language = lang_code  # type: ignore[assignment]
        session.state = BotState.SELECTING_ROLE

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                i18n.get("btn_word_master", lang_code),
                callback_data="role:wordMaster",
            ),
            InlineKeyboardButton(
                i18n.get("btn_player_a", lang_code),
                callback_data="role:playerA",
            ),
        ]
    ])
    await query.edit_message_text(
        i18n.get("select_role", lang_code),
        reply_markup=keyboard,
    )


async def _handle_role(
    query: CallbackQuery,
    session,
    role: str,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    lang = session.language
    async with session.lock:
        if session.state != BotState.SELECTING_ROLE:
            return
        if role not in ("wordMaster", "playerA"):
            return
        session.human_role = role  # type: ignore[assignment]
        if role == "wordMaster":
            session.state = BotState.ENTERING_SECRET
        else:
            session.state = BotState.GAME_RUNNING

    if role == "wordMaster":
        await query.edit_message_text(i18n.get("enter_secret", lang))
    else:
        await query.edit_message_text(i18n.get("game_started", lang))
        request = StartGameRequest(
            language=lang,
            playerAPersonality="",
            playerBPersonality="",
            humanRole="playerA",
        )
        try:
            await session.start_game(request)
        except Exception as exc:
            LOGGER.error("Failed to start game for user %s: %s", session.user_id, exc)
            async with session.lock:
                session.state = BotState.IDLE
            await context.bot.send_message(session.chat_id, i18n.get("generic_error", lang))


async def _handle_newgame(query: CallbackQuery, session) -> None:
    lang = session.language
    async with session.lock:
        session.cancel_monitor()
        session.state = BotState.SELECTING_LANGUAGE
        session._pending_intended_word = None

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(i18n.get("btn_russian"), callback_data="lang:ru"),
            InlineKeyboardButton(i18n.get("btn_english"), callback_data="lang:en"),
        ]
    ])
    if query.message:
        await query.message.reply_text(i18n.get("select_language", lang), reply_markup=keyboard)
