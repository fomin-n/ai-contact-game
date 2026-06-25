from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

_VERSION = 1


class UsageStore:
    """Persists a per-user daily game-start counter to a JSON file.

    This is a generous abuse guard, not a billing system: it exists only to
    bound how many games one user (or a bug retriggering /newgame) can start
    in a single day. All public methods are coroutines and safe to call from
    any asyncio task.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._data: dict[str, Any] = {"version": _VERSION, "daily_counts": {}}

    async def load(self) -> None:
        """Load state from disk. Call once at startup; missing file is fine."""
        async with self._lock:
            if not self._path.exists():
                LOGGER.info("Usage store not found at %s — starting empty", self._path)
                return
            try:
                text = self._path.read_text(encoding="utf-8")
                self._data = json.loads(text)
                LOGGER.info(
                    "Usage store loaded: %d user(s) with recorded usage",
                    len(self._data.get("daily_counts", {})),
                )
            except Exception as exc:
                LOGGER.error("Failed to load usage store from %s: %s", self._path, exc)

    async def record_game_start(self, user_id: int, daily_limit: int) -> tuple[bool, int]:
        """Record an attempt to start a game for *user_id*.

        Resets the per-user counter when the stored date is not today (UTC).
        Returns (allowed, count). When the user is already at daily_limit,
        returns (False, count) without incrementing further.
        """
        today = _today_str()
        async with self._lock:
            counts: dict = self._data.setdefault("daily_counts", {})
            key = str(user_id)
            entry = counts.get(key)
            if entry is None or entry.get("date") != today:
                entry = {"date": today, "count": 0}
            if entry["count"] >= daily_limit:
                counts[key] = entry
                allowed, count = False, entry["count"]
            else:
                entry["count"] += 1
                counts[key] = entry
                allowed, count = True, entry["count"]

        await self._save()
        return allowed, count

    async def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except Exception as exc:
            LOGGER.error("Failed to save usage store: %s", exc)
            tmp.unlink(missing_ok=True)


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
