from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .codes import code_to_hash

LOGGER = logging.getLogger(__name__)

_VERSION = 1


class AuthStore:
    """Persists authorized users and access code hashes to a JSON file.

    All public methods are coroutines and safe to call from any asyncio task.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._data: dict[str, Any] = {"version": _VERSION, "authorized_users": {}, "codes": {}}

    async def load(self) -> None:
        """Load state from disk. Call once at startup; missing file is fine."""
        async with self._lock:
            if not self._path.exists():
                LOGGER.info("Auth store not found at %s — starting empty", self._path)
                return
            try:
                text = self._path.read_text(encoding="utf-8")
                loaded = json.loads(text)
                self._data = loaded
                users = len(self._data.get("authorized_users", {}))
                codes = sum(
                    1 for v in self._data.get("codes", {}).values() if not v.get("used")
                )
                LOGGER.info(
                    "Auth store loaded: %d authorized user(s), %d unused code(s)", users, codes
                )
            except Exception as exc:
                LOGGER.error("Failed to load auth store from %s: %s", self._path, exc)

    async def is_authorized(self, user_id: int) -> bool:
        async with self._lock:
            return str(user_id) in self._data.get("authorized_users", {})

    async def redeem_code(self, raw_code: str, user_id: int) -> str:
        """Try to redeem *raw_code* for *user_id*.

        Returns one of: "ok", "invalid", "already_used", "already_authorized".
        Never logs the raw code — only the first 8 chars of its SHA-256 hash.
        """
        h = code_to_hash(raw_code)
        log_prefix = h[:8]

        async with self._lock:
            codes: dict = self._data.setdefault("codes", {})
            users: dict = self._data.setdefault("authorized_users", {})

            if str(user_id) in users:
                LOGGER.info(
                    "Login attempt hash=…%s user=%d outcome=already_authorized",
                    log_prefix, user_id,
                )
                return "already_authorized"

            if h not in codes:
                LOGGER.warning(
                    "Login attempt hash=…%s user=%d outcome=invalid", log_prefix, user_id
                )
                return "invalid"

            if codes[h].get("used"):
                LOGGER.warning(
                    "Login attempt hash=…%s user=%d outcome=already_used", log_prefix, user_id
                )
                return "already_used"

            # Redeem
            codes[h]["used"] = True
            codes[h]["used_by"] = user_id
            codes[h]["used_at"] = _now_iso()
            users[str(user_id)] = {"authorized_at": _now_iso(), "code_hash": h}

            LOGGER.info(
                "Login attempt hash=…%s user=%d outcome=ok", log_prefix, user_id
            )

        await self._save()
        return "ok"

    async def add_codes(self, hashes: list[str]) -> None:
        """Store pre-computed code hashes (called by the CLI after printing raw codes)."""
        async with self._lock:
            codes: dict = self._data.setdefault("codes", {})
            for h in hashes:
                codes[h] = {"used": False, "used_by": None, "used_at": None}
        await self._save()

    async def revoke_user(self, user_id: int) -> bool:
        """Remove *user_id* from the authorized set. Returns True if they were authorized."""
        async with self._lock:
            users: dict = self._data.setdefault("authorized_users", {})
            removed = users.pop(str(user_id), None)
        if removed is not None:
            await self._save()
            LOGGER.info("Revoked authorization for user %d", user_id)
            return True
        return False

    async def list_authorized(self) -> list[dict]:
        async with self._lock:
            return [
                {"user_id": int(uid), **info}
                for uid, info in self._data.get("authorized_users", {}).items()
            ]

    async def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except Exception as exc:
            LOGGER.error("Failed to save auth store: %s", exc)
            tmp.unlink(missing_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
