"""Tests for the per-provider circuit breaker in backend/app/providers/http_json.py."""
from __future__ import annotations

import time
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.providers import http_json
from backend.app.providers.http_json import (
    ProviderCapacityError,
    ProviderCircuitOpenError,
    post_chat_completion,
)


def _fake_response(status_code: int, *, body: dict | None = None, headers: dict | None = None):
    response = MagicMock()
    response.status_code = status_code
    response.is_success = 200 <= status_code < 300
    response.headers = headers or {}
    response.text = "error detail"
    response.request = MagicMock()
    payload = body if body is not None else {
        "choices": [{"message": {"content": '{"word": "library"}'}}]
    }
    response.json.return_value = payload
    return response


def _patched_client(response):
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return patch.object(http_json.httpx, "AsyncClient", return_value=client), client


class CircuitBreakerTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        # Fresh breaker per test so state doesn't leak between tests/providers.
        self._original_breaker = http_json._BREAKER
        http_json._BREAKER = http_json._CircuitBreaker(
            failure_threshold=3, window_seconds=60.0, cooldown_seconds=30.0
        )

    def tearDown(self) -> None:
        http_json._BREAKER = self._original_breaker

    async def _call(self, provider="test-provider"):
        patcher, client = _patched_client(_fake_response(429))
        with patcher:
            with self.assertRaises(ProviderCapacityError):
                await post_chat_completion(
                    provider_name=provider,
                    base_url="https://example.invalid",
                    api_key="key",
                    model="m",
                    messages=[],
                    temperature=0.5,
                )

    async def test_stays_closed_under_threshold(self) -> None:
        for _ in range(2):  # threshold is 3
            await self._call()

        patcher, client = _patched_client(_fake_response(200))
        with patcher:
            result = await post_chat_completion(
                provider_name="test-provider",
                base_url="https://example.invalid",
                api_key="key",
                model="m",
                messages=[],
                temperature=0.5,
            )
        self.assertEqual(result, {"word": "library"})
        client.post.assert_awaited_once()

    async def test_trips_at_threshold_and_short_circuits_without_http_call(self) -> None:
        for _ in range(3):
            await self._call()

        patcher, client = _patched_client(_fake_response(200))
        with patcher:
            with self.assertRaises(ProviderCircuitOpenError):
                await post_chat_completion(
                    provider_name="test-provider",
                    base_url="https://example.invalid",
                    api_key="key",
                    model="m",
                    messages=[],
                    temperature=0.5,
                )
        client.post.assert_not_awaited()

    async def test_auto_closes_after_cooldown_elapses(self) -> None:
        for _ in range(3):
            await self._call()

        # Simulate cooldown having already elapsed.
        http_json._BREAKER._open_until["test-provider"] = time.monotonic() - 1

        patcher, client = _patched_client(_fake_response(200))
        with patcher:
            result = await post_chat_completion(
                provider_name="test-provider",
                base_url="https://example.invalid",
                api_key="key",
                model="m",
                messages=[],
                temperature=0.5,
            )
        self.assertEqual(result, {"word": "library"})
        client.post.assert_awaited_once()

    async def test_failures_outside_window_are_evicted(self) -> None:
        breaker = http_json._BREAKER
        now = time.monotonic()
        # Two failures far outside the 60s window, one fresh — should not trip
        # a threshold-3 breaker.
        breaker._failure_times["test-provider"] = [now - 1000, now - 999]
        await self._call()  # one fresh failure

        patcher, client = _patched_client(_fake_response(200))
        with patcher:
            await post_chat_completion(
                provider_name="test-provider",
                base_url="https://example.invalid",
                api_key="key",
                model="m",
                messages=[],
                temperature=0.5,
            )
        client.post.assert_awaited_once()  # breaker did not trip, real call happened

    async def test_non_429_error_does_not_feed_breaker(self) -> None:
        import httpx

        patcher, client = _patched_client(_fake_response(500))
        with patcher:
            for _ in range(5):  # well above threshold, but none are 429s
                with self.assertRaises(httpx.HTTPStatusError):
                    await post_chat_completion(
                        provider_name="test-provider",
                        base_url="https://example.invalid",
                        api_key="key",
                        model="m",
                        messages=[],
                        temperature=0.5,
                    )

        patcher2, client2 = _patched_client(_fake_response(200))
        with patcher2:
            await post_chat_completion(
                provider_name="test-provider",
                base_url="https://example.invalid",
                api_key="key",
                model="m",
                messages=[],
                temperature=0.5,
            )
        client2.post.assert_awaited_once()  # breaker never tripped

    async def test_providers_have_independent_breaker_state(self) -> None:
        for _ in range(3):
            await self._call(provider="provider-a")

        patcher, client = _patched_client(_fake_response(200))
        with patcher:
            result = await post_chat_completion(
                provider_name="provider-b",
                base_url="https://example.invalid",
                api_key="key",
                model="m",
                messages=[],
                temperature=0.5,
            )
        self.assertEqual(result, {"word": "library"})
        client.post.assert_awaited_once()


if __name__ == "__main__":
    import unittest
    unittest.main()
