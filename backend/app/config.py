from __future__ import annotations

import os
from dataclasses import dataclass

from .model_catalog import known_provider_ids
from .providers.base import LLMProvider
from .providers.factory import create_provider
from .schemas import (
    AgentModelConfig,
    AgentModelInfo,
    AgentModelSelection,
    AgentProviderInfo,
    ProviderInfo,
    RoleModelSelection,
)


@dataclass(frozen=True)
class AgentProviderConfig:
    word_master_provider: LLMProvider
    player_a_provider: LLMProvider
    player_b_provider: LLMProvider


def _env_first(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def load_agent_provider_config() -> AgentProviderConfig:
    default_provider_name = os.getenv("AI_PROVIDER", "mistral")
    return AgentProviderConfig(
        word_master_provider=create_provider(os.getenv("WORD_MASTER_PROVIDER", default_provider_name)),
        player_a_provider=create_provider(os.getenv("PLAYER_A_PROVIDER", default_provider_name)),
        player_b_provider=create_provider(os.getenv("PLAYER_B_PROVIDER", default_provider_name)),
    )


def _model_for_role(role_env: str, provider: LLMProvider) -> str:
    provider_prefix = provider.name.upper()
    return _env_first(
        f"{role_env}_MODEL",
        f"{provider_prefix}_{role_env}_MODEL",
        default=getattr(provider, "default_model", "unknown-model"),
    )


def load_agent_model_config(providers: AgentProviderConfig) -> AgentModelConfig:
    return AgentModelConfig(
        word_master_model=_model_for_role("WORD_MASTER", providers.word_master_provider),
        player_a_model=_model_for_role("PLAYER_A", providers.player_a_provider),
        player_b_model=_model_for_role("PLAYER_B", providers.player_b_provider),
    )


def default_agent_model_selection(providers: AgentProviderConfig, models: AgentModelConfig) -> AgentModelSelection:
    return AgentModelSelection(
        wordMaster=RoleModelSelection(
            provider=providers.word_master_provider.name,
            model=models.word_master_model,
        ),
        playerA=RoleModelSelection(
            provider=providers.player_a_provider.name,
            model=models.player_a_model,
        ),
        playerB=RoleModelSelection(
            provider=providers.player_b_provider.name,
            model=models.player_b_model,
        ),
    )


def _normalize_provider_id(provider_id: str) -> str:
    return provider_id.strip().lower()


def _validate_role_selection(role_name: str, selection: RoleModelSelection) -> tuple[LLMProvider, str]:
    provider_id = _normalize_provider_id(selection.provider)
    if provider_id not in known_provider_ids():
        raise ValueError(f"Unknown provider for {role_name}: {selection.provider}")
    model = selection.model.strip()
    if not model:
        raise ValueError(f"Model id for {role_name} must not be empty.")
    provider = create_provider(provider_id)
    if not provider.has_api_key:
        raise ValueError(f"{provider.display_name} API key is not configured for {role_name}.")
    return provider, model


def resolve_agent_configs(
    selection: AgentModelSelection | None,
    default_providers: AgentProviderConfig,
    default_models: AgentModelConfig,
) -> tuple[AgentProviderConfig, AgentModelConfig]:
    if selection is None:
        for role_name, provider in (
            ("Word Master", default_providers.word_master_provider),
            ("Player A", default_providers.player_a_provider),
            ("Player B", default_providers.player_b_provider),
        ):
            if not provider.has_api_key:
                raise ValueError(f"{provider.display_name} API key is not configured for {role_name}.")
        return default_providers, default_models

    word_master_provider, word_master_model = _validate_role_selection("Word Master", selection.wordMaster)
    player_a_provider, player_a_model = _validate_role_selection("Player A", selection.playerA)
    player_b_provider, player_b_model = _validate_role_selection("Player B", selection.playerB)
    return (
        AgentProviderConfig(
            word_master_provider=word_master_provider,
            player_a_provider=player_a_provider,
            player_b_provider=player_b_provider,
        ),
        AgentModelConfig(
            word_master_model=word_master_model,
            player_a_model=player_a_model,
            player_b_model=player_b_model,
        ),
    )


def provider_info(providers: AgentProviderConfig, models: AgentModelConfig) -> ProviderInfo:
    unique_provider_names = {
        providers.word_master_provider.name,
        providers.player_a_provider.name,
        providers.player_b_provider.name,
    }
    display_name = (
        providers.word_master_provider.display_name
        if len(unique_provider_names) == 1
        else "Mixed providers"
    )
    return ProviderInfo(
        provider=providers.word_master_provider.name if len(unique_provider_names) == 1 else "mixed",
        displayName=display_name,
        hasApiKey=(
            providers.word_master_provider.has_api_key
            and providers.player_a_provider.has_api_key
            and providers.player_b_provider.has_api_key
        ),
        models=AgentModelInfo(
            wordMasterModel=models.word_master_model,
            playerAModel=models.player_a_model,
            playerBModel=models.player_b_model,
        ),
        providers=AgentProviderInfo(
            wordMasterProvider=providers.word_master_provider.name,
            wordMasterDisplayName=providers.word_master_provider.display_name,
            wordMasterHasApiKey=providers.word_master_provider.has_api_key,
            playerAProvider=providers.player_a_provider.name,
            playerADisplayName=providers.player_a_provider.display_name,
            playerAHasApiKey=providers.player_a_provider.has_api_key,
            playerBProvider=providers.player_b_provider.name,
            playerBDisplayName=providers.player_b_provider.display_name,
            playerBHasApiKey=providers.player_b_provider.has_api_key,
        ),
    )
