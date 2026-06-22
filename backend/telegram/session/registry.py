from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from ...app.config import load_agent_model_config, load_agent_provider_config
from ...app.game import GameManager
from ..config import TelegramBotSettings
from .game_session import GameSession

if TYPE_CHECKING:
    from telegram import Bot

LOGGER = logging.getLogger(__name__)

_CLEANUP_INTERVAL = 300.0


class SessionRegistry:
    def __init__(self, settings: TelegramBotSettings) -> None:
        self._settings = settings
        self._sessions: dict[int, GameSession] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None  # type: ignore[type-arg]
        providers = load_agent_provider_config()
        self._providers = providers
        self._models = load_agent_model_config(providers)

    async def start(self) -> None:
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        async with self._lock:
            for session in list(self._sessions.values()):
                session.cancel_monitor()
            self._sessions.clear()

    async def get_or_create(self, user_id: int, chat_id: int, bot: "Bot") -> GameSession:
        async with self._lock:
            session = self._sessions.get(user_id)
            if session is not None:
                session.last_activity = time.monotonic()
                return session
            gm = GameManager(self._providers, self._models)
            session = GameSession(user_id, chat_id, gm, bot)
            self._sessions[user_id] = session
            LOGGER.info("Created new session for user %s", user_id)
            return session

    async def get(self, user_id: int) -> GameSession | None:
        async with self._lock:
            return self._sessions.get(user_id)

    async def delete(self, user_id: int) -> None:
        async with self._lock:
            session = self._sessions.pop(user_id, None)
        if session is not None:
            session.cancel_monitor()
            LOGGER.info("Deleted session for user %s", user_id)

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(_CLEANUP_INTERVAL)
            await self._cleanup_expired()

    async def _cleanup_expired(self) -> None:
        ttl = self._settings.session_ttl_seconds
        now = time.monotonic()
        to_delete: list[int] = []

        async with self._lock:
            for user_id, session in list(self._sessions.items()):
                if now - session.last_activity > ttl:
                    to_delete.append(user_id)

        for user_id in to_delete:
            await self.delete(user_id)
            LOGGER.info("Expired session for user %s (TTL exceeded)", user_id)
