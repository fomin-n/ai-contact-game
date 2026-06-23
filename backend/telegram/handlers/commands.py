from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .. import observability
from ..i18n import copy as i18n
from ..session.bot_state import BotState
from ._helpers import get_lang, get_or_create_session, get_registry, is_allowed_chat

LOGGER = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not is_allowed_chat(update, context):
        await update.message.reply_text(i18n.get("private_only"))
        return
    user = update.effective_user
    if not user:
        return
    session = await get_or_create_session(user.id, update.effective_chat.id, context)
    async with observability.span_for_update("command.start", update, session=session):
        await _begin_new_game_flow(update, context, session)


async def newgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not is_allowed_chat(update, context):
        await update.message.reply_text(i18n.get("private_only"))
        return
    user = update.effective_user
    if not user:
        return
    session = await get_or_create_session(user.id, update.effective_chat.id, context)
    async with observability.span_for_update("command.newgame", update, session=session):
        await _begin_new_game_flow(update, context, session)


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    async with observability.span_for_update("command.rules", update):
        lang = get_lang(update, context)
        await update.message.reply_text(i18n.get("rules", lang))


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    user = update.effective_user
    if not user:
        return
    registry = get_registry(context)
    session = await registry.get(user.id)
    async with observability.span_for_update("command.status", update, session=session) as span:
        lang = get_lang(update, context)
        if session is None or session.state == BotState.IDLE:
            await update.message.reply_text(i18n.get("status_no_game", lang))
            return

        state = await session.gm.get_state()
        observability._attrs(span, {
            "game.turn_number": state.turnNumber,
            "game.max_turns": state.maxTurns,
            "game.prefix": state.currentPrefix or "",
        })
        used = ", ".join(state.usedWords) if state.usedWords else i18n.get("used_words_none", lang)
        text = i18n.get(
            "status_template",
            lang,
            turn=state.turnNumber,
            max_turns=state.maxTurns,
            prefix=state.currentPrefix or "-",
            used_words=used,
        )
        await update.message.reply_text(text)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    user = update.effective_user
    if not user:
        return
    registry = get_registry(context)
    session = await registry.get(user.id)
    async with observability.span_for_update("command.cancel", update, session=session) as span:
        lang = get_lang(update, context)
        if session is None or session.state == BotState.IDLE:
            await update.message.reply_text(i18n.get("cancel_no_game", lang))
            observability.record_auth_outcome(span, "no_active_game")
            return

        async with session.lock:
            session.cancel_monitor()
            session.state = BotState.IDLE
            session._pending_intended_word = None

        await update.message.reply_text(i18n.get("cancel_done", lang))
        observability._event(span, "game.cancelled", {})


async def _begin_new_game_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, session) -> None:
    if not update.message:
        return

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
    await update.message.reply_text(i18n.get("select_language"), reply_markup=keyboard)
