from __future__ import annotations

import asyncio
import copy
import time
import uuid

from .agents import LLMValidationError, choose_secret_word, generate_player_move, guess_partner_word, word_master_guess
from .config import AgentProviderConfig, provider_info
from .event_log import write_event
from .schemas import AgentModelConfig, GameMessage, GameState, PlayerRole, ProviderInfo, StartGameRequest
from .word_utils import first_letters, is_valid_word, normalize_word, same_word

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
        "gameOver": "Game over.",
        "maxTurns": "Max turns reached.",
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
        "turnsFinal": "Turns:",
        "winnerFinal": "Winner:",
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
        "gameOver": "Игра окончена.",
        "maxTurns": "Достигнут лимит ходов.",
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
        "turnsFinal": "Ходов:",
        "winnerFinal": "Победитель:",
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
        self._lock = asyncio.Lock()
        self._run_id = 0
        self._task: asyncio.Task | None = None
        self._state = self._idle_state(
            language="en",
            player_a_personality="Playful, metaphor-loving, a little theatrical, but concise.",
            player_b_personality="Sharp, practical, and good at noticing everyday associations.",
        )

    def get_provider_info(self) -> ProviderInfo:
        return self.provider_info

    async def get_state(self) -> GameState:
        async with self._lock:
            return copy.deepcopy(self._state)

    async def start(self, request: StartGameRequest) -> GameState:
        await self._cancel_task()
        provided_secret = self._provided_secret_word(request)
        async with self._lock:
            self._run_id += 1
            run_id = self._run_id
            self._state = self._idle_state(
                language=request.language,
                player_a_personality=request.playerAPersonality,
                player_b_personality=request.playerBPersonality,
                max_turns=request.maxTurns,
            )
            self._state.status = "running"
            if provided_secret:
                self._state.secretWord = provided_secret
                self._state.currentPrefix = first_letters(provided_secret, 1)
                self._state.revealedLength = 1
            state = copy.deepcopy(self._state)
        write_event(
            "game_start",
            runId=run_id,
            request=request,
            state=state,
            providerInfo=self.provider_info,
        )
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
                max_turns=previous.maxTurns,
            )
            write_event(
                "game_reset",
                runId=self._run_id,
                previousState=previous,
                state=self._state,
            )
            return copy.deepcopy(self._state)

    async def _cancel_task(self) -> None:
        task = self._task
        self._task = None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def _idle_state(
        self,
        *,
        language: str,
        player_a_personality: str,
        player_b_personality: str,
        max_turns: int = 50,
    ) -> GameState:
        return GameState(
            language=language,
            maxTurns=max_turns,
            playerAPersonality=player_a_personality,
            playerBPersonality=player_b_personality,
            providerInfo=self.provider_info,
        )

    def _provided_secret_word(self, request: StartGameRequest) -> str:
        raw_word = (request.secretWord or "").strip()
        if not raw_word:
            return ""
        word = normalize_word(raw_word, request.language)
        if not is_valid_word(word, request.language):
            raise ValueError(COPY[request.language]["invalidCustomSecret"])
        return word

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
                f"{labels['secretFinal']} {state.secretWord}",
                f"{labels['turnsFinal']} {state.turnNumber}",
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
                provider=self.providers.word_master_provider,
                models=self.models,
                language=state.language,
            )
            secret_word = normalize_word(secret_result["word"], state.language)
        current_prefix = first_letters(secret_word, 1)
        labels = COPY[state.language]
        write_event(
            "secret_word_chosen",
            runId=run_id,
            language=state.language,
            rawResult=secret_result,
            secretWord=secret_word,
            prefix=current_prefix,
        )

        def initialize(next_state: GameState) -> None:
            next_state.secretWord = secret_word
            next_state.currentPrefix = current_prefix
            next_state.revealedLength = 1

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

    async def _play_turn(self, run_id: int) -> None:
        state = await self._snapshot()
        labels = COPY[state.language]
        actor = state.currentTurn
        partner = other_player(actor)
        actor_name = player_label(state.language, actor)
        partner_name = player_label(state.language, partner)
        actor_personality = state.playerAPersonality if actor == "playerA" else state.playerBPersonality
        partner_personality = state.playerAPersonality if partner == "playerA" else state.playerBPersonality
        actor_provider = self.providers.player_a_provider if actor == "playerA" else self.providers.player_b_provider
        partner_provider = self.providers.player_a_provider if partner == "playerA" else self.providers.player_b_provider
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

        move = await generate_player_move(
            provider=actor_provider,
            models=self.models,
            player_name=actor_name,
            player_role=actor,
            language=state.language,
            current_prefix=state.currentPrefix,
            public_history=self._agent_history(state, include_secret=False),
            used_words=state.usedWords,
            personality=actor_personality,
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
        master_guess = await word_master_guess(
            provider=self.providers.word_master_provider,
            models=self.models,
            language=state.language,
            secret_word=state.secretWord,
            current_prefix=state.currentPrefix,
            clue=clue,
            public_history=self._agent_history(state, include_secret=True),
            used_words=state.usedWords,
        )
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
        partner_answer = await guess_partner_word(
            provider=partner_provider,
            models=self.models,
            player_name=partner_name,
            player_role=partner,
            language=state.language,
            current_prefix=state.currentPrefix,
            clue=clue,
            public_history=self._agent_history(state, include_secret=False),
            used_words=state.usedWords,
            personality=partner_personality,
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
