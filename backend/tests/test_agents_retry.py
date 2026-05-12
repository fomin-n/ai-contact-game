from __future__ import annotations

from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from backend.app import agents
from backend.app.prompt_loader import RenderedPrompt
from backend.app.providers.base import LLMProvider


class FakeProvider(LLMProvider):
    name = "fake"
    display_name = "Fake"

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.messages_seen: list[list[dict[str, str]]] = []

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
        self.messages_seen.append(messages)
        return self.responses.pop(0)


def build_test_prompt(attempt: int, repair_feedback: str) -> RenderedPrompt:
    return RenderedPrompt(
        task_name="test_task",
        id="test_prompt",
        version="v1",
        temperature=0,
        model_role="test",
        schema={},
        messages=[
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": f"attempt={attempt + 1}\nrepairFeedback={repair_feedback}"},
        ],
    )


class LLMRetryTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._logger_disabled = agents.logger.disabled
        agents.logger.disabled = True

    def tearDown(self) -> None:
        agents.logger.disabled = self._logger_disabled

    async def test_retry_prompt_contains_previous_answer_and_validation_reason(self) -> None:
        provider = FakeProvider([{"word": "running"}, {"word": "library"}])

        def validate(candidate: dict[str, Any]) -> tuple[bool, str | None, str]:
            if candidate.get("word") != "library":
                return False, None, "word must be a singular common noun."
            return True, "library", ""

        with patch.object(agents.asyncio, "sleep", new_callable=AsyncMock) as sleep:
            result = await agents._with_repair(
                provider=provider,
                model="fake-model",
                build_prompt=build_test_prompt,
                validate=validate,
                task_name="Test retry",
                response_schema={},
            )

        self.assertEqual(result, "library")
        self.assertEqual(len(provider.messages_seen), 2)
        retry_user_message = provider.messages_seen[1][1]["content"]
        self.assertIn('"word": "running"', retry_user_message)
        self.assertIn("word must be a singular common noun", retry_user_message)
        self.assertIn("This answer is not acceptable", retry_user_message)
        sleep.assert_awaited_once_with(agents.LLM_RETRY_DELAY_SECONDS)

    async def test_retry_count_respects_configured_maximum(self) -> None:
        provider = FakeProvider([{"word": "bad"} for _ in range(agents.MAX_LLM_ATTEMPTS)])

        def validate(candidate: dict[str, Any]) -> tuple[bool, None, str]:
            return False, None, "always invalid"

        with patch.object(agents.asyncio, "sleep", new_callable=AsyncMock) as sleep:
            with self.assertRaises(agents.LLMValidationError):
                await agents._with_repair(
                    provider=provider,
                    model="fake-model",
                    build_prompt=build_test_prompt,
                    validate=validate,
                    task_name="Test max retries",
                    response_schema={},
                )

        self.assertEqual(len(provider.messages_seen), agents.MAX_LLM_ATTEMPTS)
        self.assertEqual(sleep.await_count, agents.MAX_LLM_ATTEMPTS - 1)

    async def test_repeated_rejected_answer_gets_explicit_feedback(self) -> None:
        provider = FakeProvider([{"word": "bad"}, {"word": "bad"}, {"word": "valid"}])

        def validate(candidate: dict[str, Any]) -> tuple[bool, str | None, str]:
            if candidate.get("word") == "valid":
                return True, "valid", ""
            return False, None, "word does not start with the required prefix."

        with patch.object(agents.asyncio, "sleep", new_callable=AsyncMock):
            result = await agents._with_repair(
                provider=provider,
                model="fake-model",
                build_prompt=build_test_prompt,
                validate=validate,
                task_name="Test repeated answer",
                response_schema={},
            )

        self.assertEqual(result, "valid")
        self.assertEqual(len(provider.messages_seen), 3)
        second_retry_user_message = provider.messages_seen[2][1]["content"]
        self.assertIn('"word": "bad"', second_retry_user_message)
        self.assertIn("same as a previously rejected answer", second_retry_user_message)
