from __future__ import annotations

import logging

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ...app.schemas import StartGameRequest
from .. import observability
from ..i18n import copy as i18n
from ..session.bot_state import BotState
from ._helpers import edit_system, get_or_create_session, is_allowed_chat, reply_system, send_system

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
            await reply_system(query.message, i18n.get("private_only"), "en")
        return

    data = query.data or ""
    session = await get_or_create_session(user.id, chat.id, context)

    if data.startswith("lang:"):
        op = "callback.lang_select"
    elif data.startswith("role:"):
        op = "callback.role_select"
    elif data == "newgame":
        op = "callback.newgame"
    else:
        op = "callback.unknown"

    async with observability.span_for_update(op, update, session=session) as span:
        observability._attrs(span, {"tg.callback.data": data[:80]})

        if data.startswith("lang:"):
            await _handle_language(query, session, data[5:], span)
        elif data.startswith("role:"):
            await _handle_role(query, session, data[5:], context, span)
        elif data == "newgame":
            await _handle_newgame(query, session)
        else:
            LOGGER.warning("Unknown callback data: %s", data)
            observability._event(span, "callback.unknown", {"data": data[:80]})


async def _handle_language(query: CallbackQuery, session, lang_code: str, span=None) -> None:
    if lang_code not in ("en", "ru"):
        return
    async with session.lock:
        if session.state != BotState.SELECTING_LANGUAGE:
            return
        session.language = lang_code  # type: ignore[assignment]
        session.state = BotState.SELECTING_ROLE

    observability._attrs(span, {"game.language_selected": lang_code})

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
    await edit_system(query, i18n.get("select_role", lang_code), lang_code, reply_markup=keyboard)


async def _handle_role(
    query: CallbackQuery,
    session,
    role: str,
    context: ContextTypes.DEFAULT_TYPE,
    span=None,
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

    observability._attrs(span, {"game.role_selected": role})

    if role == "wordMaster":
        await edit_system(query, i18n.get("enter_secret", lang), lang)
    else:
        await edit_system(query, i18n.get("game_started", lang), lang)
        request = StartGameRequest(
            language=lang,
            playerAPersonality="",
            playerBPersonality="",
            humanRole="playerA",
        )
        try:
            await session.start_game(request)
            observability._event(span, "game.started", {
                "language": lang,
                "human_role": "playerA",
            })
        except Exception as exc:
            LOGGER.error("Failed to start game for user %s: %s", session.user_id, exc)
            async with session.lock:
                session.state = BotState.IDLE
            await send_system(context.bot, session.chat_id, i18n.get("generic_error", lang), lang)
            observability._event(span, "game.start_failed", {"error": str(exc)[:200]})


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
        await reply_system(query.message, i18n.get("select_language", lang), lang, reply_markup=keyboard)
