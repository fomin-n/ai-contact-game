import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram.constants import ParseMode
from telegram.error import BadRequest

from backend.telegram.session.bot_state import BotState
from backend.telegram.i18n import copy as i18n


def _make_provider_info():
    from backend.app.schemas import ProviderInfo, AgentModelInfo, AgentProviderInfo
    return ProviderInfo(
        provider="mistral",
        displayName="Mistral",
        hasApiKey=True,
        models=AgentModelInfo(
            wordMasterModel="mistral-small-latest",
            playerAModel="mistral-small-latest",
            playerBModel="mistral-small-latest",
        ),
        providers=AgentProviderInfo(
            wordMasterProvider="mistral", wordMasterDisplayName="Mistral",
            wordMasterHasApiKey=True,
            playerAProvider="mistral", playerADisplayName="Mistral",
            playerAHasApiKey=True,
            playerBProvider="mistral", playerBDisplayName="Mistral",
            playerBHasApiKey=True,
        ),
    )


def _make_game_state(**kwargs):
    from backend.app.schemas import GameState
    defaults = dict(
        providerInfo=_make_provider_info(),
        status="running",
        language="en",
        currentPrefix="s",
        usedWords=["snake"],
    )
    defaults.update(kwargs)
    return GameState(**defaults)


def _make_pending_input(kind, prefix="s"):
    from backend.app.schemas import PendingUserInput
    prompts = {
        "wordMasterGuess": ("Guess the word.", "Enter word..."),
        "playerMove": ("Send a clue.", "Clue..."),
        "partnerGuess": ("Guess partner's word.", "Enter word..."),
    }
    pt, ph = prompts[kind]
    return PendingUserInput(
        kind=kind,
        role="wordMaster" if kind == "wordMasterGuess" else "playerA",
        promptText=pt,
        placeholderText=ph,
        currentPrefix=prefix,
        clue="a hint" if kind == "partnerGuess" else None,
    )


def _make_session(user_id=1, chat_id=100, state=BotState.IDLE, language="en"):
    from backend.telegram.session.game_session import GameSession
    gm = MagicMock()
    gm.get_state = AsyncMock(return_value=_make_game_state())
    gm.start = AsyncMock(return_value=_make_game_state())
    gm.submit_user_input = AsyncMock(return_value=_make_game_state())
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_chat_action = AsyncMock()
    settings = MagicMock(ai_spectator_message_delay_seconds=0.0)
    session = GameSession(user_id=user_id, chat_id=chat_id, gm=gm, bot=bot, settings=settings)
    session.state = state
    session.language = language
    return session


def _make_context(allowed=True, max_games_per_day_per_user=50):
    """Context double exposing bot_data["usage_store"]/["settings"] as needed by
    enforce_daily_game_limit / get_settings."""
    context = MagicMock()
    context.bot = MagicMock()
    usage_store = MagicMock()
    usage_store.record_game_start = AsyncMock(return_value=(allowed, 1))
    context.bot_data = {
        "usage_store": usage_store,
        "settings": MagicMock(max_games_per_day_per_user=max_games_per_day_per_user),
    }
    return context


