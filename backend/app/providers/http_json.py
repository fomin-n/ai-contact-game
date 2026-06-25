from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx

from ..event_log import write_event


class MissingApiKeyError(RuntimeError):
    pass


class ProviderCircuitOpenError(RuntimeError):
    """Raised instead of making a call while a provider's breaker is open.

    A generous, hobby-scale safeguard: after a burst of HTTP 429s for a given
    provider, short-circuit further calls for a cooldown window instead of
    continuing to hammer an already-throttling provider.
    """

    def __init__(self, *, provider: str, retry_after_seconds: float) -> None:
        super().__init__(
            f"{provider} is temporarily unavailable after repeated capacity errors; "
            f"try again in about {round(retry_after_seconds)}s."
        )
        self.provider = provider
        self.retry_after_seconds = retry_after_seconds


class _CircuitBreaker:
    """Per-provider breaker: trips after _FAILURE_THRESHOLD HTTP 429s within
    _WINDOW_SECONDS, then short-circuits new calls for _COOLDOWN_SECONDS.

    No lock: both methods are fully synchronous with no `await` between a
    read and its corresponding write, so no other coroutine can interleave
    mid-method even though many different coroutines call these concurrently
    (asyncio only yields control at `await` points). If either method is
    ever changed to `await` something before its dict mutation completes,
    this reasoning breaks and a lock would become necessary.
    """

    def __init__(self, failure_threshold: int, window_seconds: float, cooldown_seconds: float) -> None:
        self._failure_threshold = failure_threshold
        self._window_seconds = window_seconds
        self._cooldown_seconds = cooldown_seconds
        self._failure_times: dict[str, list[float]] = {}
        self._open_until: dict[str, float] = {}

    def check(self, provider: str) -> None:
        until = self._open_until.get(provider)
        if until is None:
            return
        now = time.monotonic()
        if now >= until:
            del self._open_until[provider]
            self._failure_times.pop(provider, None)
            return
        raise ProviderCircuitOpenError(provider=provider, retry_after_seconds=until - now)

    def record_failure(self, provider: str) -> None:
        now = time.monotonic()
        times = [t for t in self._failure_times.get(provider, []) if now - t < self._window_seconds]
        times.append(now)
        self._failure_times[provider] = times
        if len(times) >= self._failure_threshold:
            self._open_until[provider] = now + self._cooldown_seconds
            self._failure_times[provider] = []


_FAILURE_THRESHOLD = int(os.getenv("AI_CONTACT_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "8"))
_WINDOW_SECONDS = float(os.getenv("AI_CONTACT_CIRCUIT_BREAKER_WINDOW_SECONDS", "90"))
_COOLDOWN_SECONDS = float(os.getenv("AI_CONTACT_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "90"))
_BREAKER = _CircuitBreaker(_FAILURE_THRESHOLD, _WINDOW_SECONDS, _COOLDOWN_SECONDS)


class ProviderCapacityError(RuntimeError):
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        status_code: int,
        detail: str,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(
            f"{provider} capacity is currently unavailable for {model} "
            f"(HTTP {status_code}): {detail}"
        )
        self.provider = provider
        self.model = model
        self.status_code = status_code
        self.detail = detail
        self.retry_after_seconds = retry_after_seconds


def _schema_name(schema: dict[str, Any] | None) -> str:
    raw_name = str((schema or {}).get("title") or "contact_game_response")
    name = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw_name).strip("_")
    return name or "contact_game_response"


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def parse_json_object(text: object) -> dict[str, Any]:
    raw = str(text or "").strip()
    raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).removesuffix("```").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Model did not return JSON.") from None
        parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Model JSON response must be an object.")
    return parsed


async def post_chat_completion(
    *,
    provider_name: str,
    base_url: str,
    api_key: str | None,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not api_key:
        raise MissingApiKeyError("API key is not configured.")

    _BREAKER.check(provider_name)

    request_body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        request_body["response_format"] = response_format

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    started = time.monotonic()
    write_event(
        "llm_http_request",
        provider=provider_name,
        endpoint=endpoint,
        model=model,
        requestBody=request_body,
    )
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request_body,
        )
    elapsed_ms = round((time.monotonic() - started) * 1000, 2)
    response_payload: Any
    try:
        response_payload = response.json()
    except ValueError:
        response_payload = response.text
    write_event(
        "llm_http_response",
        provider=provider_name,
        endpoint=endpoint,
        model=model,
        statusCode=response.status_code,
        elapsedMs=elapsed_ms,
        response=response_payload,
    )
    if not response.is_success:
        detail = response.text[:1200]
        if response.status_code == 429:
            _BREAKER.record_failure(provider_name)
            raise ProviderCapacityError(
                provider=provider_name,
                model=model,
                status_code=response.status_code,
                detail=detail,
                retry_after_seconds=_retry_after_seconds(response.headers.get("retry-after")),
            )
        raise httpx.HTTPStatusError(
            f"AI provider request failed with HTTP {response.status_code}: {detail}",
            request=response.request,
            response=response,
        )
    if not isinstance(response_payload, dict):
        raise ValueError(
            f"Expected a JSON object from {provider_name}, got {type(response_payload).__name__}."
        )
    choices = response_payload.get("choices") or []
    content = choices[0].get("message", {}).get("content") if choices else None
    try:
        return parse_json_object(content)
    except ValueError as error:
        write_event(
            "llm_json_parse_failure",
            provider=provider_name,
            endpoint=endpoint,
            model=model,
            content=content,
            error=error,
        )
        raise
