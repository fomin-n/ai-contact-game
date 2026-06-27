from __future__ import annotations

from dataclasses import dataclass

from .providers.factory import create_provider
from .schemas import ModelOption, ProviderModelCatalog


@dataclass(frozen=True)
class CatalogModel:
    id: str
    display_name: str
    description: str
    recommended_for: str
    supports_json_schema: bool = True


CATALOG_MODELS: dict[str, list[CatalogModel]] = {
    "mistral": [
        CatalogModel(
            id="mistral-small-latest",
            display_name="Mistral Small",
            description="Fast general-purpose Mistral model.",
            recommended_for="balanced",
        ),
        CatalogModel(
            id="mistral-medium-latest",
            display_name="Mistral Medium",
            description="Stronger option when Small is rate-limited or too weak.",
            recommended_for="strong",
        ),
        CatalogModel(
            id="mistral-large-latest",
            display_name="Mistral Large",
            description="Highest-quality Mistral option in this catalog.",
            recommended_for="strong",
        ),
    ],
    "openai": [
        CatalogModel(
            id="gpt-4.1-mini",
            display_name="GPT-4.1 mini",
            description="Efficient OpenAI-compatible option for players.",
            recommended_for="balanced",
        ),
        CatalogModel(
            id="gpt-4.1",
            display_name="GPT-4.1",
            description="Stronger OpenAI-compatible option.",
            recommended_for="strong",
        ),
        CatalogModel(
            id="gpt-4o-mini",
            display_name="GPT-4o mini",
            description="Low-cost OpenAI-compatible option.",
            recommended_for="cheap",
        ),
    ],
}


PROVIDER_IDS = tuple(CATALOG_MODELS.keys())


def known_provider_ids() -> set[str]:
    return set(PROVIDER_IDS)


def model_supports_json_schema(provider_id: str, model_id: str) -> bool:
    """Return whether a catalog model supports the json_schema response format.

    Returns True for unknown/custom models (conservative: assume support unless
    the catalog explicitly flags otherwise).
    """
    for model in CATALOG_MODELS.get(provider_id, []):
        if model.id == model_id:
            return model.supports_json_schema
    return True


def build_model_catalog() -> list[ProviderModelCatalog]:
    catalog: list[ProviderModelCatalog] = []
    for provider_id in PROVIDER_IDS:
        provider = create_provider(provider_id)
        default_model = provider.default_model
        model_options = [
            ModelOption(
                id=model.id,
                displayName=model.display_name,
                description=model.description,
                recommendedFor=model.recommended_for,
                isDefault=model.id == default_model,
                supportsJsonSchema=model.supports_json_schema,
            )
            for model in CATALOG_MODELS[provider_id]
        ]
        if default_model and all(option.id != default_model for option in model_options):
            model_options.append(
                ModelOption(
                    id=default_model,
                    displayName=default_model,
                    description="Custom default model from environment.",
                    recommendedFor="custom",
                    isDefault=True,
                    isCustom=True,
                    supportsJsonSchema=True,
                )
            )
        catalog.append(
            ProviderModelCatalog(
                id=provider.name,
                displayName=provider.display_name,
                hasApiKey=provider.has_api_key,
                defaultModel=default_model,
                models=model_options,
            )
        )
    return catalog
