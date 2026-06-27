from __future__ import annotations

import os
from typing import Any

from .base import LLMProvider
from .http_json import _schema_name, post_chat_completion


class MistralProvider(LLMProvider):
    name = "mistral"
    display_name = "Mistral"

    def __init__(self) -> None:
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.base_url = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
        self.default_model = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        supports_json_schema: bool = True,
    ) -> dict[str, Any]:
        response_format = {"type": "json_object"}
        if schema and supports_json_schema:
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
