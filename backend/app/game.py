from __future__ import annotations

import asyncio
import copy
import time
import uuid

from .agents import (
    LLMGameError,
    LLMValidationError,
    choose_secret_word,
    generate_player_move,
    guess_partner_word,
    validate_master_guess_output,
    validate_partner_guess_output,
    validate_player_move_output,
    word_master_guess,
)
from .config import AgentProviderConfig, provider_info
from .event_log import write_event
from .schemas import (
    AgentModelConfig,
    GameMessage,
    GameState,
    HumanRole,
    MasterGuess,
    PartnerGuess,
    PendingUserInput,
    PlayerMove,
    PlayerRole,
    ProviderInfo,
    StartGameRequest,
    UserInputRequest,
)
from .word_utils import compute_max_turns, first_letters, is_valid_word, normalize_word, same_word

COPY = {
    "en": {
        "playerA": "Player A",
        "playerB": "Player B",
        "players": "Players",
        "wordMaster": "Word Master",
        "system": "System",
        "wordMasterChose": "Word Master chose a secret word.",
        "prefix": "Current prefix:",
        "contactSucceeded": "Contact succeeded.",
        "contactFailed": "Contact failed.",
        "blocked": "Word Master guessed. Contact broken.",
        "failedIntercept": "There is contact!",
        "wordMasterNoGuess": "Word Master couldn't guess.",
        "wordMasterDecodedBlockedReason": "Word Master decoded this clue and blocked contact.",
        "gameOver": "Game over.",
        "maxTurns": "Maximum number of attempts reached.",
        "playersFound": "Players found the secret word.",
        "fullPrefix": "The full secret word has been revealed.",
        "apiError": "Game stopped because the backend game loop failed.",
        "validationError": "The AI response did not satisfy the game rules after retries.",
        "troubleshooting": (
            "Try: confirm the required API keys are exported in the backend shell, restart uvicorn, "
            "check provider quota/credits, and inspect the backend terminal for HTTP details. "
            "For HTTP 429 service-tier capacity errors, wait a bit or switch the affected role to another available model/provider."
        ),
        "validationTips": (
            "This usually means the model repeated a used word, picked the hidden secret word by coincidence, "
            "or returned a word that does not match the current prefix. Try again, or use a stronger model."
        ),
        "invalidCustomSecret": "Custom secret word must be one valid single word for the selected language.",
        "usedWordsFinal": "Used words:",
        "secretFinal": "Secret word:",
        "turnsFinal": "Attempts:",
        "winnerFinal": "Winner:",
        "wordMasterGuessPrompt": "Word Master, guess the encoded word.",
        "wordMasterGuessPlaceholder": "Enter your guess...",
        "playerMovePrompt": "Player A, send an encrypted clue.",
        "playerMovePlaceholder": "Encrypted clue",
        "partnerGuessPrompt": "Player A, guess the word Player B encoded.",
        "partnerGuessPlaceholder": "Enter the word you think Player B encoded...",
    },
    "ru": {
        "playerA": "Игрок A",
        "playerB": "Игрок B",
        "players": "Игроки",
        "wordMaster": "Ведущий",
        "system": "Система",
        "wordMasterChose": "Ведущий выбрал секретное слово.",
        "prefix": "Текущий префикс:",
        "contactSucceeded": "Контакт состоялся.",
        "contactFailed": "Контакт не состоялся.",
        "blocked": "Ведущий угадал. Контакт оборван.",
        "failedIntercept": "Есть контакт!",
        "wordMasterNoGuess": "Ведущий не догадался.",
        "wordMasterDecodedBlockedReason": "Ведущий расшифровал подсказку и оборвал контакт.",
        "gameOver": "Игра окончена.",
        "maxTurns": "Достигнут лимит попыток.",
        "playersFound": "Игроки нашли секретное слово.",
        "fullPrefix": "Секретное слово открыто полностью.",
        "apiError": "Игра остановилась из-за ошибки игрового цикла на сервере.",
        "validationError": "Ответ AI не прошел правила игры после повторных попыток.",
        "troubleshooting": (
            "Проверьте: нужные API-ключи заданы в терминале backend, uvicorn перезапущен, "
            "квота/баланс провайдера доступны, а подробности HTTP-ошибки видны в терминале backend. "
            "При HTTP 429 service-tier capacity подождите немного или переключите роль на другую доступную модель/провайдера."
        ),
        "validationTips": (
            "Обычно это значит, что модель повторила использованное слово, случайно выбрала скрытое "
            "секретное слово или дала слово не с текущим префиксом. Попробуйте еще раз или выберите модель сильнее."
        ),
        "invalidCustomSecret": "Пользовательское секретное слово должно быть одним допустимым словом для выбранного языка.",
        "usedWordsFinal": "Использованные слова:",
        "secretFinal": "Секретное слово:",
        "turnsFinal": "Попыток:",
        "winnerFinal": "Победитель:",
        "wordMasterGuessPrompt": "Ведущий, угадайте зашифрованное слово.",
        "wordMasterGuessPlaceholder": "Введите догадку...",
        "playerMovePrompt": "Игрок A, отправьте зашифрованную подсказку.",
        "playerMovePlaceholder": "Зашифрованная подсказка",
        "partnerGuessPrompt": "Игрок A, угадайте слово, которое зашифровал Игрок B.",
        "partnerGuessPlaceholder": "Введите слово, которое, по вашему мнению, зашифровал Игрок B...",
    },
}


