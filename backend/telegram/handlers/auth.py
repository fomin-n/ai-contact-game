from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from ..auth.store import AuthStore
from ..i18n import copy as i18n
from ._helpers import get_auth_store, is_allowed_chat

LOGGER = logging.getLogger(__name__)

# Commands allowed without authentication.
_OPEN_COMMANDS = frozenset({"/login", "/start"})


async def auth_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Group -1 handler: blocks unauthenticated access to all game functionality.

    - Authorized users: pass through silently.
    - /login command: pass through to login_command in group 0.
    - /start command: send access-required welcome, then stop.
    - Everything else: send brief access-required message, then stop.
    """
    user = update.effective_user
    if user is None:
        return

    auth_store = get_auth_store(context)
    if await auth_store.is_authorized(user.id):
        return

    message = update.effective_message
    text = (message.text or "").strip() if message else ""
    first_word = text.split()[0].split("@")[0].lower() if text else ""

    if first_word == "/login":
        return  # let login_command in group 0 handle it

    if first_word == "/start":
        # Detect language hint from Telegram client locale
        lang = _guess_lang(update)
        if message:
            await message.reply_text(i18n.get("auth_required_welcome", lang))
        raise ApplicationHandlerStop

    # Callback query from an inline button (e.g. "New game" from an old session)
    if update.callback_query:
        lang = _guess_lang(update)
        await update.callback_query.answer(
            i18n.get("auth_required_brief", lang), show_alert=True
        )
        raise ApplicationHandlerStop

    # Any other message or command
    lang = _guess_lang(update)
    if message:
        await message.reply_text(i18n.get("auth_required_brief", lang))
    raise ApplicationHandlerStop


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not is_allowed_chat(update, context):
        await update.message.reply_text(i18n.get("private_only"))
        return

    user = update.effective_user
    if not user:
        return

    # Best-effort language detection (user may not have a session yet)
    lang = _guess_lang(update)

    raw_code = " ".join(context.args or []).strip()
    if not raw_code:
        await update.message.reply_text(i18n.get("login_usage", lang))
        return

    auth_store = get_auth_store(context)
    outcome = await auth_store.redeem_code(raw_code, user.id)

    if outcome == "ok":
        await update.message.reply_text(i18n.get("login_success", lang))
    elif outcome == "already_authorized":
        await update.message.reply_text(i18n.get("login_already_authorized", lang))
    else:
        # "invalid" or "already_used" — same message to avoid oracle attacks
        await update.message.reply_text(i18n.get("login_invalid", lang))


def _guess_lang(update: Update) -> str:
    """Best-effort language from Telegram user locale; defaults to English."""
    user = update.effective_user
    if user and user.language_code and user.language_code.startswith("ru"):
        return "ru"
    return "en"
