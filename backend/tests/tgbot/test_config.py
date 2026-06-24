"""Tests for backend/telegram/config.py (TelegramBotSettings.from_env)."""
import os
import unittest
from unittest.mock import patch


class TestTelegramBotSettingsFromEnv(unittest.TestCase):
    def _env(self, **overrides):
        base = {"AI_CONTACT_TELEGRAM_BOT_TOKEN": "fake:token"}
        base.update(overrides)
        return base

    def test_spectator_delay_defaults_to_1_5_seconds(self):
        from backend.telegram.config import TelegramBotSettings

        with patch.dict(os.environ, self._env(), clear=False):
            settings = TelegramBotSettings.from_env()

        self.assertEqual(settings.ai_spectator_message_delay_seconds, 1.5)

    def test_spectator_delay_reads_env_override(self):
        from backend.telegram.config import TelegramBotSettings

        env = self._env(AI_CONTACT_TELEGRAM_AI_SPECTATOR_MESSAGE_DELAY_SECONDS="3")
        with patch.dict(os.environ, env, clear=False):
            settings = TelegramBotSettings.from_env()

        self.assertEqual(settings.ai_spectator_message_delay_seconds, 3.0)

    def test_missing_token_raises(self):
        from backend.telegram.config import TelegramBotSettings

        env = dict(os.environ)
        env.pop("AI_CONTACT_TELEGRAM_BOT_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError):
                TelegramBotSettings.from_env()


if __name__ == "__main__":
    unittest.main()
