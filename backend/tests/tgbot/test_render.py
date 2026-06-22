"""Tests for the Telegram HTML renderer (backend/telegram/render.py)."""
import unittest

from backend.telegram import render
from backend.telegram.render import esc


def _msg(role="playerA", text="hello", event_type="clue", **meta):
    from backend.app.schemas import GameMessage
    return GameMessage(
        id="test-id",
        role=role,
        text=text,
        timestamp=0.0,
        metadata={"eventType": event_type, **meta},
    )


def _state(**kwargs):
    from backend.app.schemas import GameState, ProviderInfo, AgentModelInfo, AgentProviderInfo
    defaults = dict(
        turnNumber=3,
        maxTurns=50,
        currentPrefix="CO",
        usedWords=["snake", "core"],
        language="en",
        status="running",
        providerInfo=ProviderInfo(
            provider="mistral", displayName="Mistral", hasApiKey=True,
            models=AgentModelInfo(
                wordMasterModel="m", playerAModel="m", playerBModel="m"
            ),
            providers=AgentProviderInfo(
                wordMasterProvider="mistral", wordMasterDisplayName="Mistral",
                wordMasterHasApiKey=True,
                playerAProvider="mistral", playerADisplayName="Mistral",
                playerAHasApiKey=True,
                playerBProvider="mistral", playerBDisplayName="Mistral",
                playerBHasApiKey=True,
            ),
        ),
    )
    defaults.update(kwargs)
    return GameState(**defaults)


# ---------------------------------------------------------------------------
# esc() — HTML escaping
# ---------------------------------------------------------------------------

class TestEsc(unittest.TestCase):
    def test_escapes_ampersand(self):
        self.assertEqual(esc("a & b"), "a &amp; b")

    def test_escapes_lt_gt(self):
        self.assertEqual(esc("<script>"), "&lt;script&gt;")

    def test_plain_text_unchanged(self):
        self.assertEqual(esc("hello world"), "hello world")

    def test_does_not_escape_quotes(self):
        # quote=False: single and double quotes are left as-is in body text
        result = esc('say "hi"')
        self.assertIn('"', result)

    def test_injection_attempt(self):
        # Ensure injected HTML does not pass through unescaped
        evil = '</b><b>injected</b>'
        result = esc(evil)
        self.assertNotIn("<b>", result)
        self.assertIn("&lt;", result)


# ---------------------------------------------------------------------------
# classify_event()
# ---------------------------------------------------------------------------

class TestClassifyEvent(unittest.TestCase):
    def test_clue_is_dialogue(self):
        self.assertEqual(render.classify_event(_msg(event_type="clue")), "dialogue")

    def test_master_guess_is_dialogue(self):
        self.assertEqual(render.classify_event(_msg(event_type="master-guess")), "dialogue")

    def test_prefix_is_status(self):
        self.assertEqual(render.classify_event(_msg(event_type="prefix")), "status")

    def test_blocked_is_inline(self):
        self.assertEqual(render.classify_event(_msg(event_type="blocked")), "inline")

    def test_failed_intercept_is_inline(self):
        self.assertEqual(render.classify_event(_msg(event_type="failed-intercept")), "inline")

    def test_contact_succeeded_is_inline(self):
        self.assertEqual(render.classify_event(_msg(event_type="contact-succeeded")), "inline")

    def test_contact_failed_is_inline(self):
        self.assertEqual(render.classify_event(_msg(event_type="contact-failed")), "inline")

    def test_master_no_guess_is_inline(self):
        self.assertEqual(render.classify_event(_msg(event_type="master-no-guess")), "inline")

    def test_intended_word_is_inline(self):
        self.assertEqual(render.classify_event(_msg(event_type="intended-word")), "inline")

    def test_partner_guess_is_inline(self):
        self.assertEqual(render.classify_event(_msg(event_type="partner-guess")), "inline")

    def test_game_over_is_suppress(self):
        self.assertEqual(render.classify_event(_msg(event_type="game-over")), "suppress")

    def test_error_is_suppress(self):
        self.assertEqual(render.classify_event(_msg(event_type="error")), "suppress")

    def test_unknown_defaults_to_inline(self):
        self.assertEqual(render.classify_event(_msg(event_type="")), "inline")


