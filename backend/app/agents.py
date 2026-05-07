from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel

from .event_log import write_event
from .prompt_loader import RenderedPrompt, render_prompt
from .providers.base import LLMProvider
from .providers.http_json import MissingApiKeyError, ProviderCapacityError
from .schemas import AgentModelConfig, MasterGuess, PartnerGuess, PlayerMove, PlayerRole, SecretWord
from .word_utils import (
    clue_mentions_word,
    is_valid_word,
    normalize_word,
    same_word,
    starts_with_prefix,
)

MAX_LLM_ATTEMPTS = 3
CAPACITY_RETRY_DELAYS_SECONDS = [2.0, 5.0]

logger = logging.getLogger("ai_contact.prompts")


def _language_name(language: str) -> str:
    return "Russian" if language == "ru" else "English"


def _compact(values: list[str], limit: int = 40) -> list[str]:
    return values[-limit:] if values else []


def _player_model(role: PlayerRole, models: AgentModelConfig) -> str:
    return models.player_a_model if role == "playerA" else models.player_b_model


def _pydantic_schema(model_type: type[BaseModel]) -> dict[str, Any]:
    if hasattr(model_type, "model_json_schema"):
        return model_type.model_json_schema()
    return model_type.schema()


class LLMGameError(RuntimeError):
    pass


class LLMValidationError(LLMGameError):
    pass


def _format_exception(error: Exception) -> str:
    if isinstance(error, ProviderCapacityError):
        return str(error)
    if isinstance(error, httpx.HTTPStatusError):
        return str(error)
    if isinstance(error, MissingApiKeyError):
        return str(error)
    return f"{type(error).__name__}: {error}"


def _log_prompt_call(
    *,
    task_name: str,
    prompt: RenderedPrompt,
    provider: LLMProvider,
    model: str,
    attempt: int,
    validation_failure_reason: str = "",
) -> None:
    metadata = {
        "taskName": task_name,
        "promptId": prompt.id,
        "promptVersion": prompt.version,
        "provider": provider.name,
        "model": model,
        "attemptNumber": attempt + 1,
    }
    if validation_failure_reason:
        metadata["validationFailureReason"] = validation_failure_reason
    logger.info("llm_prompt_call %s", json.dumps(metadata, ensure_ascii=False))
    write_event(
        "llm_prompt_call",
        **metadata,
        temperature=prompt.temperature,
        modelRole=prompt.model_role,
        schema=prompt.schema,
        messages=prompt.messages,
    )


def _log_validation_failure(
    *,
    task_name: str,
    prompt: RenderedPrompt,
    provider: LLMProvider,
    model: str,
    attempt: int,
    reason: str,
    candidate: dict[str, Any] | None = None,
) -> None:
    metadata = {
        "taskName": task_name,
        "promptId": prompt.id,
        "promptVersion": prompt.version,
        "provider": provider.name,
        "model": model,
        "attemptNumber": attempt + 1,
        "validationFailureReason": reason,
    }
    logger.warning("llm_validation_failure %s", json.dumps(metadata, ensure_ascii=False))
    write_event(
        "llm_validation_failure",
        **metadata,
        candidate=candidate,
    )


