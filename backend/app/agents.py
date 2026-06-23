from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from opentelemetry import trace as _otel_trace
from opentelemetry.trace import Status as _OtelStatus, StatusCode as _OtelStatusCode

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
    word_validation_failure_reason,
)

MAX_LLM_ATTEMPTS = 5
LLM_RETRY_DELAY_SECONDS = 0.5
CAPACITY_RETRY_DELAYS_SECONDS = [2.0, 5.0]

logger = logging.getLogger("ai_contact.prompts")


def _language_name(language: str) -> str:
    return "Russian" if language == "ru" else "English"


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


def _candidate_signature(candidate: dict[str, Any]) -> str:
    return json.dumps(candidate, ensure_ascii=False, sort_keys=True, default=str)


def _build_retry_feedback(previous_answer: dict[str, Any], reason: str) -> str:
    previous_answer_json = json.dumps(
        previous_answer,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return "\n".join(
        [
            f"Previous answer: {previous_answer_json}",
            f"This is not valid because: {reason}",
            "This answer is not acceptable.",
            "Generate a new valid answer that fixes the validation failure.",
            "Do not repeat the previous answer.",
        ]
    )


async def _sleep_before_retry(
    *,
    task_name: str,
    prompt: RenderedPrompt,
    provider: LLMProvider,
    model: str,
    attempt: int,
    reason: str,
    delay_seconds: float = LLM_RETRY_DELAY_SECONDS,
    event_type: str = "llm_retry_scheduled",
) -> None:
    if attempt >= MAX_LLM_ATTEMPTS - 1:
        return
    write_event(
        event_type,
        taskName=task_name,
        promptId=prompt.id,
        promptVersion=prompt.version,
        provider=provider.name,
        model=model,
        attemptNumber=attempt + 1,
        retryDelaySeconds=delay_seconds,
        reason=reason,
    )
    await asyncio.sleep(delay_seconds)


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


def _llm_event(span: Any, name: str, attrs: dict[str, Any]) -> None:
    try:
        span.add_event(name, attrs)
    except Exception:
        pass


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

    _tracer = _otel_trace.get_tracer("ai-contact-game")
    _slug = task_name.lower().replace(" ", "_").replace(".", "")[:50]
    with _tracer.start_as_current_span(f"llm.{_slug}") as _span:
      try:
        _span.set_attribute("llm.task_name", task_name)
        _span.set_attribute("llm.provider", provider.name)
        _span.set_attribute("llm.model", model)
      except Exception:
        pass

      last_error = "Unknown LLM error."
      repair_feedback = ""
      api_failed = False
      validation_failed = False
      rejected_answer_signatures: set[str] = set()
      for attempt in range(MAX_LLM_ATTEMPTS):
        prompt = build_prompt(attempt, repair_feedback if validation_failed else "")
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
                retry_delay = error.retry_after_seconds or CAPACITY_RETRY_DELAYS_SECONDS[
                    min(attempt, len(CAPACITY_RETRY_DELAYS_SECONDS) - 1)
                ]
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
            _llm_event(_span, "llm.api_error", {"attempt": attempt + 1, "error": last_error[:200]})
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
            await _sleep_before_retry(
                task_name=task_name,
                prompt=prompt,
                provider=provider,
                model=model,
                attempt=attempt,
                reason=last_error,
                event_type="llm_api_retry_scheduled",
            )
            _llm_event(_span, "llm.api_error", {"attempt": attempt + 1, "error": last_error[:200]})
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
        candidate_signature = _candidate_signature(candidate)
        if candidate_signature in rejected_answer_signatures:
            ok = False
            value = None
            reason = "Generated answer is the same as a previously rejected answer."
        else:
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
            try:
                _span.set_attribute("llm.total_attempts", attempt + 1)
                _span.set_attribute("llm.success", True)
            except Exception:
                pass
            return value

        validation_failed = True
        rejected_answer_signatures.add(candidate_signature)
        last_error = reason or "Model JSON did not satisfy validation rules."
        repair_feedback = _build_retry_feedback(candidate, last_error)
        _log_validation_failure(
            task_name=task_name,
            prompt=prompt,
            provider=provider,
            model=model,
            attempt=attempt,
            reason=last_error,
            candidate=candidate,
        )
        await _sleep_before_retry(
            task_name=task_name,
            prompt=prompt,
            provider=provider,
            model=model,
            attempt=attempt,
            reason=last_error,
            event_type="llm_validation_retry_scheduled",
        )
        _llm_event(_span, "llm.validation_retry", {"attempt": attempt + 1, "reason": last_error[:200]})

      try:
        _span.set_attribute("llm.success", False)
        _span.set_attribute("llm.total_attempts", MAX_LLM_ATTEMPTS)
        _span.set_status(_OtelStatus(_OtelStatusCode.ERROR, last_error[:200]))
      except Exception:
        pass
      if validation_failed and not api_failed:
        raise LLMValidationError(f"{task_name} failed validation after retries. {last_error}")
      raise LLMGameError(f"{task_name} failed after retries. {last_error}")


def validate_player_move_output(
    candidate: dict[str, Any],
    *,
    language: str,
    current_prefix: str,
    used_words: list[str],
) -> tuple[bool, PlayerMove | None, str]:
    used = {normalize_word(word, language) for word in used_words}
    raw_intended_word = candidate.get("intendedWord")
    intended_word = normalize_word(raw_intended_word, language)
    clue = str(candidate.get("clue") or "").strip()
    if not is_valid_word(raw_intended_word, language):
        return (
            False,
            None,
            word_validation_failure_reason(raw_intended_word, language, "intendedWord"),
        )
    if not starts_with_prefix(intended_word, current_prefix, language):
        return (
            False,
            None,
            (
                f"intendedWord={intended_word!r} does not start with required currentPrefix={current_prefix!r} "
                "after trim/lowercase normalization."
            ),
        )
    if intended_word in used:
        return (
            False,
            None,
            (
                f"intendedWord={intended_word!r} is already in usedWords/forbiddenWords. "
                "Choose a different normal word with the same prefix."
            ),
        )
    if not clue:
        return False, None, "clue is empty or missing."
    if clue_mentions_word(clue, intended_word, language):
        return False, None, f"clue directly mentions intendedWord={intended_word!r}."
    return True, PlayerMove(intendedWord=intended_word, clue=clue), ""


def validate_master_guess_output(
    candidate: dict[str, Any],
    *,
    language: str,
    secret_word: str,
    current_prefix: str,
    used_words: list[str],
) -> tuple[bool, MasterGuess, str]:
    used = {normalize_word(word, language) for word in used_words}
    secret = normalize_word(secret_word, language)
    raw_guess = candidate.get("guess")
    refused_values = {"", "null", "none", "no guess", "нет", "нет догадки"}
    if raw_guess is None or str(raw_guess).strip().lower() in refused_values:
        return (
            False,
            MasterGuess(guess="", confidence=0),
            "guess is empty or a refusal; Word Master must choose one concrete guess.",
        )
    try:
        confidence = float(candidate.get("confidence") or 0)
    except (TypeError, ValueError):
        return False, MasterGuess(guess="", confidence=0), "confidence must be a number from 0 to 1."

    guess = normalize_word(raw_guess, language)
    if not is_valid_word(raw_guess, language):
        return (
            False,
            MasterGuess(guess="", confidence=0),
            word_validation_failure_reason(raw_guess, language, "guess"),
        )
    if not starts_with_prefix(guess, current_prefix, language):
        return (
            False,
            MasterGuess(guess="", confidence=0),
            f"guess={guess!r} does not start with required currentPrefix={current_prefix!r}.",
        )
    if guess in used:
        return (
            False,
            MasterGuess(guess="", confidence=0),
            f"guess={guess!r} is already in usedWords/forbiddenWords.",
        )
    if same_word(guess, secret, language):
        return (
            False,
            MasterGuess(guess="", confidence=0),
            "guess equals the secret word; choose a different valid word.",
        )
    return True, MasterGuess(guess=guess, confidence=max(0, min(1, confidence))), ""


def validate_partner_guess_output(
    candidate: dict[str, Any],
    *,
    language: str,
    current_prefix: str,
    used_words: list[str],
) -> tuple[bool, PartnerGuess | None, str]:
    used = {normalize_word(word, language) for word in used_words}
    raw_guess = candidate.get("guess")
    guess = normalize_word(raw_guess, language)
    if not is_valid_word(raw_guess, language):
        return False, None, word_validation_failure_reason(raw_guess, language, "guess")
    if not starts_with_prefix(guess, current_prefix, language):
        return False, None, f"guess={guess!r} does not start with required currentPrefix={current_prefix!r}."
    if guess in used:
        return (
            False,
            None,
            f"guess={guess!r} is already in usedWords/forbiddenWords. "
            "Choose a different word with the same prefix.",
        )
    return True, PartnerGuess(guess=guess), ""


async def choose_secret_word(
    *,
    provider: LLMProvider,
    models: AgentModelConfig,
    language: str,
) -> dict[str, str]:
    def validate(candidate: dict[str, Any]) -> tuple[bool, dict[str, str] | None, str]:
        raw_word = candidate.get("word")
        word = normalize_word(raw_word, language)
        if not is_valid_word(raw_word, language):
            return False, None, word_validation_failure_reason(raw_word, language, "word")
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
    word_master_decoded_examples: list[dict[str, str]] | None = None,
) -> PlayerMove:
    def validate(candidate: dict[str, Any]) -> tuple[bool, PlayerMove | None, str]:
        return validate_player_move_output(
            candidate,
            language=language,
            current_prefix=current_prefix,
            used_words=used_words,
        )

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
                "usedWords": used_words,
                "forbiddenWords": used_words,
                "publicHistory": public_history,
                "sessionHistory": public_history,
                "allPreviousStepsInCurrentSession": public_history,
                "wordMasterDecodedExamples": word_master_decoded_examples or [],
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
    def validate(candidate: dict[str, Any]) -> tuple[bool, MasterGuess, str]:
        return validate_master_guess_output(
            candidate,
            language=language,
            secret_word=secret_word,
            current_prefix=current_prefix,
            used_words=used_words,
        )

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
                "secretWord": normalize_word(secret_word, language),
                "currentPrefix": current_prefix,
                "clue": clue,
                "usedWords": used_words,
                "forbiddenWords": used_words,
                "publicHistory": public_history,
                "sessionHistory": public_history,
                "allPreviousStepsInCurrentSession": public_history,
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
    word_master_decoded_examples: list[dict[str, str]] | None = None,
) -> PartnerGuess:
    def validate(candidate: dict[str, Any]) -> tuple[bool, PartnerGuess | None, str]:
        return validate_partner_guess_output(
            candidate,
            language=language,
            current_prefix=current_prefix,
            used_words=used_words,
        )

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
                "usedWords": used_words,
                "forbiddenWords": used_words,
                "publicHistory": public_history,
                "sessionHistory": public_history,
                "allPreviousStepsInCurrentSession": public_history,
                "wordMasterDecodedExamples": word_master_decoded_examples or [],
                "personality": personality or "",
                "requiredOutputKeys": ["guess"],
            },
        ),
        validate=validate,
        task_name=f"Guessing partner word for {player_name}",
        response_schema=_pydantic_schema(PartnerGuess),
    )
