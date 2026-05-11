# AGENTS.md

This file is the agent-facing operating guide for `ai-contact-game`. Keep `README.md` concise for humans; put detailed implementation context here.

## Project Overview

`ai-contact-game` is a small full-stack LLM-agent game inspired by the Russian word game "Есть контакт" / "Contact".

The observer starts a game from the web UI. Three AI roles then play automatically:

- `Word Master`: chooses and knows the secret word, reveals prefixes, and tries to intercept player clues.
- `Player A` and `Player B`: do not know the secret word. They only know the current prefix, redacted full public session history, used words, language, and their own personality text.
- The observer may provide `secretWord` in `StartGameRequest`; when present, backend validation normalizes it and Word Master skips the LLM secret-word selection step.

The frontend is observer-only. All game rules, prompts, LLM calls, state transitions, validation, and deterministic word comparison belong on the Python backend.

## Repository Structure

- `backend/app/main.py`: FastAPI app and REST routes.
- `backend/app/game.py`: backend-owned game state, loop, turn transitions, visible message timing, finish/error handling.
- `backend/app/agents.py`: LLM task helpers, validation, retry/repair behavior.
- `backend/app/word_utils.py`: deterministic normalization and word comparison.
- `backend/app/config.py`: provider/model configuration from environment variables.
- `backend/app/event_log.py`: JSONL event logging with secret redaction.
- `backend/app/prompt_loader.py`: YAML prompt loading/rendering.
- `backend/app/providers/`: provider interface and implementations.
- `backend/app/schemas.py`: Pydantic API and game data models.
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
```

There is no dedicated automated test suite yet.

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

## Provider Architecture

Game logic depends on `LLMProvider`, not on concrete providers.

Current provider files:

- `backend/app/providers/base.py`: generic provider interface.
- `backend/app/providers/mistral.py`: Mistral provider.
- `backend/app/providers/openai_compatible.py`: OpenAI-compatible provider.
- `backend/app/providers/http_json.py`: shared Chat Completions HTTP/JSON handling, response parsing, capacity errors.
- `backend/app/providers/factory.py`: provider selection.

To add a provider:

1. Implement `LLMProvider.chat_json(...)`.
2. Register the provider in `factory.py`.
3. Read API keys/models from environment variables in the provider class.
4. Keep game logic provider-agnostic.

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
- `maxTurns` defaults to `50`; reaching it ends the game with Word Master winning.

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
- start/reset buttons
- game state display
- chat-style timeline
- used word chips
- compact model display
- React Query config/game-state queries and start/reset mutations

Do not move game rules, validation, prompt logic, provider logic, or turn logic into the frontend.

## Runtime Logs

Runtime logs are JSON Lines:

```text
logs/ai-contact-game.jsonl
```

This file is gitignored. `logs/.gitkeep` is tracked.

Logs include game state, prompts, provider request/response metadata, parsed LLM responses, validation failures, and game-loop exceptions. They may include game data such as secret words and player personality text. Review logs before sharing them publicly.

`backend/app/event_log.py` redacts known API-key fields, bearer tokens, common key formats, and current provider key environment values before writing logs.

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

## Git / Release Notes

- Main branch: `main`.
- Remote: `git@github.com:fomin-n/ai-contact-game.git`.
- Public repository: `https://github.com/fomin-n/ai-contact-game`.
- Use concise commits.
- Before pushing code changes, run relevant validation commands and inspect `git status --short`.