# ---------------------------------------------------------------------------
# render_dialogue()
# ---------------------------------------------------------------------------

class TestRenderDialogue(unittest.TestCase):
    def test_player_a_clue_en(self):
        msg = _msg(role="playerA", text="a clever clue", event_type="clue")
        result = render.render_dialogue(msg, "en")
        self.assertIn("🔵", result)
        self.assertIn("<b>Player A</b>", result)
        self.assertIn("<blockquote>a clever clue</blockquote>", result)

    def test_player_b_clue_ru(self):
        msg = _msg(role="playerB", text="подсказка", event_type="clue")
        result = render.render_dialogue(msg, "ru")
        self.assertIn("🟢", result)
        self.assertIn("<b>Игрок B</b>", result)
        self.assertIn("<blockquote>подсказка</blockquote>", result)

    def test_word_master_guess(self):
        msg = _msg(role="wordMaster", text="This is not collect!", event_type="master-guess")
        result = render.render_dialogue(msg, "en")
        self.assertIn("🔴", result)
        self.assertIn("<b>Word Master</b>", result)
        self.assertIn("<blockquote>This is not collect!</blockquote>", result)

    def test_clue_text_is_html_escaped(self):
        msg = _msg(role="playerA", text="<evil> & trick", event_type="clue")
        result = render.render_dialogue(msg, "en")
        self.assertNotIn("<evil>", result)
        self.assertIn("&lt;evil&gt;", result)
        self.assertIn("&amp;", result)

    def test_contains_no_raw_html_from_text(self):
        # LLM output with bold tags should not render as HTML
        msg = _msg(role="playerB", text="<b>bold</b>", event_type="clue")
        result = render.render_dialogue(msg, "en")
        self.assertNotIn("<b>bold</b>", result)  # not rendered
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", result)  # escaped inside blockquote


# ---------------------------------------------------------------------------
# render_inline_event()
# ---------------------------------------------------------------------------

class TestRenderInlineEvent(unittest.TestCase):
    def test_blocked_has_handstop_emoji(self):
        msg = _msg(role="system", text="Contact broken.", event_type="blocked")
        result = render.render_inline_event(msg, "en")
        self.assertIn("✋", result)
        self.assertIn("Contact broken.", result)

    def test_failed_intercept_has_handshake(self):
        msg = _msg(role="system", text="There is contact!", event_type="failed-intercept")
        result = render.render_inline_event(msg, "en")
        self.assertIn("🤝", result)

    def test_contact_succeeded(self):
        msg = _msg(role="system", text="Contact succeeded.", event_type="contact-succeeded")
        result = render.render_inline_event(msg, "en")
        self.assertIn("✅", result)

    def test_contact_failed(self):
        msg = _msg(role="system", text="No contact.", event_type="contact-failed")
        result = render.render_inline_event(msg, "en")
        self.assertIn("❌", result)

    def test_text_is_escaped(self):
        msg = _msg(role="system", text="<b>bad</b>", event_type="blocked")
        result = render.render_inline_event(msg, "en")
        self.assertNotIn("<b>bad</b>", result)
        self.assertIn("&lt;b&gt;", result)


# ---------------------------------------------------------------------------
# render_system_batch()
# ---------------------------------------------------------------------------

class TestRenderSystemBatch(unittest.TestCase):
    def test_joins_lines_with_newline(self):
        lines = ["✋ Contact broken.", "✅ Contact succeeded."]
        result = render.render_system_batch(lines)
        self.assertEqual(result, "✋ Contact broken.\n✅ Contact succeeded.")

    def test_single_line(self):
        result = render.render_system_batch(["✅ Contact."])
        self.assertEqual(result, "✅ Contact.")


# ---------------------------------------------------------------------------
# render_status()
# ---------------------------------------------------------------------------

