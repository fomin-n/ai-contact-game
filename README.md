# AI Contact Game

A small LLM-agent experiment inspired by the Russian word game "Есть контакт" / "Contact".

The Python backend owns the game state, game loop, word validation, deterministic comparisons, prompts, LLM response repair, used-word tracking, and AI-provider calls. The React frontend only renders controls/state and sends start/reset requests.

The Word Master is required to make a concrete guess every turn. It may not return `null`, "no guess", the secret word, or any word already used in the current session.

## Stack

- Backend: Python + FastAPI
- Frontend: React + TypeScript + Vite
- API: REST endpoints with frontend polling
- Default AI provider: Mistral

## Run The Backend

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The backend API runs at `http://127.0.0.1:8000`.
Environment variables can be exported in the same shell or placed in a local `.env` file.

## Run The Frontend

In another terminal:

```bash
npm install
npm run dev
```

Open the URL printed by Vite, usually `http://127.0.0.1:5173`.

To open the app from another computer on the same WiFi, use your computer's LAN IP with the Vite port, for example `http://192.168.1.26:5173`. The frontend listens on `0.0.0.0`; the Python backend can stay local because Vite proxies `/api/*` to it.

Vite proxies `/api/*` to the backend port. If you use another backend port:

```bash
BACKEND_PORT=9000 npm run dev
```

## Environment Variables

Default Mistral setup:

```bash
AI_PROVIDER=mistral
MISTRAL_API_KEY=...
MISTRAL_MODEL=mistral-small-latest
```

Mixed setup with Mistral as Word Master and OpenAI for both players:

```bash
WORD_MASTER_PROVIDER=mistral
PLAYER_A_PROVIDER=openai
PLAYER_B_PROVIDER=openai
MISTRAL_API_KEY=...
OPENAI_API_KEY=...
WORD_MASTER_MODEL=mistral-small-latest
PLAYER_A_MODEL=gpt-4.1-mini
PLAYER_B_MODEL=gpt-4.1-mini
```

Optional role-specific model overrides:

```bash
WORD_MASTER_MODEL=mistral-small-latest
PLAYER_A_MODEL=mistral-small-latest
PLAYER_B_MODEL=mistral-small-latest
```

Provider-specific role overrides are also supported, for example `MISTRAL_WORD_MASTER_MODEL`, `OPENAI_PLAYER_A_MODEL`, and `OPENAI_PLAYER_B_MODEL`.

OpenAI-compatible setup:

```bash
AI_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
```

If the selected provider API key is missing, invalid, rate-limited, or unreachable, the backend stops the game and shows an error message in the timeline. There are no built-in candidate word lists.

For provider capacity errors such as Mistral HTTP 429 `service_tier_capacity_exceeded`, the backend waits before retrying instead of sending all retry attempts immediately. If the provider remains unavailable, switch the affected role to another model/provider or wait for capacity to recover.

For example, if `mistral-small-latest` is capacity-limited, keep Word Master on Mistral but switch only that role:

```bash
WORD_MASTER_PROVIDER=mistral
WORD_MASTER_MODEL=mistral-medium-latest
```

## Prompt Management

Prompt templates live in the repo-root `prompts/` directory:

- `choose_secret_word.v1.yaml`
- `generate_player_move.v1.yaml`
- `word_master_guess.v1.yaml`
- `guess_partner_word.v1.yaml`
- `_common.v1.yaml`

Each task prompt includes:

- `id`
- `version`
- `temperature`
- `model_role`
- `schema`
- `system`
- `user`

The backend loads and renders prompts through `backend/app/prompt_loader.py`. The game logic in `backend/app/agents.py` passes dynamic game state as JSON in the user message, including language, prefix, used words, public history, clue text, and player personality. Personality is treated as untrusted style guidance and is not inserted into system prompts.

Common rules are stored once in `_common.v1.yaml` and injected into task prompts with variables such as `$common_json_only`, `$common_prefix_rule`, and `$common_used_words_rule`.

To edit a prompt without changing its version, update the matching YAML file and restart the backend. To add a new prompt version:

