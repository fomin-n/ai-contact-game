# AI Contact Game

A small LLM-agent experiment inspired by the Russian word game **"Есть контакт" / "Contact"**.

Three AI agents play while you watch:

- **Word Master** secretly chooses a word and tries to intercept clues.
- **Player A** and **Player B** only know the revealed prefix and try to make contact.
- The observer sees the secret word, the prefix, used words, and the full chat timeline.

The project is intentionally small: Python runs the game and AI calls, React renders the observer UI.

## Rules

In the original game, a Word Master thinks of a word and reveals its first letter. Other players give clue-like definitions for different words that start with the revealed letter or prefix. If another player understands the clue, they announce contact; the Word Master has a chance to guess and block it. If the players name the same word, the Word Master reveals the next letter. The round ends when the secret word is named.

This project adapts that structure for three LLM agents: one Word Master and two players. The observer sees the secret word and watches the whole exchange as chat messages.

## Repository

GitHub: [fomin-n/ai-contact-game](https://github.com/fomin-n/ai-contact-game)

## Stack

- Backend: Python, FastAPI
- Frontend: React, TypeScript, Vite
- AI providers: Mistral by default, OpenAI-compatible providers supported
- Game state: in-memory backend state

## Quick Start

Create a local environment file:

```bash
cp .env.example .env
```

Fill in at least one API key in `.env`, then run everything with one command:

```bash
./scripts/dev.sh
```

The script installs Python and Node dependencies, starts the FastAPI backend, starts the Vite frontend, and prints the local URL.

Open:

```text
http://127.0.0.1:5173
```

Ports can be changed in `.env` or for a single run:

```bash
BACKEND_PORT=9000 FRONTEND_PORT=5174 ./scripts/dev.sh
```

To install dependencies without starting servers:

```bash
./scripts/dev.sh --install-only
```

## Useful Commands

```bash
npm run typecheck
npm run build
.venv/bin/python -m compileall backend
```

## Notes

- Do not commit `.env*`, runtime logs, `.venv`, `node_modules`, or `dist`.
- Detailed engineering notes for coding agents live in [AGENTS.md](./AGENTS.md).
