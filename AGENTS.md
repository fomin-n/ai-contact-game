# AGENTS.md

This file is the agent-facing operating guide for `ai-contact-game`. Keep `README.md` concise for humans; put detailed implementation context here.

## Project Overview

`ai-contact-game` is a small full-stack LLM-agent game inspired by the Russian word game "Есть контакт" / "Contact".

The web UI supports three modes:

- `none`: observer watches AI vs AI. This is the default and must remain backward-compatible.
- `wordMaster`: the human provides the secret word and submits Word Master guesses through pending backend input.
- `playerA`: the human replaces Player A, submits Player A clues, and later guesses Player B clues after failed interceptions.

In automatic mode, three AI roles play:

- `Word Master`: chooses and knows the secret word, reveals prefixes, and tries to intercept player clues.
- `Player A` and `Player B`: do not know the secret word. They only know the current prefix, redacted full public session history, used words, language, and their own personality text.
- The observer may provide `secretWord` in `StartGameRequest`; when present, backend validation normalizes it and Word Master skips the LLM secret-word selection step.
- `humanRole="wordMaster"` requires `secretWord`.
- `humanRole="playerA"` must not receive the secret word in the UI before the game is finished.

The frontend is observer-only. All game rules, prompts, LLM calls, state transitions, validation, and deterministic word comparison belong on the Python backend.

## Repository Structure

- `backend/app/main.py`: FastAPI app and REST routes.
- `backend/app/game.py`: backend-owned game state, loop, turn transitions, visible message timing, finish/error handling.
- `backend/app/agents.py`: LLM task helpers, validation, retry/repair behavior.
- `backend/app/word_utils.py`: deterministic normalization and word comparison.
- `backend/app/config.py`: provider/model configuration from environment variables.
- `backend/app/model_catalog.py`: static backend-owned provider/model catalog returned by `/api/config`.
- `backend/app/event_log.py`: JSONL event logging with secret redaction.
- `backend/app/prompt_loader.py`: YAML prompt loading/rendering.
- `backend/app/providers/`: provider interface and implementations.
- `backend/app/schemas.py`: Pydantic API and game data models.
- `backend/tests/`: standard-library unit tests for backend retry/validation behavior.
- `prompts/`: task prompt YAML files and shared common prompt blocks.
- `scripts/dev.sh`: one-command local installer/runner for backend and frontend.
- `frontend/`: React/TypeScript/Vite frontend package.
- `frontend/src/App.tsx`: frontend root composition component.
- `frontend/src/hooks/useGameController.ts`: React Query-backed UI orchestration for config, game state polling, and start/reset mutations. Keep this hook UI-only.
- `frontend/src/components/`: component folders with colocated `.tsx`, `.css`, and `index.ts` files.
- `frontend/src/api/gameApi.ts`: thin typed REST client for backend endpoints. It should not contain React logic.
- `frontend/src/types/game.ts`: frontend API/game state TypeScript types that mirror backend response shapes.
- `frontend/src/i18n/copy.ts`: UI copy and rules-dialog text.
- `frontend/src/constants/gameConstants.ts`: UI constants such as max turns and polling interval.
- `frontend/src/config/defaults.ts`: frontend-only defaults for initial empty state, default personalities, and initial provider display.
- `frontend/src/utils/gameUi.tsx`: frontend-only role labels and message rendering helpers.
- `frontend/src/styles/global.css`: global/base CSS only.
- `frontend/vite.config.ts`: Vite dev server and `/api` backend proxy.
- `.env.example`: local environment template; copy to `.env` and fill credentials.
- `logs/.gitkeep`: keeps the runtime log directory in Git.

## Setup Commands

Preferred local setup:

```bash
cp .env.example .env
# Fill at least one provider key in .env.
./scripts/dev.sh
```

`scripts/dev.sh` does all of the following:

- loads `.env` if present
- creates `.venv` if missing
- installs `requirements.txt`
- runs `npm install` in `frontend/`
- starts FastAPI on `127.0.0.1:${BACKEND_PORT:-8000}`
- starts Vite on `0.0.0.0:${FRONTEND_PORT:-5173}`
- stops both servers on Ctrl+C

Use install-only mode when an agent needs to validate dependencies without leaving servers running:

```bash
./scripts/dev.sh --install-only
```

