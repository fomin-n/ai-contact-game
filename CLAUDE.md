# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `AGENTS.md` for the full engineering reference (architecture, game rules, prompt management, provider setup, security notes).

## Commands

**Run everything (installs deps + starts servers):**
```bash
cp .env.example .env   # fill in at least one API key first
./scripts/dev.sh
```

**Install deps without starting servers:**
```bash
./scripts/dev.sh --install-only
```

**Validate before committing:**
```bash
cd frontend && npm run typecheck && npm run build && cd ..
.venv/bin/python -m compileall backend
.venv/bin/python -m unittest discover backend/tests
```

**Run a single test file:**
```bash
.venv/bin/python -m unittest backend.tests.test_human_modes
```

**Manual backend only:**
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Architecture

Full-stack app: Python/FastAPI backend + React/TypeScript/Vite frontend. Game state is in-memory.

**Backend** (`backend/app/`):
- `main.py` — FastAPI routes (`/api/game/*`)
- `game.py` — game state, turn loop, win/loss transitions
- `agents.py` — LLM calls with retry/repair feedback (max 5 attempts, exponential backoff)
- `word_utils.py` — deterministic word normalization and comparison (no LLM equality checks ever)
- `config.py` — resolves per-run `AgentProviderConfig`/`AgentModelConfig` from env vars + request
- `model_catalog.py` — static curated provider/model list returned by `/api/config`; do not fetch dynamically
- `event_log.py` — JSONL event log at `logs/ai-contact-game.jsonl`; redacts API keys before writing
- `providers/` — provider abstraction; `factory.py` selects based on env vars
- `schemas.py` — Pydantic models for all API shapes
- `prompt_loader.py` — renders YAML prompt templates from `prompts/`

**Frontend** (`frontend/src/`):
- `hooks/useGameController.ts` — React Query orchestration; keep this UI-only
- `api/gameApi.ts` — thin typed REST client; no React logic here
- `types/game.ts` — TypeScript types mirroring backend response shapes
- `components/` — colocated `.tsx` + `.css` + `index.ts` per component
- `i18n/copy.ts` — all UI copy lives here

**Data flow:** Frontend polls `/api/game/state` → `POST /api/game/start` kicks off the backend turn loop → backend calls LLMs via `agents.py` → state updates → frontend re-renders. Human moves pause the loop via `GameState.pendingUserInput`; `POST /api/game/user-input` resumes it.

## Key Invariants

- All game rules, validation, LLM calls, and turn logic live on the backend. The frontend renders only.
- Word comparison is always deterministic (`word_utils.py`). Never use an LLM or fuzzy match to check equality.
- Players never receive the secret word in prompts. In `humanRole="playerA"`, `secretWord` is redacted from client-facing state until the game ends.
- `usedWords` grows with: player intended word, Word Master guess, partner guess, and secret word on game end. Ordinary clue text words are not added.
- If an LLM/provider fails after retries, surface an error — do not silently substitute words.
- The backend owns provider/model selection end-to-end: `/api/config` returns choices, `config.py::resolve_agent_configs` validates them, and `GameManager.start` binds the per-run config. The frontend only displays choices and sends selected ids — it must never expose API keys.