async def _with_repair(
    *,
    provider: LLMProvider,
    model: str,
    build_prompt: Callable[[int, str], RenderedPrompt],
    validate: Callable[[dict[str, Any]], tuple[bool, Any, str]],
    task_name: str,
    response_schema: dict[str, Any],
) -> Any:
    if not provider.has_api_key:
        key_name = f"{provider.name.upper()}_API_KEY"
        raise LLMGameError(
            f"{provider.display_name} API key is not configured. Set {key_name} and restart the backend."
        )

    last_error = "Unknown LLM error."
    api_failed = False
    validation_failed = False
    for attempt in range(MAX_LLM_ATTEMPTS):
        prompt = build_prompt(attempt, last_error if validation_failed else "")
        _log_prompt_call(
            task_name=task_name,
            prompt=prompt,
            provider=provider,
            model=model,
            attempt=attempt,
            validation_failure_reason=last_error if validation_failed else "",
        )
        try:
            candidate = await provider.chat_json(
                messages=prompt.messages,
                schema=response_schema or prompt.schema,
                model=model,
                temperature=prompt.temperature,
            )
        except ProviderCapacityError as error:
            api_failed = True
            last_error = _format_exception(error)
            logger.warning(
                "llm_api_failure %s",
                json.dumps(
                    {
                        "taskName": task_name,
                        "promptId": prompt.id,
                        "promptVersion": prompt.version,
                        "provider": provider.name,
                        "model": model,
                        "attemptNumber": attempt + 1,
                        "validationFailureReason": last_error,
                    },
                    ensure_ascii=False,
                ),
            )
            write_event(
                "llm_api_failure",
                taskName=task_name,
                promptId=prompt.id,
                promptVersion=prompt.version,
                provider=provider.name,
                model=model,
                attemptNumber=attempt + 1,
                error=error,
            )
            if attempt < MAX_LLM_ATTEMPTS - 1:
                retry_delay = error.retry_after_seconds or CAPACITY_RETRY_DELAYS_SECONDS[min(attempt, len(CAPACITY_RETRY_DELAYS_SECONDS) - 1)]
                write_event(
                    "llm_api_retry_scheduled",
                    taskName=task_name,
                    promptId=prompt.id,
                    promptVersion=prompt.version,
                    provider=provider.name,
                    model=model,
                    attemptNumber=attempt + 1,
                    retryDelaySeconds=retry_delay,
                    reason=last_error,
                )
                await asyncio.sleep(retry_delay)
            continue
        except (MissingApiKeyError, ValueError, KeyError, TypeError, httpx.HTTPError) as error:
            api_failed = True
            last_error = _format_exception(error)
            logger.warning(
                "llm_api_failure %s",
                json.dumps(
                    {
                        "taskName": task_name,
                        "promptId": prompt.id,
                        "promptVersion": prompt.version,
                        "provider": provider.name,
                        "model": model,
                        "attemptNumber": attempt + 1,
                        "validationFailureReason": last_error,
                    },
                    ensure_ascii=False,
                ),
            )
            write_event(
                "llm_api_failure",
                taskName=task_name,
                promptId=prompt.id,
                promptVersion=prompt.version,
                provider=provider.name,
                model=model,
                attemptNumber=attempt + 1,
                error=error,
            )
            continue

        write_event(
            "llm_candidate_received",
            taskName=task_name,
            promptId=prompt.id,
            promptVersion=prompt.version,
            provider=provider.name,
            model=model,
            attemptNumber=attempt + 1,
            candidate=candidate,
        )
        try:
            ok, value, reason = validate(candidate)
        except (ValueError, KeyError, TypeError) as error:
            ok = False
            value = None
            reason = f"Validation raised {type(error).__name__}: {error}"
        if ok:
            write_event(
                "llm_validation_success",
                taskName=task_name,
                promptId=prompt.id,
                promptVersion=prompt.version,
                provider=provider.name,
                model=model,
                attemptNumber=attempt + 1,
                value=value,
            )
            return value

        validation_failed = True
        last_error = reason or "Model JSON did not satisfy validation rules."
        _log_validation_failure(
            task_name=task_name,
            prompt=prompt,
            provider=provider,
            model=model,
            attempt=attempt,
            reason=last_error,
            candidate=candidate,
        )

    if validation_failed and not api_failed:
        raise LLMValidationError(f"{task_name} failed validation after retries. {last_error}")
    raise LLMGameError(f"{task_name} failed after retries. {last_error}")


async def choose_secret_word(
    *,
    provider: LLMProvider,
    models: AgentModelConfig,
    language: str,
) -> dict[str, str]:
    def validate(candidate: dict[str, Any]) -> tuple[bool, dict[str, str] | None, str]:
        word = normalize_word(candidate.get("word"), language)
        if not is_valid_word(word, language):
            return False, None, "Invalid secret word."
        return True, {"word": word}, ""

    return await _with_repair(
        provider=provider,
        model=models.word_master_model,
        build_prompt=lambda attempt, repair_feedback: render_prompt(
            "choose_secret_word",
            attempt=attempt,
            repair_feedback=repair_feedback,
            payload={
                "language": language,
                "languageName": _language_name(language),
                "requiredOutputKeys": ["word"],
            },
        ),
        validate=validate,
        task_name="Choosing a secret word",
        response_schema=_pydantic_schema(SecretWord),
    )


async def generate_player_move(
    *,
    provider: LLMProvider,
    models: AgentModelConfig,
    player_name: str,
    player_role: PlayerRole,
    language: str,
    current_prefix: str,
    public_history: list[str],
    used_words: list[str],
    personality: str,
) -> PlayerMove:
    used = {normalize_word(word, language) for word in used_words}

    def validate(candidate: dict[str, Any]) -> tuple[bool, PlayerMove | None, str]:
        intended_word = normalize_word(candidate.get("intendedWord"), language)
        clue = str(candidate.get("clue") or "").strip()
        if not is_valid_word(intended_word, language):
            return False, None, "Invalid intended word."
        if not starts_with_prefix(intended_word, current_prefix, language):
            return (
                False,
                None,
                (
                    f"Intended word must begin exactly with currentPrefix={current_prefix!r} "
                    "after trim/lowercase normalization."
                ),
            )
        if intended_word in used:
            return (
                False,
                None,
                "Selected intended word is already in usedWords. Choose a different normal word with the same prefix.",
            )
        if not clue:
            return False, None, "Missing clue."
        if clue_mentions_word(clue, intended_word, language):
            return False, None, "Clue contains intended word."
        return True, PlayerMove(intendedWord=intended_word, clue=clue), ""

    return await _with_repair(
        provider=provider,
        model=_player_model(player_role, models),
        build_prompt=lambda attempt, repair_feedback: render_prompt(
            "generate_player_move",
            attempt=attempt,
            repair_feedback=repair_feedback,
            payload={
                "playerName": player_name,
                "playerRole": player_role,
                "language": language,
                "languageName": _language_name(language),
                "currentPrefix": current_prefix,
                "usedWords": _compact(used_words),
                "forbiddenWords": _compact(used_words),
                "publicHistory": _compact(public_history, 24),
                "personality": personality or "",
                "requiredOutputKeys": ["intendedWord", "clue"],
            },
        ),
        validate=validate,
        task_name=f"Generating move for {player_name}",
        response_schema=_pydantic_schema(PlayerMove),
    )


