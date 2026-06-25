from __future__ import annotations

import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

from ...app.schemas import StartGameRequest, UserInputRequest
from .. import observability
from ..i18n import copy as i18n
from ..safety import MAX_CLUE_LENGTH, sanitize_text, validate_clue_input, validate_word_input
from ..session.bot_state import BotState
from ._helpers import (
    enforce_daily_game_limit,
    get_or_create_session,
    get_settings,
    is_allowed_chat,
    reply_system,
)

LOGGER = logging.getLogger(__name__)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    if not is_allowed_chat(update, context):
        await reply_system(update.message, i18n.get("private_only"), "en")
        return

    display_name = user.full_name or user.first_name or ""
    session = await get_or_create_session(user.id, chat.id, context, display_name=display_name)

    async with observability.span_for_update("text_message", update, session=session) as span:
        text = update.message.text.strip()
        lang = session.language

        # Guard: deduplication + rate limit (no I/O while holding lock)
        rate_limited = False
        async with session.lock:
            if session.is_duplicate_update(update.update_id):
                observability._event(span, "update.duplicate", {})
                return
            session.last_activity = time.monotonic()
            if not session.check_rate_limit():
                rate_limited = True
            state = session.state

        if rate_limited:
            await reply_system(update.message, i18n.get("rate_limited", lang), lang)
            observability._event(span, "rate_limited", {})
            return

        observability._safe(span.set_attribute, "game.bot_state", state.name)

        if state == BotState.ENTERING_SECRET:
            await _handle_entering_secret(session, text, update, context, span)
        elif state == BotState.WAITING_WM_GUESS:
            await _handle_wm_guess(session, text, update, span)
        elif state == BotState.WAITING_INTENDED_WORD:
            await _handle_intended_word(session, text, update, span)
        elif state == BotState.WAITING_CLUE:
            await _handle_clue(session, text, update, span)
        elif state == BotState.WAITING_PARTNER_GUESS:
            await _handle_partner_guess(session, text, update, span)
        else:
            await reply_system(update.message, i18n.get("unexpected", lang), lang)
            observability._event(span, "unexpected_state", {"state": state.name})


async def _handle_entering_secret(session, text: str, update: Update, context, span=None) -> None:
    lang = session.language

    word, err = validate_word_input(text, lang, "", [])
    if err:
        hint = i18n.get("lang_hint_ru" if lang == "ru" else "lang_hint_en", lang)
        await reply_system(update.message, _word_error_message(err, lang, prefix="", hint=hint), lang)
        observability.record_validation_failure(span, "secret_word", err)
        return

    if not await enforce_daily_game_limit(context, session.user_id):
        limit = get_settings(context).max_games_per_day_per_user
        await reply_system(update.message, i18n.get("daily_game_limit_reached", lang, limit=limit), lang)
        async with session.lock:
            session.state = BotState.IDLE
        observability._event(span, "game.daily_limit_reached", {"role": "wordMaster"})
        return

    request = StartGameRequest(
        language=lang,
        playerAPersonality="",
        playerBPersonality="",
        humanRole="wordMaster",
        secretWord=word,
    )
    try:
        await session.start_game(request)
        await reply_system(update.message, i18n.get("game_started", lang), lang)
        observability._event(span, "game.started", {
            "language": lang,
            "human_role": "wordMaster",
        })
    except ValueError as exc:
        await reply_system(
            update.message, i18n.get("game_input_error", lang, error=str(exc)), lang
        )
        observability._event(span, "game.start_failed", {"error": str(exc)[:200]})
    except Exception as exc:
        LOGGER.error("Failed to start game for user %s: %s", session.user_id, exc)
        async with session.lock:
            session.state = BotState.IDLE
        await reply_system(update.message, i18n.get("generic_error", lang), lang)
        observability._event(span, "game.start_failed", {"error": str(exc)[:200]})


async def _handle_wm_guess(session, text: str, update: Update, span=None) -> None:
    lang = session.language
    snapshot = await session.gm.get_state()
    prefix = snapshot.currentPrefix
    used = snapshot.usedWords

    word, err = validate_word_input(text, lang, prefix, used)
    if err:
        hint = i18n.get("lang_hint_ru" if lang == "ru" else "lang_hint_en", lang)
        await reply_system(update.message, _word_error_message(err, lang, prefix=prefix, hint=hint), lang)
        observability.record_validation_failure(span, "wm_guess", err)
        return

    observability._event(span, "user.submitted_wm_guess", {"prefix": prefix})

    async with session.lock:
        if session.state != BotState.WAITING_WM_GUESS:
            return
        session.state = BotState.GAME_RUNNING

    try:
        await session.submit_input(UserInputRequest(kind="wordMasterGuess", guess=word))
    except ValueError as exc:
        async with session.lock:
            session.state = BotState.WAITING_WM_GUESS
        await reply_system(
            update.message, i18n.get("game_input_error", lang, error=str(exc)), lang
        )
        observability._event(span, "input.rejected", {"error": str(exc)[:200]})