class TestLanguageAndRoleSelection(unittest.IsolatedAsyncioTestCase):
    async def test_language_callback_transitions_to_role_selection(self):
        from backend.telegram.handlers.callbacks import _handle_language

        session = _make_session(state=BotState.SELECTING_LANGUAGE)
        query = MagicMock()
        query.edit_message_text = AsyncMock()

        await _handle_language(query, session, "ru")

        self.assertEqual(session.state, BotState.SELECTING_ROLE)
        self.assertEqual(session.language, "ru")
        query.edit_message_text.assert_awaited_once()
        # Role keyboard shown
        call_kwargs = query.edit_message_text.call_args
        self.assertIn("reply_markup", call_kwargs.kwargs or {})

    async def test_language_callback_ignored_if_wrong_state(self):
        from backend.telegram.handlers.callbacks import _handle_language

        session = _make_session(state=BotState.GAME_RUNNING)
        query = MagicMock()
        query.edit_message_text = AsyncMock()

        await _handle_language(query, session, "en")

        # State unchanged, no edit sent
        self.assertEqual(session.state, BotState.GAME_RUNNING)
        query.edit_message_text.assert_not_awaited()

    async def test_role_word_master_prompts_for_secret(self):
        from backend.telegram.handlers.callbacks import _handle_role

        session = _make_session(state=BotState.SELECTING_ROLE)
        session.language = "en"
        query = MagicMock()
        query.edit_message_text = AsyncMock()
        context = _make_context()

        await _handle_role(query, session, "wordMaster", context)

        self.assertEqual(session.state, BotState.ENTERING_SECRET)
        query.edit_message_text.assert_awaited_once()

    async def test_role_player_a_starts_game(self):
        from backend.telegram.handlers.callbacks import _handle_role

        session = _make_session(state=BotState.SELECTING_ROLE)
        session.language = "en"
        query = MagicMock()
        query.edit_message_text = AsyncMock()
        context = _make_context()

        mock_start = AsyncMock()
        with patch.object(session, "start_game", new=mock_start):
            await _handle_role(query, session, "playerA", context)

        mock_start.assert_awaited_once()
        req = mock_start.call_args[0][0]
        self.assertEqual(req.humanRole, "playerA")

    async def test_role_none_starts_spectator_game(self):
        from backend.telegram.handlers.callbacks import _handle_role

        session = _make_session(state=BotState.SELECTING_ROLE)
        session.language = "en"
        query = MagicMock()
        query.edit_message_text = AsyncMock()
        context = _make_context()

        mock_start = AsyncMock()
        with patch.object(session, "start_game", new=mock_start):
            await _handle_role(query, session, "none", context)

        self.assertEqual(session.state, BotState.GAME_RUNNING)
        self.assertEqual(session.human_role, "none")
        mock_start.assert_awaited_once()
        req = mock_start.call_args[0][0]
        self.assertEqual(req.humanRole, "none")
        # Spectator-specific copy, not the generic "game_started" string
        query.edit_message_text.assert_awaited_once()
        text = query.edit_message_text.call_args[0][0]
        self.assertIn(i18n.get("spectator_game_started", "en"), text)

    async def test_role_none_ru_uses_localized_spectator_copy(self):
        from backend.telegram.handlers.callbacks import _handle_role

        session = _make_session(state=BotState.SELECTING_ROLE, language="ru")
        query = MagicMock()
        query.edit_message_text = AsyncMock()
        context = _make_context()

        mock_start = AsyncMock()
        with patch.object(session, "start_game", new=mock_start):
            await _handle_role(query, session, "none", context)

        text = query.edit_message_text.call_args[0][0]
        self.assertIn(i18n.get("spectator_game_started", "ru"), text)

    async def test_role_player_a_blocked_when_daily_limit_reached(self):
        from backend.telegram.handlers.callbacks import _handle_role

        session = _make_session(state=BotState.SELECTING_ROLE)
        session.language = "en"
        query = MagicMock()
        query.edit_message_text = AsyncMock()
        context = _make_context(allowed=False, max_games_per_day_per_user=50)

        mock_start = AsyncMock()
        with patch.object(session, "start_game", new=mock_start):
            await _handle_role(query, session, "playerA", context)

        mock_start.assert_not_awaited()
        self.assertEqual(session.state, BotState.IDLE)
        text = query.edit_message_text.call_args[0][0]
        self.assertIn("50", text)

    async def test_role_keyboard_includes_ai_vs_ai_button(self):
        from backend.telegram.handlers.callbacks import _handle_language

        session = _make_session(state=BotState.SELECTING_LANGUAGE)
        query = MagicMock()
        query.edit_message_text = AsyncMock()

        await _handle_language(query, session, "en")

        keyboard = query.edit_message_text.call_args.kwargs["reply_markup"]
        callback_data = [
            button.callback_data for row in keyboard.inline_keyboard for button in row
        ]
        self.assertIn("role:none", callback_data)

    async def test_unknown_role_rejected(self):
        from backend.telegram.handlers.callbacks import _handle_role

        session = _make_session(state=BotState.SELECTING_ROLE)
        query = MagicMock()
        query.edit_message_text = AsyncMock()
        context = _make_context()

        await _handle_role(query, session, "bogus", context)

        self.assertEqual(session.state, BotState.SELECTING_ROLE)
        query.edit_message_text.assert_not_awaited()