async def word_master_guess(
    *,
    provider: LLMProvider,
    models: AgentModelConfig,
    language: str,
    secret_word: str,
    current_prefix: str,
    clue: str,
    public_history: list[str],
    used_words: list[str],
) -> MasterGuess:
    used = {normalize_word(word, language) for word in used_words}
    secret = normalize_word(secret_word, language)

    def validate(candidate: dict[str, Any]) -> tuple[bool, MasterGuess, str]:
        raw_guess = candidate.get("guess")
        confidence = float(candidate.get("confidence") or 0)
        if raw_guess is None or str(raw_guess).strip().lower() in {"", "null", "none", "no guess", "нет", "нет догадки"}:
            return False, MasterGuess(guess="", confidence=0), "Word Master must choose one concrete guess."

        guess = normalize_word(raw_guess, language)
        if not is_valid_word(guess, language):
            return False, MasterGuess(guess="", confidence=0), "Invalid guess."
        if not starts_with_prefix(guess, current_prefix, language):
            return False, MasterGuess(guess="", confidence=0), "Guess misses prefix."
        if guess in used:
            return False, MasterGuess(guess="", confidence=0), "Guess is already in usedWords."
        if same_word(guess, secret, language):
            return False, MasterGuess(guess="", confidence=0), "Guess equals the secret word."
        return True, MasterGuess(guess=guess, confidence=max(0, min(1, confidence))), ""

    return await _with_repair(
        provider=provider,
        model=models.word_master_model,
        build_prompt=lambda attempt, repair_feedback: render_prompt(
            "word_master_guess",
            attempt=attempt,
            repair_feedback=repair_feedback,
            payload={
                "language": language,
                "languageName": _language_name(language),
                "secretWord": secret,
                "currentPrefix": current_prefix,
                "clue": clue,
                "usedWords": _compact(used_words),
                "forbiddenWords": _compact(used_words),
                "publicHistory": _compact(public_history, 24),
                "requiredOutputKeys": ["guess", "confidence"],
            },
        ),
        validate=validate,
        task_name="Word Master guessing",
        response_schema=_pydantic_schema(MasterGuess),
    )


async def guess_partner_word(
    *,
    provider: LLMProvider,
    models: AgentModelConfig,
    player_name: str,
    player_role: PlayerRole,
    language: str,
    current_prefix: str,
    clue: str,
    public_history: list[str],
    used_words: list[str],
    personality: str,
) -> PartnerGuess:
    used = {normalize_word(word, language) for word in used_words}

    def validate(candidate: dict[str, Any]) -> tuple[bool, PartnerGuess | None, str]:
        guess = normalize_word(candidate.get("guess"), language)
        if not is_valid_word(guess, language):
            return False, None, "Invalid partner guess."
        if not starts_with_prefix(guess, current_prefix, language):
            return False, None, "Partner guess misses prefix."
        if guess in used:
            return False, None, "Partner guess already used. Choose a different word with the same prefix."
        return True, PartnerGuess(guess=guess), ""

    return await _with_repair(
        provider=provider,
        model=_player_model(player_role, models),
        build_prompt=lambda attempt, repair_feedback: render_prompt(
            "guess_partner_word",
            attempt=attempt,
            repair_feedback=repair_feedback,
            payload={
                "playerName": player_name,
                "playerRole": player_role,
                "language": language,
                "languageName": _language_name(language),
                "currentPrefix": current_prefix,
                "clue": clue,
                "usedWords": _compact(used_words),
                "forbiddenWords": _compact(used_words),
                "publicHistory": _compact(public_history, 24),
                "personality": personality or "",
                "requiredOutputKeys": ["guess"],
            },
        ),
        validate=validate,
        task_name=f"Guessing partner word for {player_name}",
        response_schema=_pydantic_schema(PartnerGuess),
    )