class TestRenderStatus(unittest.TestCase):
    def test_contains_turn_and_prefix(self):
        state = _state(turnNumber=5, maxTurns=50, currentPrefix="CO")
        result = render.render_status(state, "en")
        self.assertIn("🎮", result)
        self.assertIn("Turn 5 / 50", result)
        self.assertIn("<b>CO</b>", result)

    def test_used_words_listed(self):
        state = _state(usedWords=["snake", "core", "copper"])
        result = render.render_status(state, "en")
        self.assertIn("snake", result)
        self.assertIn("core", result)
        self.assertIn("copper", result)

    def test_no_used_words_no_used_line(self):
        state = _state(usedWords=[])
        result = render.render_status(state, "en")
        self.assertNotIn("Used:", result)

    def test_russian_labels(self):
        state = _state(turnNumber=2, maxTurns=50, currentPrefix="К", language="ru")
        result = render.render_status(state, "ru")
        self.assertIn("Ход 2 / 50", result)
        self.assertIn("<b>К</b>", result)

    def test_prefix_is_html_escaped(self):
        state = _state(currentPrefix="<X>")
        result = render.render_status(state, "en")
        self.assertNotIn("<X>", result)
        self.assertIn("&lt;X&gt;", result)

    def test_long_used_words_capped_at_15(self):
        words = [f"word{i}" for i in range(20)]
        state = _state(usedWords=words)
        result = render.render_status(state, "en")
        # Only last 15 should appear
        self.assertIn("word19", result)
        self.assertNotIn("word0", result)  # first 5 are dropped


# ---------------------------------------------------------------------------
# render_prompt_wm_guess()
# ---------------------------------------------------------------------------

class TestRenderPromptWmGuess(unittest.TestCase):
    def test_contains_role_and_prefix(self):
        from backend.app.schemas import PendingUserInput
        state = _state(currentPrefix="CO")
        state.pendingUserInput = PendingUserInput(
            kind="wordMasterGuess", role="wordMaster",
            promptText="Guess", placeholderText="...",
            currentPrefix="CO", clue="a clever hint",
        )
        result = render.render_prompt_wm_guess(state, "en")
        self.assertIn("🔴", result)
        self.assertIn("<b>Word Master</b>", result)
        self.assertIn("<b>CO</b>", result)

    def test_clue_shown_in_blockquote(self):
        from backend.app.schemas import PendingUserInput
        state = _state(currentPrefix="CO")
        state.pendingUserInput = PendingUserInput(
            kind="wordMasterGuess", role="wordMaster",
            promptText="Guess", placeholderText="...",
            currentPrefix="CO", clue="tricky clue here",
        )
        result = render.render_prompt_wm_guess(state, "en")
        self.assertIn("<blockquote>tricky clue here</blockquote>", result)

    def test_clue_text_is_escaped(self):
        from backend.app.schemas import PendingUserInput
        state = _state(currentPrefix="CO")
        state.pendingUserInput = PendingUserInput(
            kind="wordMasterGuess", role="wordMaster",
            promptText="Guess", placeholderText="...",
            currentPrefix="CO", clue="<inject>",
        )
        result = render.render_prompt_wm_guess(state, "en")
        self.assertNotIn("<inject>", result)
        self.assertIn("&lt;inject&gt;", result)

    def test_no_pending_input_no_clue_block(self):
        state = _state(currentPrefix="C")
        state.pendingUserInput = None
        result = render.render_prompt_wm_guess(state, "en")
        self.assertNotIn("<blockquote>", result)


# ---------------------------------------------------------------------------
# render_prompt_partner_guess()
# ---------------------------------------------------------------------------

class TestRenderPromptPartnerGuess(unittest.TestCase):
    def test_shows_clue_in_blockquote(self):
        from backend.app.schemas import PendingUserInput
        state = _state(currentPrefix="CO")
        state.pendingUserInput = PendingUserInput(
            kind="partnerGuess", role="playerA",
            promptText="Guess", placeholderText="...",
            currentPrefix="CO", clue="Player B's mysterious clue",
        )
        result = render.render_prompt_partner_guess(state, "en")
        self.assertIn("🔵", result)
        self.assertIn("<blockquote>Player B's mysterious clue</blockquote>", result)
        self.assertIn("<b>CO</b>", result)


# ---------------------------------------------------------------------------
# render_prompt_player_move()
# ---------------------------------------------------------------------------