Manual backend setup remains useful for debugging:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

If the backend is not on port `8000`, set `BACKEND_PORT`:

```bash
cd frontend
BACKEND_PORT=9000 npm run dev
```

For a single combined-script run with custom ports:

```bash
BACKEND_PORT=9000 FRONTEND_PORT=5174 ./scripts/dev.sh
```

For LAN access during development, Vite listens on `0.0.0.0`; use the printed network URL. The backend can remain local because Vite proxies `/api/*`.

## Validation Commands

Use relevant checks before committing:

```bash
cd frontend
npm run typecheck
npm run build
cd ..
.venv/bin/python -m compileall backend
.venv/bin/python -m unittest discover backend/tests
```

The backend unit tests currently cover LLM retry-feedback behavior and provider/model selection resolution.

## Environment Variables

Default Mistral setup:

```bash
AI_PROVIDER=mistral
MISTRAL_API_KEY=...
MISTRAL_MODEL=mistral-small-latest
```

Mixed setup often used during development:

```bash
WORD_MASTER_PROVIDER=mistral
PLAYER_A_PROVIDER=openai
PLAYER_B_PROVIDER=openai
MISTRAL_API_KEY=...
OPENAI_API_KEY=...
WORD_MASTER_MODEL=mistral-medium-latest
PLAYER_A_MODEL=gpt-4.1-mini
PLAYER_B_MODEL=gpt-4.1-mini
```

OpenAI-compatible setup:

```bash
AI_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
```

Do not hardcode API keys. Do not commit `.env*` files.

`.env` is loaded by `scripts/dev.sh` as a shell-compatible file. Keep it to simple `KEY=value` lines. `.env.example` is intentionally safe to commit and should not contain real credentials.

The web UI can choose among configured providers/models per game run. Environment variables still define startup defaults and credentials. The frontend receives only provider/model ids, display names, and `hasApiKey` booleans; it must never receive API key values.

## Provider Architecture

Game logic depends on `LLMProvider`, not on concrete providers.

Current provider files:

- `backend/app/providers/base.py`: generic provider interface.
- `backend/app/providers/mistral.py`: Mistral provider.
- `backend/app/providers/openai_compatible.py`: OpenAI-compatible provider.
- `backend/app/providers/http_json.py`: shared Chat Completions HTTP/JSON handling, response parsing, capacity errors.
- `backend/app/providers/factory.py`: provider selection.
- `backend/app/model_catalog.py`: curated static provider/model options exposed to the UI.

To add a provider:

1. Implement `LLMProvider.chat_json(...)`.
2. Register the provider in `factory.py`.
3. Add provider/model options in `model_catalog.py`.
4. Read API keys/models from environment variables in the provider class.
5. Keep game logic provider-agnostic.

Providers should pass JSON Schema response formats when a schema is provided and fall back to JSON object response formats otherwise. Python validators remain the final source of truth for game rules and structured output correctness.

## Model Selection Flow

The backend owns provider/model selection. The frontend only displays choices and sends the selected ids.

- `/api/config` returns `providerInfo`, `modelCatalog`, and `defaultAgentModelSelection`.
- `modelCatalog` is static and curated in `backend/app/model_catalog.py`; do not dynamically fetch provider model lists for this small app.
- `modelCatalog[*].hasApiKey` is a boolean derived from environment variables. Never expose key values.
- The frontend stores the last selected model UI state in `localStorage` and sends `StartGameRequest.agentModelSelection` when starting a game.
- `backend/app/config.py::resolve_agent_configs(...)` validates provider ids, non-empty model ids, and API key presence.
- Unknown providers fail with HTTP 400.
- Unknown model ids are accepted for known providers if non-empty, so newly released or custom OpenAI-compatible models can be used without code changes.
- `GameManager.start(...)` resolves per-run `AgentProviderConfig` and `AgentModelConfig`, stores them as the current run config, and `GameState.providerInfo` reflects the active run.
- `_initialize_secret`, `_play_turn`, `choose_secret_word`, `generate_player_move`, `word_master_guess`, and `guess_partner_word` must use the current run config, not only startup defaults.
- Reset may preserve the latest visible provider info; do not add server-side user persistence.

## Prompt Management

Prompt templates live in `prompts/`:

- `_common.v1.yaml`
- `choose_secret_word.v1.yaml`
- `generate_player_move.v1.yaml`
- `word_master_guess.v1.yaml`
- `guess_partner_word.v1.yaml`

Each task prompt contains `id`, `version`, `temperature`, `model_role`, `schema`, `system`, and `user`.

Dynamic game state should be passed as JSON in the user message. Do not put user-controlled player personality text directly into system prompts. Personality is style guidance only and must not override game rules, schemas, or validation constraints.

Common constraints are injected from `_common.v1.yaml` by `backend/app/prompt_loader.py`. Python validation remains the source of truth.

To add a prompt version:

1. Copy an existing task YAML file, for example `generate_player_move.v1.yaml` to `generate_player_move.v2.yaml`.
2. Set `version: v2`.
3. Update the relevant `render_prompt(..., version="v2")` call.
4. Keep validation unchanged unless the actual game rules changed.

## Core Game Rules

- Secret word is visible only to the observer UI and Word Master.
- In human Player A mode, client-facing game state redacts `secretWord` until the game finishes.
- Observer-provided `secretWord` is optional. If provided, it must pass the same single-word letter validation for the selected language, then the game proceeds as if Word Master chose it.
- Players never receive the secret word in prompts.
- Players know current prefix, redacted full public session history, used words, language, and their own personality.
- Word Master receives full session history, including the secret word context.
- Prompt payloads include `allPreviousStepsInCurrentSession` as the explicit chronological context field for Player A, Player B, and Word Master.
- Do not truncate prompt session history unless a future context-size change explicitly requires it.
- Player intended words and guesses must be normal single words.
- Prompt rules require every secret word, intended word, and guess to be an existing common singular noun in normal dictionary form: singular, nominative case, and the most standard/basic noun form.
- Prompt rules forbid adjectives, verbs, proper nouns, plural forms, phrases, abbreviations, and inflected case forms as game words.
- Words must start with the current prefix.
- Used words are forbidden for the rest of the session.
- Word Master must make a concrete guess every turn.
- Word Master may not guess the secret word or an already used word.
- If any player explicitly calls the secret word, the game ends with players winning.
- There are no fallback dictionaries or hardcoded candidate words in the repository.
- If the LLM/provider fails, show an error instead of silently substituting words.
- `maxTurns` is computed, not configurable: `(len(secretWord) - 1) * 3` — three contact attempts per letter after the first, already-revealed one. It is `0` until the secret word is known (computed in `GameManager._initialize_secret`, or eagerly in `start()` when the secret is provided up front), and reaching it ends the game with Word Master winning (`finishReason="maxTurns"`). A one-letter secret word has zero remaining letters to guess, so it is special-cased: the game ends immediately as a players' win (`finishReason="fullPrefix"`) rather than running a zero-attempt game. `backend/app/word_utils.py::compute_max_turns` is the single source of truth for the formula.

## Human Input Flow

- `StartGameRequest.humanRole` is `"none"`, `"wordMaster"`, or `"playerA"`.
- `GameState.pendingUserInput` is the single backend-owned pause marker for human moves.
- Submit human input through `POST /api/game/user-input`.
- Valid pending input kinds are `wordMasterGuess`, `playerMove`, and `partnerGuess`.
- The frontend renders pending input inline in the timeline, but backend validation and turn transitions remain authoritative.
- Invalid human input returns HTTP 400, leaves `pendingUserInput` in place, and does not advance the game.

## Deterministic Word Comparison

Never use an LLM judge for equality.

`backend/app/word_utils.py` owns normalization and comparison:

- trim whitespace
- lowercase
- remove surrounding quotes
- for Russian, normalize `ё` to `е`
- reject spaces, hyphens, punctuation, digits, and symbols
- English words: `a-z`
- Russian words: `а-яё`
- compare normalized strings exactly

No fuzzy matching, semantic matching, embeddings, or LLM equality checks.

## Used Words

Add explicit candidate/guess words to `usedWords`:

- player hidden intended word
- Word Master guess
- partner guess
- secret word when the game ends

Do not add ordinary clue text words automatically.

## UI Responsibilities

Frontend owns rendering only:

- language selector
- personality textareas
- AI model/provider selection controls
- start/reset buttons
- game state display
- chat-style timeline
- used word chips
- compact model display
- React Query config/game-state queries and start/reset mutations

