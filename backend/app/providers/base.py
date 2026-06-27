from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    name: str
    display_name: str

    @property
    @abstractmethod
    def has_api_key(self) -> bool:
        """Whether this provider has enough credentials to make API calls."""

    @abstractmethod
    async def chat_json(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        supports_json_schema: bool = True,
    ) -> dict[str, Any]:
        """Return a parsed JSON object from chat messages.

        When supports_json_schema is False the provider must use json_object
        mode even if a schema is supplied — the model does not support the
        json_schema response format.
        """