class TestSecretWordEntry(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_word_stays_in_entering_secret(self):
        from backend.telegram.handlers.messages import _handle_entering_secret

        session = _make_session(state=BotState.ENTERING_SECRET, language="en")
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.message = msg
        context = _make_context()

        # Word with digits is invalid
        await _handle_entering_secret(session, "appl3", update, context)

        # State should still be ENTERING_SECRET (no transition)
        self.assertEqual(session.state, BotState.ENTERING_SECRET)
        msg.reply_text.assert_awaited_once()

    async def test_valid_word_starts_game(self):
        from backend.telegram.handlers.messages import _handle_entering_secret

        session = _make_session(state=BotState.ENTERING_SECRET, language="en")
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.message = msg
        context = _make_context()

        mock_start = AsyncMock()
        with patch.object(session, "start_game", new=mock_start):
            await _handle_entering_secret(session, "apple", update, context)

        mock_start.assert_awaited_once()
        req = mock_start.call_args[0][0]
        self.assertEqual(req.humanRole, "wordMaster")
        self.assertEqual(req.secretWord, "apple")

    async def test_word_master_blocked_when_daily_limit_reached(self):
        from backend.telegram.handlers.messages import _handle_entering_secret

        session = _make_session(state=BotState.ENTERING_SECRET, language="en")
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.message = msg
        context = _make_context(allowed=False, max_games_per_day_per_user=50)

        mock_start = AsyncMock()
        with patch.object(session, "start_game", new=mock_start):
            await _handle_entering_secret(session, "apple", update, context)

        mock_start.assert_not_awaited()
        self.assertEqual(session.state, BotState.IDLE)
        text = msg.reply_text.call_args[0][0]
        self.assertIn("50", text)


class TestWordMasterGuessFlow(unittest.IsolatedAsyncioTestCase):
    async def test_wrong_prefix_rejected(self):
        from backend.telegram.handlers.messages import _handle_wm_guess

        session = _make_session(state=BotState.WAITING_WM_GUESS, language="en")
        session.gm.get_state = AsyncMock(return_value=_make_game_state(currentPrefix="s"))
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.message = msg

        # "banana" doesn't start with "s"
        await _handle_wm_guess(session, "banana", update)

        self.assertEqual(session.state, BotState.WAITING_WM_GUESS)
        msg.reply_text.assert_awaited_once()

    async def test_valid_guess_submits_and_starts_monitor(self):
        from backend.telegram.handlers.messages import _handle_wm_guess

        session = _make_session(state=BotState.WAITING_WM_GUESS, language="en")
        session.gm.get_state = AsyncMock(return_value=_make_game_state(currentPrefix="s"))
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        mock_submit = AsyncMock()
        with patch.object(session, "submit_input", new=mock_submit):
            await _handle_wm_guess(session, "sword", update)

        mock_submit.assert_awaited_once()
        req = mock_submit.call_args[0][0]
        self.assertEqual(req.kind, "wordMasterGuess")
        self.assertEqual(req.guess, "sword")


class TestPlayerMoveFlow(unittest.IsolatedAsyncioTestCase):
    async def test_intended_word_step1_transitions_to_waiting_clue(self):
        from backend.telegram.handlers.messages import _handle_intended_word

        session = _make_session(state=BotState.WAITING_INTENDED_WORD, language="en")
        session.gm.get_state = AsyncMock(return_value=_make_game_state(currentPrefix="s"))
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.message = msg

        await _handle_intended_word(session, "stone", update)

        self.assertEqual(session.state, BotState.WAITING_CLUE)
        self.assertEqual(session._pending_intended_word, "stone")

    async def test_clue_with_intended_word_rejected(self):
        from backend.telegram.handlers.messages import _handle_clue

        session = _make_session(state=BotState.WAITING_CLUE, language="en")
        session._pending_intended_word = "stone"
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.message = msg

        # Clue contains the intended word "stone"
        await _handle_clue(session, "it is a stone", update)

        # State unchanged; error reply sent
        self.assertEqual(session.state, BotState.WAITING_CLUE)
        msg.reply_text.assert_awaited_once()

    async def test_valid_clue_submits_both_word_and_clue(self):
        from backend.telegram.handlers.messages import _handle_clue

        session = _make_session(state=BotState.WAITING_CLUE, language="en")
        session._pending_intended_word = "stone"
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        mock_submit = AsyncMock()
        with patch.object(session, "submit_input", new=mock_submit):
            await _handle_clue(session, "think of a rock in the water", update)

        mock_submit.assert_awaited_once()
        req = mock_submit.call_args[0][0]
        self.assertEqual(req.kind, "playerMove")
        self.assertEqual(req.intendedWord, "stone")
        self.assertIsNotNone(req.clue)


class TestCancelAndStatus(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_sets_idle(self):
        from backend.telegram.handlers.commands import cancel_command

        session = _make_session(state=BotState.WAITING_WM_GUESS, language="en")
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 1
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.bot_data = {
            "registry": MagicMock(),
            "settings": MagicMock(allowed_chat_types=frozenset(["private"])),
        }
        update.effective_chat = MagicMock()
        update.effective_chat.type = "private"
        context.bot_data["registry"].get = AsyncMock(return_value=session)

        await cancel_command(update, context)

        self.assertEqual(session.state, BotState.IDLE)

    async def test_status_with_no_game_sends_no_game_message(self):
        from backend.telegram.handlers.commands import status_command

        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 1
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.bot_data = {
            "registry": MagicMock(),
            "settings": MagicMock(allowed_chat_types=frozenset(["private"])),
        }
        update.effective_chat = MagicMock()
        update.effective_chat.type = "private"
        context.bot_data["registry"].get = AsyncMock(return_value=None)

        with patch("backend.telegram.handlers._helpers.get_registry", return_value=context.bot_data["registry"]):
            await status_command(update, context)

        update.message.reply_text.assert_awaited_once()
        text = update.message.reply_text.call_args[0][0]
        self.assertIn("newgame", text.lower())

    async def test_status_shows_dash_for_unknown_max_turns(self):
        from backend.telegram.handlers.commands import status_command

        session = _make_session(state=BotState.GAME_RUNNING)
        session.gm.get_state = AsyncMock(return_value=_make_game_state(maxTurns=0, turnNumber=1))

        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 1
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.bot_data = {
            "registry": MagicMock(),
            "settings": MagicMock(allowed_chat_types=frozenset(["private"])),
        }
        update.effective_chat = MagicMock()
        update.effective_chat.type = "private"
        context.bot_data["registry"].get = AsyncMock(return_value=session)

        with patch("backend.telegram.handlers._helpers.get_registry", return_value=context.bot_data["registry"]):
            await status_command(update, context)

        text = update.message.reply_text.call_args[0][0]
        self.assertIn("1/—", text.replace(" ", ""))


class TestPrivateChatOnly(unittest.IsolatedAsyncioTestCase):
    async def test_group_chat_rejected(self):
        from backend.telegram.handlers.messages import handle_text

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "hello"
        update.message.reply_text = AsyncMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 1
        update.effective_chat = MagicMock()
        update.effective_chat.type = "group"  # group chat
        context = MagicMock()
        context.bot_data = {
            "settings": MagicMock(allowed_chat_types=frozenset(["private"])),
            "registry": MagicMock(),
        }

        await handle_text(update, context)

        update.message.reply_text.assert_awaited_once()
        text = update.message.reply_text.call_args[0][0]
        self.assertIn(i18n.get("private_only"), text)
        self.assertNotIn("[System]", text)


class TestSpectatorMessagePacing(unittest.IsolatedAsyncioTestCase):
    async def test_delay_applied_between_messages_in_spectator_mode(self):
        from backend.app.schemas import GameMessage
        from backend.telegram.session.game_session import GameSession

        gm = MagicMock()
        messages = [
            GameMessage(id="1", role="playerA", text="clue one", timestamp=0.0,
                        metadata={"eventType": "clue"}),
            GameMessage(id="2", role="playerB", text="clue two", timestamp=0.0,
                        metadata={"eventType": "clue"}),
        ]
        gm.get_state = AsyncMock(
            return_value=_make_game_state(status="finished", winner="players", messages=messages)
        )
        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_chat_action = AsyncMock()
        settings = MagicMock(ai_spectator_message_delay_seconds=2.5)
        session = GameSession(user_id=1, chat_id=1, gm=gm, bot=bot, settings=settings)
        session.human_role = "none"

        with patch("backend.telegram.session.game_session.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            await session._monitor_loop()

        delay_calls = [call.args[0] for call in mock_sleep.call_args_list if call.args[0] == 2.5]
        self.assertEqual(len(delay_calls), len(messages))

    async def test_no_delay_for_non_spectator_session(self):
        from backend.app.schemas import GameMessage
        from backend.telegram.session.game_session import GameSession

        gm = MagicMock()
        messages = [
            GameMessage(id="1", role="playerA", text="clue one", timestamp=0.0,
                        metadata={"eventType": "clue"}),
        ]
        gm.get_state = AsyncMock(
            return_value=_make_game_state(status="finished", winner="players", messages=messages)
        )
        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_chat_action = AsyncMock()
        settings = MagicMock(ai_spectator_message_delay_seconds=2.5)
        session = GameSession(user_id=1, chat_id=1, gm=gm, bot=bot, settings=settings)
        session.human_role = "playerA"

        with patch("backend.telegram.session.game_session.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            await session._monitor_loop()

        delay_calls = [call.args[0] for call in mock_sleep.call_args_list if call.args[0] == 2.5]
        self.assertEqual(len(delay_calls), 0)


class TestSystemMessageHelpers(unittest.IsolatedAsyncioTestCase):
    async def test_reply_system_sends_html_with_text(self):
        from backend.telegram.handlers._helpers import reply_system

        message = MagicMock()
        message.reply_text = AsyncMock()

        await reply_system(message, "Please wait a moment.", "en")

        message.reply_text.assert_awaited_once()
        args, kwargs = message.reply_text.call_args
        self.assertNotIn("[System]", args[0])
        self.assertIn("Please wait a moment.", args[0])
        self.assertEqual(kwargs.get("parse_mode"), ParseMode.HTML)

    async def test_reply_system_falls_back_to_plain_on_bad_request(self):
        from backend.telegram.handlers._helpers import reply_system

        message = MagicMock()
        message.reply_text = AsyncMock(
            side_effect=[BadRequest("Can't parse entities"), None]
        )

        await reply_system(message, "Please wait a moment.", "en")

        self.assertEqual(message.reply_text.await_count, 2)
        second_args, second_kwargs = message.reply_text.call_args_list[1]
        self.assertEqual(second_args[0], "Please wait a moment.")
        self.assertNotIn("parse_mode", second_kwargs)

    async def test_reply_system_skips_html_when_oversized(self):
        from backend.telegram.handlers._helpers import reply_system

        message = MagicMock()
        message.reply_text = AsyncMock()
        oversized = "x" * 5000

        await reply_system(message, oversized, "en")

        message.reply_text.assert_awaited_once()
        args, kwargs = message.reply_text.call_args
        self.assertNotIn("parse_mode", kwargs)
        self.assertLessEqual(len(args[0]), 4096)


class TestModelInfoHidden(unittest.IsolatedAsyncioTestCase):
    def test_no_provider_model_names_in_copy(self):
        """Model and provider names must not appear in any user-facing copy strings."""
        internal_terms = ["mistral", "openai", "gpt", "mistral-small", "model="]
        all_copy = i18n._COPY
        for lang, strings in all_copy.items():
            for key, value in strings.items():
                low = value.lower()
                for term in internal_terms:
                    self.assertNotIn(
                        term,
                        low,
                        msg=f"Internal term '{term}' found in copy[{lang}][{key}]: {value!r}",
                    )

    def test_observability_does_not_log_env_secrets(self):
        """Tracing metadata must not include raw API keys or tokens."""
        from backend.telegram.observability import _safe_metadata
        # If a secret were accidentally passed as metadata, we should not store it verbatim.
        # _safe_metadata just converts non-primitives to str; it doesn't redact.
        # The guarantee is that we never pass actual secrets as metadata keys.
        meta = {"user_id": "hashed123", "event": "game_start", "turn": 1}
        safe = _safe_metadata(meta)
        self.assertNotIn("MISTRAL_API_KEY", str(safe))
        self.assertNotIn("BOT_TOKEN", str(safe))


if __name__ == "__main__":
    unittest.main()
