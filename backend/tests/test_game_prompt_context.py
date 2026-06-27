from __future__ import annotations

from typing import Any
from unittest import TestCase

from backend.app.config import AgentProviderConfig
from backend.app.game import GameManager
from backend.app.providers.base import LLMProvider
from backend.app.schemas import AgentModelConfig, GameMessage


class StubProvider(LLMProvider):
    name = "stub"
    display_name = "Stub"

    @property
    def has_api_key(self) -> bool:
        return True

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        supports_json_schema: bool = True,
    ) -> dict[str, Any]:
        raise NotImplementedError


class GamePromptContextTests(TestCase):
    def test_word_master_decoded_examples_are_extracted_from_blocked_turns(self) -> None:
        provider = StubProvider()
        manager = GameManager(
            AgentProviderConfig(provider, provider, provider),
            AgentModelConfig(
                word_master_model="stub-model",
                player_a_model="stub-model",
                player_b_model="stub-model",
            ),
        )
        state = manager._idle_state(
            language="en",
            player_a_personality="",
            player_b_personality="",
        )
        state.messages = [
            GameMessage(
                id="1",
                role="playerA",
                text="The orange path from yesterday.",
                timestamp=1,
                metadata={"eventType": "clue"},
            ),
            GameMessage(
                id="2",
                role="wordMaster",
                text="This is not carrot!",
                timestamp=2,
                metadata={"eventType": "master-guess", "word": "carrot"},
            ),
            GameMessage(
                id="3",
                role="system",
                text="Word Master guessed. Contact broken.",
                timestamp=3,
                metadata={"eventType": "blocked"},
            ),
        ]

        self.assertEqual(
            manager._word_master_decoded_examples(state),
            [
                {
                    "actingPlayer": "Player A",
                    "clue": "The orange path from yesterday.",
                    "decodedWord": "carrot",
                    "whyNegative": "Word Master decoded this clue and blocked contact.",
                }
            ],
        )
