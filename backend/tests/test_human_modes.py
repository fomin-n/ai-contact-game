from __future__ import annotations

import asyncio
from typing import Any, Callable
from unittest import IsolatedAsyncioTestCase

from backend.app.config import AgentProviderConfig
from backend.app.game import GameManager
from backend.app.providers.base import LLMProvider
from backend.app.schemas import AgentModelConfig, GameState, StartGameRequest, UserInputRequest


class QueueProvider(LLMProvider):
    name = "queue"
    display_name = "Queue"

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self.responses = list(responses or [])

    @property
    def has_api_key(self) -> bool:
        return True

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        await asyncio.sleep(0)
        if not self.responses:
            raise AssertionError("No queued provider response available.")
        return self.responses.pop(0)


def build_manager(
    *,
    word_master: QueueProvider | None = None,
    player_a: QueueProvider | None = None,
    player_b: QueueProvider | None = None,
) -> GameManager:
    word_master_provider = word_master or QueueProvider()
    player_a_provider = player_a or QueueProvider()
    player_b_provider = player_b or QueueProvider()
    return GameManager(
        AgentProviderConfig(word_master_provider, player_a_provider, player_b_provider),
        AgentModelConfig(
            word_master_model="test-model",
            player_a_model="test-model",
            player_b_model="test-model",
        ),
    )


def start_request(**overrides: Any) -> StartGameRequest:
    return StartGameRequest(
        language=overrides.pop("language", "en"),
        playerAPersonality=overrides.pop("playerAPersonality", ""),
        playerBPersonality=overrides.pop("playerBPersonality", ""),
        **overrides,
    )


async def wait_for_state(
    manager: GameManager,
    predicate: Callable[[GameState], bool],
    *,
    timeout: float = 2,
) -> GameState:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        state = await manager.get_state()
        if predicate(state):
            return state
        await asyncio.sleep(0.01)
    raise AssertionError("Timed out waiting for expected game state.")


