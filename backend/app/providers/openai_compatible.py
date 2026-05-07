from __future__ import annotations

import os
import re
from typing import Any

from .base import LLMProvider
from .http_json import post_chat_completion


def _schema_name(schema: dict[str, Any] | None) -> str:
    raw_name = str((schema or {}).get("title") or "contact_game_response")
    name = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw_name).strip("_")
    return name or "contact_game_response"


class OpenAICompatibleProvider(LLMProvider):
    name = "openai"
    display_name = "OpenAI-compatible"

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.default_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        response_format = {"type": "json_object"}
        if schema:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": _schema_name(schema),
                    "schema": schema,
                    "strict": False,
                },
            }
        return await post_chat_completion(
            provider_name=self.name,
            base_url=self.base_url,
            api_key=self.api_key,
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            response_format=response_format,
        )
