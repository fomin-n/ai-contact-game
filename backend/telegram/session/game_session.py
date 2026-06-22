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
from ..i18n import copy as i18n
from .bot_state import BotState

if TYPE_CHECKING:
    from telegram import Bot

LOGGER = logging.getLogger(__name__)

_MONITOR_POLL_INTERVAL = 0.15
_TYPING_INTERVAL = 4.0


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

            for msg in snapshot.messages[self._last_sent_msg_idx:]:
                await self._send_game_message(msg)
            self._last_sent_msg_idx = len(snapshot.messages)

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

    async def _send_game_message(self, msg: GameMessage) -> None:
        lang = self.language
        role_label = {
            "system": i18n.get("role_system", lang),
            "playerA": i18n.get("role_player_a", lang),
            "playerB": i18n.get("role_player_b", lang),
            "wordMaster": i18n.get("role_word_master", lang),
        }.get(msg.role, msg.role)

        if msg.role == "system":
            text = msg.text
        else:
            text = f"[{role_label}] {msg.text}"

        try:
            await self._bot.send_message(self.chat_id, text)
        except Exception as exc:
            LOGGER.warning("Failed to send game message to chat %s: %s", self.chat_id, exc)

    async def _send_pending_prompt(self, snapshot: GameState) -> None:
        pending = snapshot.pendingUserInput
        if pending is None:
            return
        lang = self.language

        if pending.kind == "wordMasterGuess":
            text = i18n.get("wm_guess_prompt", lang, prefix=snapshot.currentPrefix)
        elif pending.kind == "playerMove":
            text = i18n.get("player_move_step1", lang, prefix=snapshot.currentPrefix)
        else:
            clue_text = pending.clue or ""
            text = i18n.get(
                "partner_guess_prompt",
                lang,
                clue=clue_text,
                prefix=snapshot.currentPrefix,
            )

        try:
            await self._bot.send_message(self.chat_id, text)
        except Exception as exc:
            LOGGER.warning("Failed to send pending prompt to chat %s: %s", self.chat_id, exc)

    async def _send_game_over(self, snapshot: GameState) -> None:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        lang = self.language
        word = snapshot.secretWord

        if snapshot.winner == "players":
            text = i18n.get("game_over_players_win", lang, word=word)
        elif snapshot.winner == "wordMaster":
            text = i18n.get("game_over_wm_wins", lang, word=word)
        elif snapshot.status == "finished" and snapshot.finishReason:
            # Error finish
            text = i18n.get("game_over_error", lang)
        else:
            text = i18n.get("game_over_unknown", lang)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(i18n.get("btn_new_game", lang), callback_data="newgame")]
        ])
        try:
            await self._bot.send_message(self.chat_id, text, reply_markup=keyboard)
        except Exception as exc:
            LOGGER.warning("Failed to send game over to chat %s: %s", self.chat_id, exc)

    async def start_game(self, request: StartGameRequest) -> None:
        await self.gm.start(request)
        async with self.lock:
            self._last_sent_msg_idx = 0
            self.state = BotState.GAME_RUNNING
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