1. Copy a task file, for example `generate_player_move.v1.yaml` to `generate_player_move.v2.yaml`.
2. Change `version: v2` and edit the prompt text, schema, or temperature.
3. Update the backend call to `render_prompt(..., version="v2")` for the task you want to test.
4. Keep Python validation unchanged unless the actual game rules changed.

If no matching `_common.<version>.yaml` exists, the loader reuses `_common.v1.yaml`.

Prompt schemas are included in YAML for readability and review. For provider calls, the backend also passes JSON schema generated from the relevant Pydantic response model where the provider supports structured outputs. The Python validators remain the source of truth for prefixes, used words, valid word shape, clue restrictions, and deterministic equality.

Prompt call logs include task name, prompt id, prompt version, provider, model, attempt number, and validation failure reason when present.

## Debug Logs

Runtime debug logs are written as JSON Lines to:

```text
logs/ai-contact-game.jsonl
```

That file is gitignored. The `logs/` directory is kept in the repo with `logs/.gitkeep`.

The log includes:

- game start/reset/finish events
- game state mutations and visible messages
- selected secret word, turn starts, intended words, guesses, and used words
- rendered LLM prompt messages
- provider request bodies without API keys
- provider HTTP responses
- parsed LLM JSON candidates
- validation successes and failures
- backend game-loop exceptions

These logs intentionally include local game data, including secret words and player personality text, so do not share them publicly without reviewing them first. API keys are not logged.

## If Mistral Is Not Working

Check these first:

1. Confirm `MISTRAL_API_KEY` is exported in the same shell that starts `uvicorn`.
2. Confirm `AI_PROVIDER=mistral`.
3. Try `MISTRAL_MODEL=mistral-small-latest`.
4. Restart the backend after changing environment variables.
5. Check the backend terminal for the provider HTTP status and response body.
6. Verify your Mistral account has credits/quota and that the API key has not expired.
7. If JSON output validation fails, try a stronger model or lower traffic/rate pressure.

## Current Agent Models

The frontend displays the active provider and model names from `/api/config` and `/api/game/state`:

- AI provider: `AI_PROVIDER`, or `mixed` when roles use different providers
- Word Master provider: `WORD_MASTER_PROVIDER`, defaulting to `AI_PROVIDER`
- Player A provider: `PLAYER_A_PROVIDER`, defaulting to `AI_PROVIDER`
- Player B provider: `PLAYER_B_PROVIDER`, defaulting to `AI_PROVIDER`
- Word Master model: `WORD_MASTER_MODEL`, provider-specific override, or provider default
- Player A model: `PLAYER_A_MODEL`, provider-specific override, or provider default
- Player B model: `PLAYER_B_MODEL`, provider-specific override, or provider default

The current recommended mixed test setup is Word Master on `mistral-small-latest` and both players on `gpt-4.1-mini`.

Model and provider selection is independent from prompt selection. YAML prompt files define task instructions and temperature; environment variables define which provider/model each role uses.

## Switching Providers

Provider selection is controlled globally by `AI_PROVIDER`, and per role by `WORD_MASTER_PROVIDER`, `PLAYER_A_PROVIDER`, and `PLAYER_B_PROVIDER`.

Existing provider implementations live in `backend/app/providers`:

- `mistral.py`: default Mistral provider
- `openai_compatible.py`: OpenAI-compatible provider
- `base.py`: generic `LLMProvider` interface
- `factory.py`: provider selection

To add a new provider:

1. Add a new class implementing `LLMProvider.chat_json(...)`.
2. Register it in `backend/app/providers/factory.py`.
3. Add any environment variables and defaults in the provider class.
4. Optionally document provider-specific role model overrides.

Game logic depends only on the generic provider interface, not on Mistral-specific code.

## Checks

```bash
npm run typecheck
npm run build
.venv/bin/python -m compileall backend
```

## Notes

Word equality is deterministic on the Python backend. The app trims whitespace, lowercases words, strips surrounding quotes, normalizes Russian `ё` to `е`, and compares normalized strings exactly. It does not use an LLM judge, fuzzy matching, embeddings, or semantic matching for equality.

Visible Player A, Player B, and Word Master messages are delayed by about one second in the backend game loop. System messages appear immediately, and the frontend remains responsive because it polls backend state and reset cancels the active backend task.
