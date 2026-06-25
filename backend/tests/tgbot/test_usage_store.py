"""Tests for backend/telegram/usage_store.py (per-user daily game limit)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.telegram.usage_store import UsageStore


class UsageStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "usage.json"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    async def test_first_game_is_allowed(self) -> None:
        store = UsageStore(self.path)
        allowed, count = await store.record_game_start(1, daily_limit=50)
        self.assertTrue(allowed)
        self.assertEqual(count, 1)

    async def test_rejects_exactly_at_the_limit(self) -> None:
        store = UsageStore(self.path)
        for _ in range(3):
            allowed, _ = await store.record_game_start(1, daily_limit=3)
            self.assertTrue(allowed)

        allowed, count = await store.record_game_start(1, daily_limit=3)
        self.assertFalse(allowed)
        self.assertEqual(count, 3)  # not incremented past the limit

    async def test_independent_users_have_independent_counters(self) -> None:
        store = UsageStore(self.path)
        for _ in range(2):
            await store.record_game_start(1, daily_limit=2)

        allowed_user_1, _ = await store.record_game_start(1, daily_limit=2)
        allowed_user_2, count_user_2 = await store.record_game_start(2, daily_limit=2)

        self.assertFalse(allowed_user_1)
        self.assertTrue(allowed_user_2)
        self.assertEqual(count_user_2, 1)

    async def test_date_rollover_resets_the_counter(self) -> None:
        store = UsageStore(self.path)
        with patch("backend.telegram.usage_store._today_str", return_value="2026-01-01"):
            for _ in range(2):
                allowed, _ = await store.record_game_start(1, daily_limit=2)
                self.assertTrue(allowed)
            blocked, _ = await store.record_game_start(1, daily_limit=2)
            self.assertFalse(blocked)

        with patch("backend.telegram.usage_store._today_str", return_value="2026-01-02"):
            allowed, count = await store.record_game_start(1, daily_limit=2)
            self.assertTrue(allowed)
            self.assertEqual(count, 1)

    async def test_persists_and_reloads_across_instances(self) -> None:
        store = UsageStore(self.path)
        await store.record_game_start(1, daily_limit=50)
        await store.record_game_start(1, daily_limit=50)

        reloaded = UsageStore(self.path)
        await reloaded.load()
        allowed, count = await reloaded.record_game_start(1, daily_limit=50)
        self.assertTrue(allowed)
        self.assertEqual(count, 3)

    async def test_load_is_tolerant_of_missing_file(self) -> None:
        store = UsageStore(self.path)
        await store.load()  # should not raise
        allowed, count = await store.record_game_start(1, daily_limit=50)
        self.assertTrue(allowed)
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