class HumanModeTests(IsolatedAsyncioTestCase):
    async def test_ai_vs_ai_start_defaults_to_no_human_role(self) -> None:
        provider = QueueProvider(
            [
                {"word": "canyon"},
                {"intendedWord": "carrot", "clue": "Orange rabbit snack."},
                {"guess": "candle", "confidence": 0.4},
                {"guess": "carrot"},
            ]
        )
        manager = build_manager(word_master=provider, player_a=provider, player_b=provider)
        try:
            state = await manager.start(start_request())
            self.assertEqual(state.humanRole, "none")
            self.assertEqual(state.status, "running")
        finally:
            await manager.reset()

    async def test_human_word_master_requires_secret_word(self) -> None:
        manager = build_manager()
        with self.assertRaisesRegex(ValueError, "Secret word is required"):
            await manager.start(start_request(humanRole="wordMaster"))

    async def test_human_word_master_pauses_after_player_clue(self) -> None:
        manager = build_manager(
            player_a=QueueProvider(
                [{"intendedWord": "carrot", "clue": "Orange rabbit snack."}]
            )
        )
        try:
            await manager.start(start_request(humanRole="wordMaster", secretWord="canyon"))
            state = await wait_for_state(
                manager,
                lambda game: game.pendingUserInput is not None
                and game.pendingUserInput.kind == "wordMasterGuess",
            )
            self.assertEqual(state.pendingUserInput.role, "wordMaster")
            self.assertEqual(state.messages[-1].metadata["eventType"], "clue")
        finally:
            await manager.reset()

    async def test_valid_human_word_master_guess_resumes_game(self) -> None:
        manager = build_manager(
            player_a=QueueProvider(
                [{"intendedWord": "carrot", "clue": "Orange rabbit snack."}]
            ),
            player_b=QueueProvider(
                [{"intendedWord": "castle", "clue": "Stone home."}]
            ),
        )
        try:
            await manager.start(start_request(humanRole="wordMaster", secretWord="canyon"))
            await wait_for_state(
                manager,
                lambda game: game.pendingUserInput is not None
                and game.pendingUserInput.kind == "wordMasterGuess",
            )
            await manager.submit_user_input(UserInputRequest(kind="wordMasterGuess", guess="carrot"))
            state = await wait_for_state(
                manager,
                lambda game: any(
                    (message.metadata or {}).get("eventType") == "blocked"
                    for message in game.messages
                ),
            )
            self.assertIn("carrot", state.usedWords)
        finally:
            await manager.reset()

    async def test_human_player_a_pauses_when_player_a_must_give_clue(self) -> None:
        manager = build_manager(word_master=QueueProvider([{"word": "canyon"}]))
        try:
            await manager.start(start_request(humanRole="playerA"))
            state = await wait_for_state(
                manager,
                lambda game: game.pendingUserInput is not None
                and game.pendingUserInput.kind == "playerMove",
            )
            self.assertEqual(state.pendingUserInput.role, "playerA")
            self.assertEqual(state.secretWord, "")
            self.assertTrue(all("canyon" not in message.text for message in state.messages))
            self.assertTrue(
                all(
                    not message.metadata or message.metadata.get("word") != "canyon"
                    for message in state.messages
                )
            )
        finally:
            await manager.reset()

    async def test_human_player_a_can_submit_intended_word_and_clue(self) -> None:
        manager = build_manager(
            word_master=QueueProvider(
                [
                    {"word": "canyon"},
                    {"guess": "candle", "confidence": 0.5},
                ]
            ),
            player_b=QueueProvider([{"guess": "carrot"}]),
        )
        try:
            await manager.start(start_request(humanRole="playerA"))
            await wait_for_state(
                manager,
                lambda game: game.pendingUserInput is not None
                and game.pendingUserInput.kind == "playerMove",
            )
            await manager.submit_user_input(
                UserInputRequest(
                    kind="playerMove",
                    intendedWord="carrot",
                    clue="Orange rabbit snack.",
                )
            )
            state = await wait_for_state(
                manager,
                lambda game: any(
                    (message.metadata or {}).get("eventType") == "clue"
                    and message.role == "playerA"
                    for message in game.messages
                ),
            )
            self.assertIsNone(state.pendingUserInput)
        finally:
            await manager.reset()

    async def test_human_player_a_pauses_to_guess_player_b_clue_after_failed_interception(self) -> None:
        manager = build_manager(
            word_master=QueueProvider([{"guess": "basket", "confidence": 0.4}]),
            player_b=QueueProvider(
                [{"intendedWord": "banana", "clue": "Yellow curve."}]
            ),
        )
        manager._run_id = 1
        manager._state = manager._idle_state(
            language="en",
            player_a_personality="",
            player_b_personality="",
            human_role="playerA",
        )
        manager._state.status = "running"
        manager._state.secretWord = "bottle"
        manager._state.currentPrefix = "b"
        manager._state.revealedLength = 1
        manager._state.currentTurn = "playerB"
        manager._task = asyncio.create_task(manager._play_turn(1))
        try:
            state = await wait_for_state(
                manager,
                lambda game: game.pendingUserInput is not None
                and game.pendingUserInput.kind == "partnerGuess",
            )
            self.assertEqual(state.pendingUserInput.role, "playerA")
            self.assertNotIn("banana", [message.text for message in state.messages])
        finally:
            await manager.reset()

    async def test_invalid_human_input_keeps_game_waiting(self) -> None:
        manager = build_manager(word_master=QueueProvider([{"word": "canyon"}]))
        try:
            await manager.start(start_request(humanRole="playerA"))
            state = await wait_for_state(
                manager,
                lambda game: game.pendingUserInput is not None
                and game.pendingUserInput.kind == "playerMove",
            )
            message_count = len(state.messages)
            with self.assertRaisesRegex(ValueError, "does not start with required currentPrefix"):
                await manager.submit_user_input(
                    UserInputRequest(
                        kind="playerMove",
                        intendedWord="library",
                        clue="A quiet shelf maze.",
                    )
                )

            state = await manager.get_state()
            self.assertIsNotNone(state.pendingUserInput)
            self.assertEqual(len(state.messages), message_count)
        finally:
            await manager.reset()
