from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from ...app.game import GameManager
from ...app.schemas import (
    GameMessage,
    GameState,
    HumanRole,
    Language,
    StartGameRequest,
    UserInputRequest,
)
from .. import observability, render
from ..i18n import copy as i18n
from .bot_state import BotState

if TYPE_CHECKING:
    from telegram import Bot

LOGGER = logging.getLogger(__name__)

_MONITOR_POLL_INTERVAL = 0.15
_TYPING_INTERVAL = 4.0
_HTML = "HTML"


class GameSession:
    def __init__(
        self,
        user_id: int,
        chat_id: int,
        gm: GameManager,
        bot: "Bot",
    ) -> None:
        self.user_id = user_id
        self.chat_id = chat_id
        self.gm = gm
        self._bot = bot
        self.state = BotState.IDLE
        self.language: Language = "en"
        self.human_role: HumanRole = "none"
        self.lock = asyncio.Lock()
        self.last_activity = time.monotonic()
        self._last_sent_msg_idx: int = 0
        self._monitor_task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._pending_intended_word: str | None = None
        self._last_submission_time: float = 0.0
        self._last_processed_update_id: int | None = None
        # Rendering state
        self._status_msg_id: int | None = None
        self._system_buffer: list[str] = []

    def start_monitor(self) -> None:
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    def cancel_monitor(self) -> None:
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()

    async def _monitor_loop(self) -> None:
        typing_sent_at = 0.0
        while True:
            await asyncio.sleep(_MONITOR_POLL_INTERVAL)

            now = time.monotonic()
            if now - typing_sent_at > _TYPING_INTERVAL:
                try:
                    from telegram.constants import ChatAction
                    await self._bot.send_chat_action(self.chat_id, ChatAction.TYPING)
                    typing_sent_at = now
                except Exception:
                    pass

            try:
                snapshot = await self.gm.get_state()
            except Exception as exc:
                LOGGER.error("get_state failed in monitor loop: %s", exc)
                await asyncio.sleep(1.0)
                continue

            new_messages = snapshot.messages[self._last_sent_msg_idx:]
            self._last_sent_msg_idx = len(snapshot.messages)

            for msg in new_messages:
                await self._dispatch_message(msg, snapshot)

            await self._flush_system_buffer()

            if snapshot.pendingUserInput is not None:
                async with self.lock:
                    kind = snapshot.pendingUserInput.kind
                    if kind == "playerMove":
                        self.state = BotState.WAITING_INTENDED_WORD
                    elif kind == "wordMasterGuess":
                        self.state = BotState.WAITING_WM_GUESS
                    else:
                        self.state = BotState.WAITING_PARTNER_GUESS
                await self._send_pending_prompt(snapshot)
                return

            if snapshot.status != "running":
                await self._send_game_over(snapshot)
                async with self.lock:
                    self.state = BotState.IDLE
                    self.last_activity = time.monotonic()
                return

    async def _dispatch_message(self, msg: GameMessage, snapshot: GameState) -> None:
        category = render.classify_event(msg)

        if category == "suppress":
            return

        # The human's own input is already visible as their sent message in Telegram.
        if render.is_human_origin(msg, self.human_role):
            return

        if category == "dialogue":
            await self._flush_system_buffer()
            await self._send_html(render.render_dialogue(msg, self.language))
            return

        if category == "status":
            await self._flush_system_buffer()
            await self._send_or_edit_status(snapshot)
            return

        # "inline" or "unknown": accumulate for batching
        self._system_buffer.append(render.render_inline_event(msg, self.language))

    async def _flush_system_buffer(self) -> None:
        if not self._system_buffer:
            return
        text = render.render_system_batch(self._system_buffer)
        self._system_buffer.clear()
        await self._send_html(text)

    async def _send_or_edit_status(self, snapshot: GameState) -> None:
        text = render.render_status(snapshot, self.language)
        try:
            if self._status_msg_id is None:
                sent = await self._bot.send_message(self.chat_id, text, parse_mode=_HTML)
                self._status_msg_id = sent.message_id
            else:
                await self._bot.edit_message_text(
                    text, self.chat_id, self._status_msg_id, parse_mode=_HTML
                )
        except Exception as exc:
            LOGGER.warning("Failed to update status message for chat %s: %s", self.chat_id, exc)
            self._status_msg_id = None  # will re-send next time

    async def _send_pending_prompt(self, snapshot: GameState) -> None:
        pending = snapshot.pendingUserInput
        if pending is None:
            return
        lang = self.language

        if pending.kind == "wordMasterGuess":
            text = render.render_prompt_wm_guess(snapshot, lang)
        elif pending.kind == "playerMove":
            text = render.render_prompt_player_move(snapshot, lang)
        else:
            text = render.render_prompt_partner_guess(snapshot, lang)

        await self._send_html(text)

    async def _send_game_over(self, snapshot: GameState) -> None:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        lang = self.language
        text = render.render_game_over(snapshot, lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(i18n.get("btn_new_game", lang), callback_data="newgame")]
        ])
        try:
            await self._bot.send_message(
                self.chat_id, text, parse_mode=_HTML, reply_markup=keyboard
            )
        except Exception as exc:
            LOGGER.warning("Failed to send game over to chat %s: %s", self.chat_id, exc)

    async def _send_html(self, text: str) -> None:
        try:
            await self._bot.send_message(self.chat_id, text, parse_mode=_HTML)
            LOGGER.debug("sent message to chat %s (%d chars)", self.chat_id, len(text))
        except Exception as exc:
            LOGGER.warning("Failed to send message to chat %s: %s", self.chat_id, exc)

    async def start_game(self, request: StartGameRequest) -> None:
        with observability.span_for_game_session(
            "start",
            self.user_id,
            language=request.language,
            human_role=str(request.humanRole),
        ) as span:
            observability._attrs(span, {
                "game.language": request.language,
                "game.human_role": str(request.humanRole),
            })
            await self.gm.start(request)
            async with self.lock:
                self._last_sent_msg_idx = 0
                self._status_msg_id = None
                self._system_buffer = []
                self.state = BotState.GAME_RUNNING
            observability._event(span, "game.started", {
                "language": request.language,
                "human_role": str(request.humanRole),
            })
        self.start_monitor()

    async def submit_input(self, request: UserInputRequest) -> None:
        await self.gm.submit_user_input(request)
        self.start_monitor()

    def check_rate_limit(self) -> bool:
        """Return True if the user is within the rate limit (OK to proceed)."""
        now = time.monotonic()
        if now - self._last_submission_time < 1.0:
            return False
        self._last_submission_time = now
        return True

    def is_duplicate_update(self, update_id: int) -> bool:
        if self._last_processed_update_id == update_id:
            return True
        self._last_processed_update_id = update_id
        return False