Do not move game rules, validation, prompt logic, provider logic, or turn logic into the frontend. The frontend must not expose or request API keys.

## Runtime Logs

Runtime logs are JSON Lines:

```text
logs/ai-contact-game.jsonl
```

This file is gitignored. `logs/.gitkeep` is tracked.

Logs include game state, prompts, provider request/response metadata, parsed LLM responses, validation failures, and game-loop exceptions. They may include game data such as secret words and player personality text. Review logs before sharing them publicly.

`backend/app/event_log.py` redacts known API-key fields, bearer tokens, common key formats, and current provider key environment values before writing logs.

The log file rotates via stdlib `logging.handlers.RotatingFileHandler` (no unbounded growth). Configurable via env vars, all optional with generous defaults:
- `AI_CONTACT_LOG_MAX_BYTES` (default `20971520`, 20 MiB) — size threshold per file before rotating.
- `AI_CONTACT_LOG_BACKUP_COUNT` (default `5`) — number of rotated backups kept (`ai-contact-game.jsonl.1` … `.5`), so ~120 MiB max retained.
- `AI_CONTACT_LOG_MAX_STRING_LENGTH` (default `20000`) — per-string truncation length within a single log record (unrelated to file rotation).

## Security Notes

- Never commit `.env*`, `.envrc`, runtime logs, `.venv`, `node_modules`, `dist`, private keys, or certificate/key files.
- `.gitignore` is configured for those files.
- Do not print raw API keys in terminal output or user-facing messages.
- Do not add hardcoded candidate-word dictionaries. The product requirement is that words come from the AI provider or fail visibly.

## Known Operational Notes

- Mistral may return HTTP 429 `service_tier_capacity_exceeded` for some models. The backend retries capacity errors with a delay, then fails visibly if the provider remains unavailable.
- `mistral-medium-latest` has been used successfully for Word Master when `mistral-small-latest` capacity was limited.
- `gpt-4.1-mini` has been used successfully for Player A and Player B through the OpenAI-compatible provider.
- There is no artificial delay before visible game-chat messages. Provider latency is the only expected delay.
- A per-provider circuit breaker (`backend/app/providers/http_json.py::_BREAKER`) trips after a burst of HTTP 429s and short-circuits further calls to that provider for a cooldown window — a generous, hobby-scale safeguard against hammering an already-throttling provider, not a billing control. Configurable, all optional:
  - `AI_CONTACT_CIRCUIT_BREAKER_FAILURE_THRESHOLD` (default `8`) — 429s within the window before tripping.
  - `AI_CONTACT_CIRCUIT_BREAKER_WINDOW_SECONDS` (default `90`) — sliding window for counting failures.
  - `AI_CONTACT_CIRCUIT_BREAKER_COOLDOWN_SECONDS` (default `90`) — how long the breaker stays open once tripped.
  - When open, calls fail fast with `ProviderCircuitOpenError`, which `agents.py::_with_repair` raises immediately as `LLMGameError` on the first attempt (no wasted retries). This degrades exactly like any other `LLMGameError`: gracefully for the Word-Master-guess step (`master-no-guess`, game continues), fatally everywhere else (visible game-stopped error) — unchanged from existing behavior.

## Telegram Bot

### Package structure

```
backend/telegram/
  bot.py              # Entry point: python -m backend.telegram.bot
  config.py           # TelegramBotSettings (reads AI_CONTACT_TELEGRAM_* env vars)
  safety.py           # Unicode sanitization, length limits, word/clue validation
  observability.py    # Phoenix/OpenTelemetry setup; _safe_metadata for trace export
  i18n/copy.py        # All user-facing strings: en + ru. get(key, lang, **fmt) helper.
  session/
    bot_state.py      # BotState enum
    game_session.py   # GameSession: owns GameManager + polling monitor task
    registry.py       # SessionRegistry: user_id → GameSession; TTL cleanup
  handlers/
    _helpers.py       # get_registry, get_settings, is_allowed_chat, get_lang
    commands.py       # /start /newgame /rules /status /cancel
    callbacks.py      # Inline keyboard callbacks (lang:, role:, newgame)
    messages.py       # Incoming text dispatch and per-state handlers
```

Tests in `backend/tests/tgbot/` (not `telegram/` to avoid shadowing the library package).

