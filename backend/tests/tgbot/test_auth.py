"""Tests for access-code authentication: store, gate, and login command."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from backend.telegram.auth.codes import code_to_hash, generate_code, normalize
from backend.telegram.auth.store import AuthStore


# ---------------------------------------------------------------------------
# Code generation helpers
# ---------------------------------------------------------------------------

class TestCodeHelpers(unittest.TestCase):
    def test_generate_code_length_and_format(self):
        code = generate_code()
        # XXXXX-XXXXX-XXXXX-XXXXX
        parts = code.split("-")
        self.assertEqual(len(parts), 4)
        for part in parts:
            self.assertEqual(len(part), 5)

    def test_normalize_strips_dashes(self):
        self.assertEqual(normalize("ABCDE-FGHIJ-KLMNO-PQRST"), "ABCDEFGHIJKLMNOPQRST")

    def test_normalize_lowercases_input(self):
        self.assertEqual(normalize("abcde-fghij"), "ABCDEFGHIJ")

    def test_normalize_strips_spaces(self):
        self.assertEqual(normalize("AB CD"), "ABCD")

    def test_hash_stable(self):
        code = "ABCDE-FGHIJ-KLMNO-PQRST"
        self.assertEqual(code_to_hash(code), code_to_hash(code.lower()))
        self.assertEqual(code_to_hash(code), code_to_hash("ABCDEFGHIJKLMNOPQRST"))

    def test_different_codes_different_hashes(self):
        c1, c2 = generate_code(), generate_code()
        # Astronomically unlikely to collide, but guard anyway
        if c1 != c2:
            self.assertNotEqual(code_to_hash(c1), code_to_hash(c2))


# ---------------------------------------------------------------------------
# AuthStore
# ---------------------------------------------------------------------------

class TestAuthStore(unittest.IsolatedAsyncioTestCase):
    def _store(self, tmp_dir: str) -> AuthStore:
        return AuthStore(Path(tmp_dir) / "auth.json")

    async def test_empty_store_not_authorized(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            await store.load()
            self.assertFalse(await store.is_authorized(999))

    async def test_redeem_valid_code_authorizes_user(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            await store.load()
            code = generate_code()
            await store.add_codes([code_to_hash(code)])

            result = await store.redeem_code(code, user_id=42)
            self.assertEqual(result, "ok")
            self.assertTrue(await store.is_authorized(42))

    async def test_redeem_persists_across_load(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "auth.json"
            store = AuthStore(path)
            await store.load()
            code = generate_code()
            await store.add_codes([code_to_hash(code)])
            await store.redeem_code(code, user_id=7)

            # Re-load from disk
            store2 = AuthStore(path)
            await store2.load()
            self.assertTrue(await store2.is_authorized(7))

    async def test_redeem_invalid_code_returns_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            await store.load()
            result = await store.redeem_code("AAAAA-BBBBB-CCCCC-DDDDD", user_id=1)
            self.assertEqual(result, "invalid")
            self.assertFalse(await store.is_authorized(1))

    async def test_redeem_same_code_twice_returns_already_used(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            await store.load()
            code = generate_code()
            await store.add_codes([code_to_hash(code)])
            await store.redeem_code(code, user_id=1)
            result = await store.redeem_code(code, user_id=2)
            self.assertEqual(result, "already_used")
            self.assertFalse(await store.is_authorized(2))

    async def test_redeem_when_already_authorized_returns_already_authorized(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            await store.load()
            code1 = generate_code()
            code2 = generate_code()
            await store.add_codes([code_to_hash(code1), code_to_hash(code2)])
            await store.redeem_code(code1, user_id=5)
            result = await store.redeem_code(code2, user_id=5)
            self.assertEqual(result, "already_authorized")

    async def test_revoke_removes_user(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            await store.load()
            code = generate_code()
            await store.add_codes([code_to_hash(code)])
            await store.redeem_code(code, user_id=9)
            self.assertTrue(await store.is_authorized(9))
            removed = await store.revoke_user(9)
            self.assertTrue(removed)
            self.assertFalse(await store.is_authorized(9))

    async def test_revoke_nonexistent_user_returns_false(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            await store.load()
            self.assertFalse(await store.revoke_user(999))

    async def test_list_authorized_returns_users(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            await store.load()
            code = generate_code()
            await store.add_codes([code_to_hash(code)])
            await store.redeem_code(code, user_id=3)
            users = await store.list_authorized()
            self.assertEqual(len(users), 1)
            self.assertEqual(users[0]["user_id"], 3)

    async def test_codes_accepted_with_different_normalizations(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            await store.load()
            code = "ABCDE-FGHIJ-KLMNO-PQRST"
            await store.add_codes([code_to_hash(code)])
            # User types lowercase without dashes
            result = await store.redeem_code("abcdefghijklmnopqrst", user_id=1)
            self.assertEqual(result, "ok")


# ---------------------------------------------------------------------------
# Auth gate (group -1 handler)
# ---------------------------------------------------------------------------

def _make_update(text: str = "", user_id: int = 1, has_callback: bool = False):
    update = MagicMock()
    update.update_id = 1
    user = MagicMock()
    user.id = user_id
    user.language_code = "en"
    update.effective_user = user

    if has_callback:
        update.effective_message = None
        update.callback_query = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.message = None
    else:
        update.callback_query = None
        msg = MagicMock()
        msg.text = text
        msg.reply_text = AsyncMock()
        update.effective_message = msg
        update.message = msg

    return update


def _make_context(auth_store):
    ctx = MagicMock()
    ctx.bot_data = {"auth_store": auth_store}
    ctx.args = []
    return ctx


class TestAuthGate(unittest.IsolatedAsyncioTestCase):
    async def _make_store(self, authorized_user_id: int | None = None):
        with tempfile.TemporaryDirectory() as d:
            store = AuthStore(Path(d) / "auth.json")
            await store.load()
            if authorized_user_id is not None:
                code = generate_code()
                await store.add_codes([code_to_hash(code)])
                await store.redeem_code(code, user_id=authorized_user_id)
            return store

    async def test_authorized_user_passes_through(self):
        from backend.telegram.handlers.auth import auth_gate
        from telegram.ext import ApplicationHandlerStop

        store = await self._make_store(authorized_user_id=42)
        update = _make_update(text="/newgame", user_id=42)
        ctx = _make_context(store)

        # Should not raise
        await auth_gate(update, ctx)
        update.effective_message.reply_text.assert_not_called()

    async def test_unauthorized_text_blocked(self):
        from backend.telegram.handlers.auth import auth_gate
        from telegram.ext import ApplicationHandlerStop

        store = await self._make_store()
        update = _make_update(text="hello", user_id=99)
        ctx = _make_context(store)

        with self.assertRaises(ApplicationHandlerStop):
            await auth_gate(update, ctx)
        update.effective_message.reply_text.assert_called_once()

    async def test_unauthorized_start_blocked_with_welcome(self):
        from backend.telegram.handlers.auth import auth_gate
        from telegram.ext import ApplicationHandlerStop
        from backend.telegram.i18n import copy as i18n

        store = await self._make_store()
        update = _make_update(text="/start", user_id=99)
        ctx = _make_context(store)

        with self.assertRaises(ApplicationHandlerStop):
            await auth_gate(update, ctx)

        call_args = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("/login", call_args)

    async def test_login_command_passes_through(self):
        from backend.telegram.handlers.auth import auth_gate
        from telegram.ext import ApplicationHandlerStop

        store = await self._make_store()
        update = _make_update(text="/login ABCDE-FGHIJ-KLMNO-PQRST", user_id=99)
        ctx = _make_context(store)

        # Should NOT raise — /login is always passed through
        await auth_gate(update, ctx)
        update.effective_message.reply_text.assert_not_called()

    async def test_unauthorized_callback_query_blocked(self):
        from backend.telegram.handlers.auth import auth_gate
        from telegram.ext import ApplicationHandlerStop

        store = await self._make_store()
        update = _make_update(user_id=99, has_callback=True)
        ctx = _make_context(store)

        with self.assertRaises(ApplicationHandlerStop):
            await auth_gate(update, ctx)
        update.callback_query.answer.assert_called_once()

    async def test_no_user_passes_through(self):
        from backend.telegram.handlers.auth import auth_gate

        store = await self._make_store()
        update = _make_update(text="hi", user_id=1)
        update.effective_user = None
        ctx = _make_context(store)

        # No user → return silently (can't block what we can't identify)
        await auth_gate(update, ctx)


# ---------------------------------------------------------------------------
# Login command handler
# ---------------------------------------------------------------------------

class TestLoginCommand(unittest.IsolatedAsyncioTestCase):
    def _make_ctx(self, store, args=None):
        ctx = MagicMock()
        ctx.bot_data = {
            "auth_store": store,
            "settings": MagicMock(allowed_chat_types=frozenset({"private"})),
        }
        ctx.args = args or []
        return ctx

    def _make_update(self, text="/login CODE", user_id=1, chat_type="private"):
        update = MagicMock()
        user = MagicMock()
        user.id = user_id
        user.language_code = "en"
        update.effective_user = user
        chat = MagicMock()
        chat.type = chat_type
        update.effective_chat = chat
        msg = MagicMock()
        msg.text = text
        msg.reply_text = AsyncMock()
        update.message = msg
        update.effective_message = msg
        return update

    async def _fresh_store(self):
        d = tempfile.mkdtemp()
        store = AuthStore(Path(d) / "auth.json")
        await store.load()
        return store

    async def test_valid_code_succeeds(self):
        from backend.telegram.handlers.auth import login_command
        from backend.telegram.i18n import copy as i18n

        store = await self._fresh_store()
        code = generate_code()
        await store.add_codes([code_to_hash(code)])

        update = self._make_update(user_id=7)
        ctx = self._make_ctx(store, args=[code])

        await login_command(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        self.assertIn(i18n.get("login_success"), reply)
        self.assertTrue(await store.is_authorized(7))

    async def test_invalid_code_rejected(self):
        from backend.telegram.handlers.auth import login_command
        from backend.telegram.i18n import copy as i18n

        store = await self._fresh_store()
        update = self._make_update(user_id=8)
        ctx = self._make_ctx(store, args=["AAAAA-BBBBB-CCCCC-DDDDD"])

        await login_command(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        self.assertIn(i18n.get("login_invalid"), reply)
        self.assertFalse(await store.is_authorized(8))

    async def test_used_code_rejected(self):
        from backend.telegram.handlers.auth import login_command
        from backend.telegram.i18n import copy as i18n

        store = await self._fresh_store()
        code = generate_code()
        await store.add_codes([code_to_hash(code)])
        await store.redeem_code(code, user_id=1)

        update = self._make_update(user_id=2)
        ctx = self._make_ctx(store, args=[code])

        await login_command(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        self.assertIn(i18n.get("login_invalid"), reply)
        self.assertFalse(await store.is_authorized(2))

    async def test_no_args_shows_usage(self):
        from backend.telegram.handlers.auth import login_command
        from backend.telegram.i18n import copy as i18n

        store = await self._fresh_store()
        update = self._make_update(user_id=3)
        ctx = self._make_ctx(store, args=[])

        await login_command(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        self.assertIn("/login", reply)

    async def test_already_authorized_user_gets_confirmation(self):
        from backend.telegram.handlers.auth import login_command
        from backend.telegram.i18n import copy as i18n

        store = await self._fresh_store()
        code1 = generate_code()
        code2 = generate_code()
        await store.add_codes([code_to_hash(code1), code_to_hash(code2)])
        await store.redeem_code(code1, user_id=5)

        update = self._make_update(user_id=5)
        ctx = self._make_ctx(store, args=[code2])

        await login_command(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        self.assertIn(i18n.get("login_already_authorized"), reply)

    async def test_code_accepted_without_dashes(self):
        from backend.telegram.handlers.auth import login_command

        store = await self._fresh_store()
        code = "ABCDE-FGHIJ-KLMNO-PQRST"
        await store.add_codes([code_to_hash(code)])

        # User types without dashes
        update = self._make_update(user_id=10)
        ctx = self._make_ctx(store, args=["ABCDEFGHIJKLMNOPQRST"])

        await login_command(update, ctx)
        self.assertTrue(await store.is_authorized(10))

    async def test_code_split_across_args(self):
        """User types /login ABCDE FGHIJ KLMNO PQRST (spaces instead of dashes)."""
        from backend.telegram.handlers.auth import login_command

        store = await self._fresh_store()
        code = "ABCDE-FGHIJ-KLMNO-PQRST"
        await store.add_codes([code_to_hash(code)])

        update = self._make_update(user_id=11)
        ctx = self._make_ctx(store, args=["ABCDE", "FGHIJ", "KLMNO", "PQRST"])

        await login_command(update, ctx)
        self.assertTrue(await store.is_authorized(11))


if __name__ == "__main__":
    unittest.main()