class TestRenderPromptPlayerMove(unittest.TestCase):
    def test_shows_prefix_and_role(self):
        state = _state(currentPrefix="CO")
        state.pendingUserInput = None
        result = render.render_prompt_player_move(state, "en")
        self.assertIn("🔵", result)
        self.assertIn("<b>CO</b>", result)

    def test_russian(self):
        state = _state(currentPrefix="К", language="ru")
        state.pendingUserInput = None
        result = render.render_prompt_player_move(state, "ru")
        self.assertIn("🔵", result)
        self.assertIn("<b>К</b>", result)


# ---------------------------------------------------------------------------
# render_game_over()
# ---------------------------------------------------------------------------

class TestRenderGameOver(unittest.TestCase):
    def test_players_win(self):
        state = _state(
            winner="players", secretWord="collect",
            turnNumber=7, usedWords=["snake", "core", "collect"],
            status="finished",
        )
        result = render.render_game_over(state, "en")
        self.assertIn("collect", result)
        self.assertIn("7", result)  # turn number

    def test_wm_wins(self):
        state = _state(
            winner="wordMaster", secretWord="collect",
            turnNumber=7, usedWords=["snake"],
            status="finished",
        )
        result = render.render_game_over(state, "en")
        self.assertIn("collect", result)

    def test_secret_word_is_escaped(self):
        state = _state(
            winner="players", secretWord="<script>",
            turnNumber=1, usedWords=[],
            status="finished",
        )
        result = render.render_game_over(state, "en")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_error_finish(self):
        state = _state(
            winner="wordMaster", secretWord="x",
            finishReason="llmError", status="finished",
            usedWords=[], turnNumber=1,
        )
        result = render.render_game_over(state, "en")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_russian(self):
        state = _state(
            winner="players", secretWord="кот",
            turnNumber=4, usedWords=["кот"],
            status="finished", language="ru",
        )
        result = render.render_game_over(state, "ru")
        self.assertIn("кот", result)
        self.assertIn("4", result)


# ---------------------------------------------------------------------------
# is_human_origin()
# ---------------------------------------------------------------------------

class TestIsHumanOrigin(unittest.TestCase):
    def test_playerA_clue_suppressed_when_human_is_playerA(self):
        msg = _msg(role="playerA", event_type="clue")
        self.assertTrue(render.is_human_origin(msg, "playerA"))

    def test_playerA_intended_word_suppressed_when_human_is_playerA(self):
        msg = _msg(role="playerA", event_type="intended-word")
        self.assertTrue(render.is_human_origin(msg, "playerA"))

    def test_playerA_partner_guess_suppressed_when_human_is_playerA(self):
        msg = _msg(role="playerA", event_type="partner-guess")
        self.assertTrue(render.is_human_origin(msg, "playerA"))

    def test_wm_guess_suppressed_when_human_is_wordMaster(self):
        msg = _msg(role="wordMaster", event_type="master-guess")
        self.assertTrue(render.is_human_origin(msg, "wordMaster"))

    def test_playerB_clue_shown_when_human_is_playerA(self):
        msg = _msg(role="playerB", event_type="clue")
        self.assertFalse(render.is_human_origin(msg, "playerA"))

    def test_playerA_clue_shown_when_human_is_wordMaster(self):
        msg = _msg(role="playerA", event_type="clue")
        self.assertFalse(render.is_human_origin(msg, "wordMaster"))

    def test_wm_guess_shown_when_human_is_playerA(self):
        msg = _msg(role="wordMaster", event_type="master-guess")
        self.assertFalse(render.is_human_origin(msg, "playerA"))

    def test_nothing_suppressed_in_ai_vs_ai(self):
        for role in ("playerA", "playerB", "wordMaster", "system"):
            msg = _msg(role=role)
            self.assertFalse(render.is_human_origin(msg, "none"))

    def test_empty_human_role_suppresses_nothing(self):
        msg = _msg(role="playerA")
        self.assertFalse(render.is_human_origin(msg, ""))

    def test_playerB_intended_word_shown_when_human_is_playerA(self):
        # AI player's intended word is informative — must remain visible
        msg = _msg(role="playerB", event_type="intended-word")
        self.assertFalse(render.is_human_origin(msg, "playerA"))


if __name__ == "__main__":
    unittest.main()