### Session lifecycle

Each Telegram `user_id` gets an independent `GameSession` in `SessionRegistry`. Each session owns a fresh `GameManager` instance. Sessions are keyed by `user_id` only (private chats). The `SessionRegistry` runs a background cleanup task every 5 minutes, removing sessions idle beyond `AI_CONTACT_TELEGRAM_SESSION_TTL_SECONDS`.

`GameSession` state machine transitions:
- `IDLE` → `/start` → `SELECTING_LANGUAGE` → lang callback → `SELECTING_ROLE`
- `SELECTING_ROLE` → wordMaster → `ENTERING_SECRET` → valid word → `GAME_RUNNING`
- `SELECTING_ROLE` → playerA → `GAME_RUNNING` (game starts immediately)
- `SELECTING_ROLE` → none ("Let LLMs play" / spectator) → `GAME_RUNNING` (game starts immediately, no pendingUserInput ever)
- `GAME_RUNNING` → monitor detects pending → `WAITING_WM_GUESS` / `WAITING_INTENDED_WORD` / `WAITING_PARTNER_GUESS`
- `WAITING_INTENDED_WORD` → valid word → `WAITING_CLUE` → valid clue → `GAME_RUNNING`
- `WAITING_*` → valid input → submit → `GAME_RUNNING` → monitor resumes
- Any state → `/cancel` → `IDLE`
- Any state → `/newgame` → `SELECTING_LANGUAGE`

### Spectator mode ("Let LLMs play" / "Пусть LLM играют сами")

The third role-selection button starts a game with `humanRole="none"` — the same
mode the web app calls "AI vs AI" (see `## Human Modes` above). No backend
changes were needed: the engine never sets `pendingUserInput` for `"none"`,
never redacts `secretWord`, and the Word-Master-guess-failure path
(`master-no-guess` → falls through to `failed-intercept`, game continues) was
already in place. The bot's `render.is_human_origin()` already returns `False`
for `human_role="none"`, so every message (clue, guess, prefix reveal, secret
word reveal) is dispatched — nothing extra to suppress or reformat.

The only bot-side addition is delivery pacing: `GameSession._monitor_loop`
sleeps `settings.ai_spectator_message_delay_seconds` between dispatching each
new message when `human_role == "none"`, so a turn's burst of messages (clue,
guess, contact result, prefix update) trickles in readably instead of landing
in one burst per 150ms poll tick. This does not change the engine's LLM call
cadence — that remains provider-latency-paced only, consistent with the "no
artificial delay before visible game-chat messages" rule above, which still
holds for the *engine*; the delay is purely a Telegram message-delivery
courtesy for spectators.

### Per-user daily game limit

`backend/telegram/usage_store.py::UsageStore` persists a per-user, per-UTC-day
game-start counter to `AI_CONTACT_TELEGRAM_USAGE_DATA_PATH` (default
`data/usage.json`), mirroring `auth/store.py`'s atomic-write pattern. This is a
generous abuse guard, not a billing system — the default limit is
`AI_CONTACT_TELEGRAM_MAX_GAMES_PER_DAY_PER_USER=50`. Enforced at the only two
places `session.start_game(...)` is actually called:
`callbacks.py::_handle_role` (playerA/none) and
`messages.py::_handle_entering_secret` (wordMaster). On limit hit, the user
gets a localized message and the session resets to `IDLE`.

### Concurrency model

Each `GameSession` has an `asyncio.Lock` that protects state machine transitions. The monitor task runs independently and acquires the lock only when changing `self.state`. Handler functions acquire the lock briefly for state read/write, then release it before doing I/O (Telegram API calls, `gm.submit_user_input`). The deduplication guard (`_last_processed_update_id`) prevents double-processing.

Monitor loop: polls `gm.get_state()` every 150ms. Sends new messages to Telegram, sends a typing action every 4s. Stops when `pendingUserInput` is detected (transitions session state, sends prompt) or when game finishes (sends game-over message with New Game button).

After the user submits input: handler calls `gm.submit_user_input(...)` (resumes the game loop), then calls `session.start_monitor()` which restarts the monitor from `_last_sent_msg_idx`.

### Mapping Telegram steps to pendingUserInput kinds