async def _handle_intended_word(session, text: str, update: Update, span=None) -> None:
    lang = session.language
    snapshot = await session.gm.get_state()
    prefix = snapshot.currentPrefix
    used = snapshot.usedWords

    word, err = validate_word_input(text, lang, prefix, used)
    if err:
        hint = i18n.get("lang_hint_ru" if lang == "ru" else "lang_hint_en", lang)
        await reply_system(update.message, _word_error_message(err, lang, prefix=prefix, hint=hint), lang)
        observability.record_validation_failure(span, "intended_word", err)
        return

    async with session.lock:
        if session.state != BotState.WAITING_INTENDED_WORD:
            return
        session._pending_intended_word = word
        session.state = BotState.WAITING_CLUE

    observability._event(span, "user.submitted_intended_word", {"prefix": prefix})
    await reply_system(update.message, i18n.get("player_move_step2", lang, word=word), lang)


async def _handle_clue(session, text: str, update: Update, span=None) -> None:
    lang = session.language

    async with session.lock:
        if session.state != BotState.WAITING_CLUE:
            return
        intended_word = session._pending_intended_word

    if intended_word is None:
        async with session.lock:
            session.state = BotState.WAITING_INTENDED_WORD
        snapshot = await session.gm.get_state()
        await reply_system(
            update.message, i18n.get("player_move_step1", lang, prefix=snapshot.currentPrefix), lang
        )
        return

    clue_text, clue_err = validate_clue_input(text, intended_word, lang, MAX_CLUE_LENGTH)
    if clue_err:
        if clue_err == "clue_contains_word":
            await reply_system(
                update.message, i18n.get("clue_contains_word", lang, word=intended_word), lang
            )
        else:
            await reply_system(update.message, i18n.get(clue_err, lang), lang)
        observability.record_validation_failure(span, "clue", clue_err)
        return

    async with session.lock:
        if session.state != BotState.WAITING_CLUE:
            return
        session._pending_intended_word = None
        session.state = BotState.GAME_RUNNING

    observability._event(span, "user.submitted_clue", {
        "clue_char_count": len(clue_text),
    })

    try:
        await session.submit_input(
            UserInputRequest(
                kind="playerMove",
                intendedWord=intended_word,
                clue=clue_text,
            )
        )
    except ValueError as exc:
        async with session.lock:
            session._pending_intended_word = intended_word
            session.state = BotState.WAITING_CLUE
        await reply_system(
            update.message, i18n.get("game_input_error", lang, error=str(exc)), lang
        )
        observability._event(span, "input.rejected", {"error": str(exc)[:200]})


async def _handle_partner_guess(session, text: str, update: Update, span=None) -> None:
    lang = session.language
    snapshot = await session.gm.get_state()
    prefix = snapshot.currentPrefix
    used = snapshot.usedWords

    word, err = validate_word_input(text, lang, prefix, used)
    if err:
        hint = i18n.get("lang_hint_ru" if lang == "ru" else "lang_hint_en", lang)
        await reply_system(update.message, _word_error_message(err, lang, prefix=prefix, hint=hint), lang)
        observability.record_validation_failure(span, "partner_guess", err)
        return

    observability._event(span, "user.submitted_partner_guess", {"prefix": prefix})

    async with session.lock:
        if session.state != BotState.WAITING_PARTNER_GUESS:
            return
        session.state = BotState.GAME_RUNNING

    try:
        await session.submit_input(UserInputRequest(kind="partnerGuess", guess=word))
    except ValueError as exc:
        async with session.lock:
            session.state = BotState.WAITING_PARTNER_GUESS
        await reply_system(
            update.message, i18n.get("game_input_error", lang, error=str(exc)), lang
        )
        observability._event(span, "input.rejected", {"error": str(exc)[:200]})


def _word_error_message(err: str, lang: str, prefix: str, hint: str) -> str:
    if err == "word_wrong_prefix":
        return i18n.get("word_wrong_prefix", lang, prefix=prefix)
    if err == "word_invalid_chars":
        return i18n.get("word_invalid_chars", lang, lang_hint=hint)
    return i18n.get(err, lang)
