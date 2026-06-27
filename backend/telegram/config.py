from __future__ import annotations

import os
from pathlib import Path


class TelegramBotSettings:
    def __init__(
        self,
        bot_token: str,
        session_ttl_seconds: int,
        max_input_length: int,
        allowed_chat_types: frozenset[str],
        enable_phoenix_tracing: bool,
        phoenix_project_name: str,
        phoenix_collector_endpoint: str,
        ai_spectator_message_delay_seconds: float,
        usage_data_path: Path,
        max_games_per_day_per_user: int,
    ) -> None:
        self.bot_token = bot_token
        self.session_ttl_seconds = session_ttl_seconds
        self.max_input_length = max_input_length
        self.allowed_chat_types = allowed_chat_types
        self.enable_phoenix_tracing = enable_phoenix_tracing
        self.phoenix_project_name = phoenix_project_name
        self.phoenix_collector_endpoint = phoenix_collector_endpoint
        self.ai_spectator_message_delay_seconds = ai_spectator_message_delay_seconds
        self.usage_data_path = usage_data_path
        self.max_games_per_day_per_user = max_games_per_day_per_user

    @classmethod
    def from_env(cls) -> "TelegramBotSettings":
        token = os.getenv("AI_CONTACT_TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "AI_CONTACT_TELEGRAM_BOT_TOKEN is not set. "
                "Export it or add it to .env before running the bot."
            )
        chat_types_raw = os.getenv("AI_CONTACT_TELEGRAM_ALLOWED_CHAT_TYPES", "private")
        allowed = frozenset(t.strip() for t in chat_types_raw.split(",") if t.strip())
        return cls(
            bot_token=token,
            session_ttl_seconds=int(os.getenv("AI_CONTACT_TELEGRAM_SESSION_TTL_SECONDS", "3600")),
            max_input_length=int(os.getenv("AI_CONTACT_TELEGRAM_MAX_INPUT_LENGTH", "500")),
            allowed_chat_types=allowed,
            enable_phoenix_tracing=os.getenv("ENABLE_PHOENIX_TRACING", "false").lower() == "true",
            phoenix_project_name=os.getenv("PHOENIX_PROJECT_NAME", "ai-contact-game-bot"),
            phoenix_collector_endpoint=os.getenv(
                "PHOENIX_COLLECTOR_ENDPOINT", "http://127.0.0.1:6006/v1/traces"
            ),
            ai_spectator_message_delay_seconds=float(
                os.getenv("AI_CONTACT_TELEGRAM_AI_SPECTATOR_MESSAGE_DELAY_SECONDS", "1.5")
            ),
            usage_data_path=Path(
                os.getenv("AI_CONTACT_TELEGRAM_USAGE_DATA_PATH", "data/usage.json")
            ),
            max_games_per_day_per_user=int(
                os.getenv("AI_CONTACT_TELEGRAM_MAX_GAMES_PER_DAY_PER_USER", "50")
            ),
        )