| pendingUserInput.kind | Bot state when waiting | User action | Submitted as |
|---|---|---|---|
| `wordMasterGuess` | `WAITING_WM_GUESS` | Send one word | `guess` field |
| `playerMove` | `WAITING_INTENDED_WORD` then `WAITING_CLUE` | Two messages: word then clue | `intendedWord` + `clue` |
| `partnerGuess` | `WAITING_PARTNER_GUESS` | Send one word | `guess` field |

### Safety pipeline

All user text goes through `backend/telegram/safety.py`:
1. Unicode NFC normalization
2. C0/C1 control character removal (allows `\n`, `\t`)
3. Length limits: words ≤ 50 chars, clues ≤ 500 chars
4. For words: `word_utils.is_valid_word()` + `word_utils.starts_with_prefix()`
5. For clues: `word_utils.clue_mentions_word()` check
6. Rate limiting: 1s cooldown per session

The `clue_safety` block in `prompts/_common.v1.yaml` (referenced as `$common_clue_safety`) instructs every prompt whose payload can carry clue/history text — `generate_player_move`, `word_master_guess`, `guess_partner_word` — to treat that text as untrusted player communication that cannot override system rules or response schemas. `choose_secret_word` does not reference it: it runs before any game messages exist, so no untrusted text ever reaches it. `backend/tests/test_prompt_content.py` enforces that every prompt file is explicitly classified and that classified-`True` tasks actually reference the block, so this can't silently drift again.

### Observability

Phoenix v17.2.0 runs at `127.0.0.1:6006` (Docker, on the same VPS — see local ops notes for the compose file path). The bot sends traces to a separate project `ai-contact-game-bot` using `arize-phoenix-otel`.

Access Phoenix UI:
```bash
ssh -L 6006:127.0.0.1:6006 user@host -N
# Open http://localhost:6006 → select "ai-contact-game-bot" project
```

User IDs are SHA-256 hashed before export (first 16 hex chars). API keys and tokens are never passed as metadata.

### Deployment

The bot runs as a systemd service on the VPS at `/opt/ai-contact-game/`. It uses the standard systemd + git-pull deploy pattern.

Service file: `deploy/systemd/ai-contact-game.service`
Deploy script: `deploy/scripts/deploy.sh`

Required env vars in `/opt/ai-contact-game/.env`:
```bash
MISTRAL_API_KEY=...
AI_CONTACT_TELEGRAM_BOT_TOKEN=...
# Optional:
ENABLE_PHOENIX_TRACING=true
PHOENIX_COLLECTOR_ENDPOINT=http://127.0.0.1:6006/v1/traces
AI_CONTACT_TELEGRAM_AI_SPECTATOR_MESSAGE_DELAY_SECONDS=1.5  # pacing for "Let LLMs play" mode
```

Management:
```bash
sudo systemctl status ai-contact-game    # status
sudo journalctl -u ai-contact-game -f    # live logs
sudo systemctl restart ai-contact-game   # restart
cd /opt/ai-contact-game && git pull && sudo systemctl restart ai-contact-game  # update
```

### Validation commands

```bash
.venv/bin/python -m unittest backend.tests.tgbot.test_safety
.venv/bin/python -m unittest backend.tests.tgbot.test_session_isolation
.venv/bin/python -m unittest backend.tests.tgbot.test_handlers
.venv/bin/python -m unittest discover backend/tests
```

### Operational troubleshooting

- **Bot not responding**: `sudo journalctl -u ai-contact-game -n 50`. Check token validity with `curl https://api.telegram.org/bot<TOKEN>/getMe`.
- **Game stuck in GAME_RUNNING**: the monitor task may have died. User can `/cancel` or `/newgame` to reset.
- **Session lost after restart**: expected (in-memory). Users start a new game with `/newgame`.
- **Phoenix traces missing**: check `ENABLE_PHOENIX_TRACING=true` in `.env` and that Phoenix Docker container is running: `docker ps | grep phoenix`.
- **Mistral 429 errors**: same behavior as web version — bot will show an error message. Switch models or wait for capacity.

## Git / Release Notes

- Main branch: `main`.
- Remote: `git@github.com:fomin-n/ai-contact-game.git`.
- Public repository: `https://github.com/fomin-n/ai-contact-game`.
- Use concise commits.
- Before pushing code changes, run relevant validation commands and inspect `git status --short`.