def other_player(player: PlayerRole) -> PlayerRole:
    return "playerB" if player == "playerA" else "playerA"


def player_label(language: str, player: PlayerRole) -> str:
    return COPY[language][player]


def role_label(language: str, role: str) -> str:
    return COPY[language][role]


class GameManager:
    def __init__(self, providers: AgentProviderConfig, models: AgentModelConfig) -> None:
        self.providers = providers
        self.models = models
        self.provider_info = provider_info(providers, models)
        self._run_providers = providers
        self._run_models = models
        self._lock = asyncio.Lock()
        self._run_id = 0
        self._task: asyncio.Task | None = None
        self._pending_event: asyncio.Event | None = None
        self._pending_submission: MasterGuess | PlayerMove | PartnerGuess | None = None
        self._state = self._idle_state(
            language="en",
            player_a_personality="",
            player_b_personality="",
        )

    def get_provider_info(self) -> ProviderInfo:
        return self.provider_info

    def _resolve_run_configs(self, request: StartGameRequest) -> tuple[AgentProviderConfig, AgentModelConfig, ProviderInfo]:
        from .config import resolve_agent_configs

        providers, models = resolve_agent_configs(request.agentModelSelection, self.providers, self.models)
        return providers, models, provider_info(providers, models)

    async def get_state(self) -> GameState:
        async with self._lock:
            return self._client_state(self._state)

    async def start(self, request: StartGameRequest) -> GameState:
        await self._cancel_task()
        provided_secret = self._provided_secret_word(request)
        if request.humanRole == "wordMaster" and not provided_secret:
            raise ValueError("Secret word is required when playing as Word Master.")
        if request.humanRole == "playerA" and provided_secret:
            raise ValueError("Secret word cannot be provided when playing as Player A.")
        run_providers, run_models, run_provider_info = self._resolve_run_configs(request)
        async with self._lock:
            self._run_id += 1
            run_id = self._run_id
            self._run_providers = run_providers
            self._run_models = run_models
            self._state = self._idle_state(
                language=request.language,
                player_a_personality=request.playerAPersonality,
                player_b_personality=request.playerBPersonality,
                human_role=request.humanRole,
                provider_info=run_provider_info,
            )
            self._state.status = "running"
            if provided_secret:
                self._state.secretWord = provided_secret
                self._state.currentPrefix = first_letters(provided_secret, 1)
                self._state.revealedLength = 1
                self._state.maxTurns = compute_max_turns(provided_secret)
            state = self._client_state(self._state)
        write_event(
            "game_start",
            runId=run_id,
            request=request,
            state=state,
            providerInfo=self.provider_info,
            runProviderInfo=run_provider_info,
            humanRole=request.humanRole,
        )
        write_event("human_role_selected", runId=run_id, humanRole=request.humanRole)
        self._task = asyncio.create_task(self._run_loop(run_id))
        return state

    async def reset(self) -> GameState:
        await self._cancel_task()
        async with self._lock:
            previous = self._state
            self._run_id += 1
            self._state = self._idle_state(
                language=previous.language,
                player_a_personality=previous.playerAPersonality,
                player_b_personality=previous.playerBPersonality,
                human_role=previous.humanRole,
                provider_info=previous.providerInfo,
            )
            write_event(
                "game_reset",
                runId=self._run_id,
                previousState=previous,
                state=self._state,
            )
            return self._client_state(self._state)

    async def submit_user_input(self, request: UserInputRequest) -> GameState:
        event: asyncio.Event | None = None
        async with self._lock:
            if self._state.status != "running" or not self._state.pendingUserInput:
                raise ValueError("The game is not waiting for user input.")
            pending = self._state.pendingUserInput
            if request.kind != pending.kind:
                raise ValueError(f"The game is waiting for {pending.kind}, not {request.kind}.")

            try:
                submission = self._validate_user_input(self._state, request)
            except ValueError as error:
                write_event(
                    "human_input_validation_failure",
                    runId=self._run_id,
                    humanRole=self._state.humanRole,
                    pendingUserInput=pending,
                    request=request,
                    error=error,
                    state=self._state,
                )
                raise

            self._pending_submission = submission
            self._state.pendingUserInput = None
            event = self._pending_event
            write_event(
                "human_input_submitted",
                runId=self._run_id,
                humanRole=self._state.humanRole,
                inputKind=request.kind,
                submission=submission,
                state=self._state,
            )
            state = self._client_state(self._state)

        if event:
            event.set()
        return state

    async def _cancel_task(self) -> None:
        task = self._task
        self._task = None
        if self._pending_event:
            self._pending_event.set()
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._pending_event = None
        self._pending_submission = None

    def _idle_state(
        self,
        *,
        language: str,
        player_a_personality: str,
        player_b_personality: str,
        human_role: HumanRole = "none",
        provider_info: ProviderInfo | None = None,
    ) -> GameState:
        return GameState(
            language=language,
            humanRole=human_role,
            playerAPersonality=player_a_personality,
            playerBPersonality=player_b_personality,
            providerInfo=provider_info or self.provider_info,
        )

    def _client_state(self, state: GameState) -> GameState:
        visible_state = copy.deepcopy(state)
        if visible_state.humanRole == "playerA" and visible_state.status != "finished":
            secret = visible_state.secretWord
            secret_placeholder = "[secret]" if visible_state.language == "en" else "[секрет]"
            labels = COPY[visible_state.language]
            if secret:
                for message in visible_state.messages:
                    event_type = (message.metadata or {}).get("eventType")
                    if event_type == "secret-chosen":
                        message.text = labels["wordMasterChose"]
                    else:
                        message.text = message.text.replace(secret, secret_placeholder)
                    if message.metadata and message.metadata.get("word") == secret:
                        message.metadata = {**message.metadata}
                        message.metadata.pop("word", None)
            visible_state.secretWord = ""
        return visible_state

    def _provided_secret_word(self, request: StartGameRequest) -> str:
        raw_word = (request.secretWord or "").strip()
        if not raw_word:
            return ""
        word = normalize_word(raw_word, request.language)
        if not is_valid_word(word, request.language):
            raise ValueError(COPY[request.language]["invalidCustomSecret"])
        return word

    def _validate_user_input(self, state: GameState, request: UserInputRequest) -> MasterGuess | PlayerMove | PartnerGuess:
        if request.kind == "wordMasterGuess":
            ok, value, reason = validate_master_guess_output(
                {"guess": request.guess, "confidence": 1},
                language=state.language,
                secret_word=state.secretWord,
                current_prefix=state.currentPrefix,
                used_words=state.usedWords,
            )
        elif request.kind == "playerMove":
            ok, value, reason = validate_player_move_output(
                {"intendedWord": request.intendedWord, "clue": request.clue},
                language=state.language,
                current_prefix=state.currentPrefix,
                used_words=state.usedWords,
            )
        elif request.kind == "partnerGuess":
            ok, value, reason = validate_partner_guess_output(
                {"guess": request.guess},
                language=state.language,
                current_prefix=state.currentPrefix,
                used_words=state.usedWords,
            )
        else:
            raise ValueError(f"Unsupported user input kind: {request.kind}.")
        if not ok or value is None:
            raise ValueError(reason or "Submitted input does not satisfy the game rules.")
        return value

    async def _is_active(self, run_id: int) -> bool:
        async with self._lock:
            return self._run_id == run_id and self._state.status == "running"

    async def _mutate(self, run_id: int, callback) -> bool:
        async with self._lock:
            if self._run_id != run_id or self._state.status != "running":
                return False
            callback(self._state)
            write_event("game_state_mutation", runId=run_id, state=self._state)
            return True

    async def _append_message(
        self,
        run_id: int,
        role: str,
        text: str,
        metadata: dict | None = None,
    ) -> bool:
        def append(state: GameState) -> None:
            state.messages.append(
                GameMessage(
                    id=str(uuid.uuid4()),
                    role=role,
                    text=text,
                    timestamp=time.time() * 1000,
                    metadata=metadata,
                )
            )
            write_event(
                "game_message",
                runId=run_id,
                role=role,
                text=text,
                metadata=metadata,
                state=state,
            )

        return await self._mutate(run_id, append)

    async def _await_user_input(
        self,
        run_id: int,
        pending_input: PendingUserInput,
    ) -> MasterGuess | PlayerMove | PartnerGuess | None:
        event = asyncio.Event()
        async with self._lock:
            if self._run_id != run_id or self._state.status != "running":
                return None
            if self._state.pendingUserInput is not None:
                raise RuntimeError("A user input request is already pending.")
            self._pending_event = event
            self._pending_submission = None
            self._state.pendingUserInput = pending_input
            write_event(
                "pending_user_input_created",
                runId=run_id,
                humanRole=self._state.humanRole,
                pendingUserInput=pending_input,
                state=self._state,
            )

        await event.wait()

        async with self._lock:
            if self._run_id != run_id or self._state.status != "running":
                return None
            submission = self._pending_submission
            self._pending_submission = None
            self._pending_event = None
            write_event(
                "game_resumed_after_human_input",
                runId=run_id,
                humanRole=self._state.humanRole,
                inputKind=pending_input.kind,
                submission=submission,
                state=self._state,
            )
            return submission

    def _agent_history(self, state: GameState, *, include_secret: bool) -> list[str]:
        labels = COPY[state.language]
        secret_placeholder = "[secret]" if state.language == "en" else "[секрет]"
        history = []
        for index, message in enumerate(state.messages, start=1):
            text = message.text
            event_type = (message.metadata or {}).get("eventType")
            if not include_secret:
                if event_type == "secret-chosen":
                    text = labels["wordMasterChose"]
                elif state.secretWord:
                    text = text.replace(state.secretWord, secret_placeholder)
            history.append(f"{index}. {role_label(state.language, message.role)}: {text}")
        return history

    def _word_master_decoded_examples(self, state: GameState) -> list[dict[str, str]]:
        examples = []
        current_clue: dict[str, str] | None = None
        current_master_guess = ""
        for message in state.messages:
            event_type = (message.metadata or {}).get("eventType")
            if event_type == "clue" and message.role in ("playerA", "playerB"):
                current_clue = {
                    "actingPlayer": role_label(state.language, message.role),
                    "clue": message.text,
                }
                current_master_guess = ""
                continue
            if event_type == "master-guess":
                current_master_guess = str((message.metadata or {}).get("word") or "").strip()
                continue
            if event_type == "blocked" and current_clue and current_master_guess:
                examples.append(
                    {
                        **current_clue,
                        "decodedWord": current_master_guess,
                        "whyNegative": COPY[state.language]["wordMasterDecodedBlockedReason"],
                    }
                )
                current_clue = None
                current_master_guess = ""
        return examples

    def _add_used_words(self, state: GameState, words: list[str]) -> None:
        seen = {normalize_word(word, state.language) for word in state.usedWords}
        for word in words:
            if not is_valid_word(word, state.language):
                continue
            normalized = normalize_word(word, state.language)
            if normalized in seen:
                continue
            seen.add(normalized)
            state.usedWords.append(normalized)
            write_event("used_word_added", language=state.language, word=normalized, usedWords=state.usedWords)

    def _final_summary(self, state: GameState) -> str:
        labels = COPY[state.language]
        winner = labels["players"] if state.winner == "players" else labels["wordMaster"]
        return " ".join(
            [
                labels["gameOver"],
                f"{labels['winnerFinal']} {winner}.",
                f"{labels['secretFinal']} {state.secretWord}.",
                f"{labels['turnsFinal']} {state.turnNumber}/{state.maxTurns}.",
                f"{labels['usedWordsFinal']} {', '.join(state.usedWords) or '-'}",
            ]
        )

    async def _finish(
        self,
        run_id: int,
        *,
        winner: str,
        reason: str,
        text: str,
    ) -> None:
        async with self._lock:
            if self._run_id != run_id or self._state.status != "running":
                return
            self._add_used_words(self._state, [self._state.secretWord])
            self._state.status = "finished"
            self._state.winner = winner
            self._state.finishReason = reason
            final_text = f"{text} {self._final_summary(self._state)}"
            self._state.messages.append(
                GameMessage(
                    id=str(uuid.uuid4()),
                    role="system",
                    text=final_text,
                    timestamp=time.time() * 1000,
                    metadata={"eventType": "game-over"},
                )
            )
            write_event(
                "game_finished",
                runId=run_id,
                winner=winner,
                reason=reason,
                text=text,
                state=self._state,
            )

    async def _finish_error(self, run_id: int, error: Exception) -> None:
        async with self._lock:
            if self._run_id != run_id or self._state.status != "running":
                return
            labels = COPY[self._state.language]
            is_validation_error = isinstance(error, LLMValidationError)
            self._state.status = "finished"
            self._state.winner = "wordMaster"
            self._state.finishReason = "llmValidationError" if is_validation_error else "llmError"
            prefix = labels["validationError"] if is_validation_error else labels["apiError"]
            tips = labels["validationTips"] if is_validation_error else labels["troubleshooting"]
            self._state.messages.append(
                GameMessage(
                    id=str(uuid.uuid4()),
                    role="system",
                    text=f"{prefix} {error} {tips}",
                    timestamp=time.time() * 1000,
                    metadata={"eventType": "error"},
                )
            )
            write_event(
                "game_error_finished",
                runId=run_id,
                error=error,
                isValidationError=is_validation_error,
                state=self._state,
            )

    async def _snapshot(self) -> GameState:
        async with self._lock:
            return copy.deepcopy(self._state)

    async def _run_loop(self, run_id: int) -> None:
        write_event("game_loop_started", runId=run_id)
        try:
            await self._initialize_secret(run_id)

            while await self._is_active(run_id):
                state = await self._snapshot()
                labels = COPY[state.language]
                if state.turnNumber > state.maxTurns:
                    await self._finish(
                        run_id,
                        winner="wordMaster",
                        reason="maxTurns",
                        text=labels["maxTurns"],
                    )
                    return

                await self._play_turn(run_id)
        except asyncio.CancelledError:
            write_event("game_loop_cancelled", runId=run_id)
            raise
        except Exception as error:
            write_event("game_loop_exception", runId=run_id, error=error)
            await self._finish_error(run_id, error)

    async def _initialize_secret(self, run_id: int) -> None:
        state = await self._snapshot()
        if state.secretWord:
            secret_word = state.secretWord
            secret_result = {"word": secret_word, "source": "observer"}
            write_event(
                "secret_word_provided_by_observer",
                runId=run_id,
                language=state.language,
                secretWord=secret_word,
            )
        else:
            secret_result = await choose_secret_word(
                provider=self._run_providers.word_master_provider,
                models=self._run_models,
                language=state.language,
            )
            secret_word = normalize_word(secret_result["word"], state.language)
        current_prefix = first_letters(secret_word, 1)
        max_turns = compute_max_turns(secret_word)
        labels = COPY[state.language]
        write_event(
            "secret_word_chosen",
            runId=run_id,
            language=state.language,
            rawResult=secret_result,
            secretWord=secret_word,
            prefix=current_prefix,
            maxTurns=max_turns,
        )

        def initialize(next_state: GameState) -> None:
            next_state.secretWord = secret_word
            next_state.currentPrefix = current_prefix
            next_state.revealedLength = 1
            next_state.maxTurns = max_turns

        if not await self._mutate(run_id, initialize):
            return
        await self._append_message(
            run_id,
            "system",
            f"{labels['wordMasterChose']} {secret_word}",
            {"eventType": "secret-chosen", "word": secret_word},
        )
        await self._append_message(
            run_id,
            "system",
            f"{labels['prefix']} {current_prefix}",
            {"eventType": "prefix", "prefix": current_prefix},
        )

        if len(secret_word) <= 1:
            # A one-letter secret word is already fully revealed by the
            # initial prefix — there are no remaining letters to establish
            # contact over, so the game ends immediately as a players' win
            # rather than running a zero-attempt game.
            await self._finish(
                run_id,
                winner="players",
                reason="fullPrefix",
                text=labels["fullPrefix"],
            )

    async def _play_turn(self, run_id: int) -> None:
        state = await self._snapshot()
        labels = COPY[state.language]
        actor = state.currentTurn
        partner = other_player(actor)
        actor_name = player_label(state.language, actor)
        partner_name = player_label(state.language, partner)
        actor_personality = state.playerAPersonality if actor == "playerA" else state.playerBPersonality
        partner_personality = state.playerAPersonality if partner == "playerA" else state.playerBPersonality
        actor_provider = self._run_providers.player_a_provider if actor == "playerA" else self._run_providers.player_b_provider
        partner_provider = self._run_providers.player_a_provider if partner == "playerA" else self._run_providers.player_b_provider
        write_event(
            "turn_started",
            runId=run_id,
            turnNumber=state.turnNumber,
            actor=actor,
            partner=partner,
            prefix=state.currentPrefix,
            usedWords=state.usedWords,
            state=state,
        )

        if state.humanRole == "playerA" and actor == "playerA":
            move_result = await self._await_user_input(
                run_id,
                PendingUserInput(
                    kind="playerMove",
                    role="playerA",
                    promptText=labels["playerMovePrompt"],
                    placeholderText=labels["playerMovePlaceholder"],
                    currentPrefix=state.currentPrefix,
                    actingPlayer=actor,
                    partner=partner,
                ),
            )
            if move_result is None:
                return
            if not isinstance(move_result, PlayerMove):
                raise RuntimeError("Expected a PlayerMove submission.")
            move = move_result
        else:
            move = await generate_player_move(
                provider=actor_provider,
                models=self._run_models,
                player_name=actor_name,
                player_role=actor,
                language=state.language,
                current_prefix=state.currentPrefix,
                public_history=self._agent_history(state, include_secret=False),
                used_words=state.usedWords,
                personality=actor_personality,
                word_master_decoded_examples=self._word_master_decoded_examples(state),
            )
        intended_word = normalize_word(move.intendedWord, state.language)
        clue = move.clue.strip()
        write_event(
            "player_move_generated",
            runId=run_id,
            actor=actor,
            intendedWord=intended_word,
            clue=clue,
            rawMove=move,
        )
        if not await self._append_message(run_id, actor, clue, {"eventType": "clue"}):
            return

        state = await self._snapshot()
        if state.humanRole == "wordMaster":
            master_guess_result = await self._await_user_input(
                run_id,
                PendingUserInput(
                    kind="wordMasterGuess",
                    role="wordMaster",
                    promptText=labels["wordMasterGuessPrompt"],
                    placeholderText=labels["wordMasterGuessPlaceholder"],
                    currentPrefix=state.currentPrefix,
                    clue=clue,
                    actingPlayer=actor,
                    partner=partner,
                ),
            )
            if master_guess_result is None:
                return
            if not isinstance(master_guess_result, MasterGuess):
                raise RuntimeError("Expected a Word Master guess submission.")
            master_guess = master_guess_result
        else:
            try:
                master_guess = await word_master_guess(
                    provider=self._run_providers.word_master_provider,
                    models=self._run_models,
                    language=state.language,
                    secret_word=state.secretWord,
                    current_prefix=state.currentPrefix,
                    clue=clue,
                    public_history=self._agent_history(state, include_secret=True),
                    used_words=state.usedWords,
                )
            except LLMGameError as error:
                master_guess = None
                write_event(
                    "word_master_guess_unavailable",
                    runId=run_id,
                    error=error,
                    clue=clue,
                    prefix=state.currentPrefix,
                    state=state,
                )

        if master_guess is None:
            if not await self._append_message(
                run_id,
                "wordMaster",
                labels["wordMasterNoGuess"],
                {"eventType": "master-no-guess"},
            ):
                return
        else:
            master_guess_word = normalize_word(master_guess.guess, state.language)
            write_event(
                "word_master_guess_generated",
                runId=run_id,
                guess=master_guess_word,
                rawGuess=master_guess,
            )
            block_text = (
                f"Это не {master_guess_word}!"
                if state.language == "ru"
                else f"This is not {master_guess_word}!"
            )
            if not await self._append_message(
                run_id,
                "wordMaster",
                block_text,
                {"eventType": "master-guess", "word": master_guess_word},
            ):
                return

            def add_master_guess(next_state: GameState) -> None:
                self._add_used_words(next_state, [master_guess_word])

            if not await self._mutate(run_id, add_master_guess):
                return

            if same_word(master_guess_word, intended_word, state.language):
                def block_contact(next_state: GameState) -> None:
                    self._add_used_words(next_state, [intended_word])
                    next_state.currentTurn = partner
                    next_state.turnNumber += 1

                if not await self._append_message(run_id, "system", labels["blocked"], {"eventType": "blocked"}):
                    return
                await self._mutate(run_id, block_contact)
                return

        if not await self._append_message(
            run_id,
            "system",
            labels["failedIntercept"],
            {"eventType": "failed-intercept"},
        ):
            return

        state = await self._snapshot()
        if state.humanRole == "playerA" and partner == "playerA":
            partner_guess_result = await self._await_user_input(
                run_id,
                PendingUserInput(
                    kind="partnerGuess",
                    role="playerA",
                    promptText=labels["partnerGuessPrompt"],
                    placeholderText=labels["partnerGuessPlaceholder"],
                    currentPrefix=state.currentPrefix,
                    clue=clue,
                    actingPlayer=actor,
                    partner=partner,
                ),
            )
            if partner_guess_result is None:
                return
            if not isinstance(partner_guess_result, PartnerGuess):
                raise RuntimeError("Expected a Player A partner guess submission.")
            partner_answer = partner_guess_result
        else:
            partner_answer = await guess_partner_word(
                provider=partner_provider,
                models=self._run_models,
                player_name=partner_name,
                player_role=partner,
                language=state.language,
                current_prefix=state.currentPrefix,
                clue=clue,
                public_history=self._agent_history(state, include_secret=False),
                used_words=state.usedWords,
                personality=partner_personality,
                word_master_decoded_examples=self._word_master_decoded_examples(state),
            )
        guessed_word = normalize_word(partner_answer.guess, state.language)
        write_event(
            "partner_guess_generated",
            runId=run_id,
            partner=partner,
            guess=guessed_word,
            rawGuess=partner_answer,
        )
        if not await self._append_message(
            run_id,
            actor,
            intended_word,
            {"eventType": "intended-word", "word": intended_word},
        ):
            return
        if not await self._append_message(
            run_id,
            partner,
            guessed_word,
            {"eventType": "partner-guess", "word": guessed_word},
        ):
            return

        def add_revealed_words(next_state: GameState) -> None:
            self._add_used_words(next_state, [intended_word, guessed_word])

        if not await self._mutate(run_id, add_revealed_words):
            return

        state = await self._snapshot()
        if same_word(intended_word, state.secretWord, state.language) or same_word(guessed_word, state.secretWord, state.language):
            await self._finish(
                run_id,
                winner="players",
                reason="secretFound",
                text=labels["playersFound"],
            )
            return

        if same_word(intended_word, guessed_word, state.language):
            if not await self._append_message(
                run_id,
                "system",
                labels["contactSucceeded"],
                {"eventType": "contact-succeeded"},
            ):
                return
            state = await self._snapshot()
            next_reveal_length = state.revealedLength + 1
            if next_reveal_length >= len(state.secretWord):
                def reveal_all(next_state: GameState) -> None:
                    next_state.revealedLength = len(next_state.secretWord)
                    next_state.currentPrefix = next_state.secretWord

                await self._mutate(run_id, reveal_all)
                state = await self._snapshot()
                await self._finish(
                    run_id,
                    winner="players",
                    reason="fullPrefix",
                    text=labels["fullPrefix"],
                )
                return

            next_prefix = first_letters(state.secretWord, next_reveal_length)

            def reveal_next(next_state: GameState) -> None:
                next_state.revealedLength = next_reveal_length
                next_state.currentPrefix = next_prefix
                next_state.currentTurn = partner
                next_state.turnNumber += 1

            if not await self._mutate(run_id, reveal_next):
                return
            await self._append_message(
                run_id,
                "system",
                f"{labels['prefix']} {next_prefix}",
                {"eventType": "prefix", "prefix": next_prefix},
            )
            return

        def fail_contact(next_state: GameState) -> None:
            next_state.currentTurn = partner
            next_state.turnNumber += 1

        if not await self._append_message(run_id, "system", labels["contactFailed"], {"eventType": "contact-failed"}):
            return
        await self._mutate(run_id, fail_contact)
