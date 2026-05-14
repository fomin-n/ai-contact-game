from __future__ import annotations

import os
from unittest import TestCase
from unittest.mock import patch

from backend.app.config import (
    load_agent_model_config,
    load_agent_provider_config,
    provider_info,
    resolve_agent_configs,
)
from backend.app.schemas import AgentModelSelection, RoleModelSelection


def selection(
    *,
    word_master: tuple[str, str],
    player_a: tuple[str, str],
    player_b: tuple[str, str],
) -> AgentModelSelection:
    return AgentModelSelection(
        wordMaster=RoleModelSelection(provider=word_master[0], model=word_master[1]),
        playerA=RoleModelSelection(provider=player_a[0], model=player_a[1]),
        playerB=RoleModelSelection(provider=player_b[0], model=player_b[1]),
    )


class ModelSelectionTests(TestCase):
    def test_default_env_provider_and_model_config_still_works(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "mistral",
                "MISTRAL_API_KEY": "test-key",
                "MISTRAL_MODEL": "mistral-medium-latest",
            },
            clear=True,
        ):
            providers = load_agent_provider_config()
            models = load_agent_model_config(providers)

        self.assertEqual(providers.word_master_provider.name, "mistral")
        self.assertEqual(providers.player_a_provider.name, "mistral")
        self.assertEqual(providers.player_b_provider.name, "mistral")
        self.assertEqual(models.word_master_model, "mistral-medium-latest")
        self.assertEqual(models.player_a_model, "mistral-medium-latest")
        self.assertEqual(models.player_b_model, "mistral-medium-latest")

    def test_role_level_selection_overrides_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MISTRAL_API_KEY": "test-mistral-key",
                "OPENAI_API_KEY": "test-openai-key",
            },
            clear=True,
        ):
            default_providers = load_agent_provider_config()
            default_models = load_agent_model_config(default_providers)
            providers, models = resolve_agent_configs(
                selection(
                    word_master=("mistral", "mistral-large-latest"),
                    player_a=("openai", "gpt-4.1"),
                    player_b=("openai", "gpt-4.1-mini"),
                ),
                default_providers,
                default_models,
            )

        self.assertEqual(providers.word_master_provider.name, "mistral")
        self.assertEqual(providers.player_a_provider.name, "openai")
        self.assertEqual(providers.player_b_provider.name, "openai")
        self.assertEqual(models.word_master_model, "mistral-large-latest")
        self.assertEqual(models.player_a_model, "gpt-4.1")
        self.assertEqual(models.player_b_model, "gpt-4.1-mini")

    def test_missing_api_key_fails_early(self) -> None:
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "test-mistral-key"}, clear=True):
            default_providers = load_agent_provider_config()
            default_models = load_agent_model_config(default_providers)
            with self.assertRaisesRegex(ValueError, "API key is not configured"):
                resolve_agent_configs(
                    selection(
                        word_master=("mistral", "mistral-small-latest"),
                        player_a=("openai", "gpt-4.1-mini"),
                        player_b=("mistral", "mistral-small-latest"),
                    ),
                    default_providers,
                    default_models,
                )

    def test_unknown_provider_fails(self) -> None:
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "test-mistral-key"}, clear=True):
            default_providers = load_agent_provider_config()
            default_models = load_agent_model_config(default_providers)
            with self.assertRaisesRegex(ValueError, "Unknown provider"):
                resolve_agent_configs(
                    selection(
                        word_master=("unknown", "model"),
                        player_a=("mistral", "mistral-small-latest"),
                        player_b=("mistral", "mistral-small-latest"),
                    ),
                    default_providers,
                    default_models,
                )

    def test_custom_non_empty_model_for_known_provider_is_accepted(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}, clear=True):
            default_providers = load_agent_provider_config()
            default_models = load_agent_model_config(default_providers)
            providers, models = resolve_agent_configs(
                selection(
                    word_master=("openai", "future-custom-model"),
                    player_a=("openai", "future-custom-model"),
                    player_b=("openai", "future-custom-model"),
                ),
                default_providers,
                default_models,
            )

        self.assertEqual(providers.word_master_provider.name, "openai")
        self.assertEqual(models.word_master_model, "future-custom-model")
        self.assertEqual(models.player_a_model, "future-custom-model")
        self.assertEqual(models.player_b_model, "future-custom-model")

    def test_provider_info_reflects_selected_models(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MISTRAL_API_KEY": "test-mistral-key",
                "OPENAI_API_KEY": "test-openai-key",
            },
            clear=True,
        ):
            default_providers = load_agent_provider_config()
            default_models = load_agent_model_config(default_providers)
            providers, models = resolve_agent_configs(
                selection(
                    word_master=("mistral", "mistral-medium-latest"),
                    player_a=("openai", "gpt-4.1"),
                    player_b=("openai", "gpt-4.1-mini"),
                ),
                default_providers,
                default_models,
            )
            info = provider_info(providers, models)

        self.assertEqual(info.provider, "mixed")
        self.assertEqual(info.models.wordMasterModel, "mistral-medium-latest")
        self.assertEqual(info.models.playerAModel, "gpt-4.1")
        self.assertEqual(info.providers.playerAProvider, "openai")
