from __future__ import annotations

import os

from .base import LLMProvider
from .mistral import MistralProvider
from .openai_compatible import OpenAICompatibleProvider


def create_provider(provider_name: str | None = None) -> LLMProvider:
    provider = (provider_name or os.getenv("AI_PROVIDER", "mistral")).strip().lower()
    if provider == "mistral":
        return MistralProvider()
    if provider == "openai":
        return OpenAICompatibleProvider()
    raise ValueError(f"Unsupported AI_PROVIDER: {provider}")
