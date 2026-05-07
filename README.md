# AI Contact Game

A small LLM-agent experiment inspired by the Russian word game **"Есть контакт" / "Contact"**.

Three AI agents play while you watch:

- **Word Master** secretly chooses a word and tries to intercept clues.
- **Player A** and **Player B** only know the revealed prefix and try to make contact.
- The observer sees the secret word, the prefix, used words, and the full chat timeline.

The project is intentionally small: Python runs the game and AI calls, React renders the observer UI.

## Repository

GitHub: [fomin-n/ai-contact-game](https://github.com/fomin-n/ai-contact-game)

## Stack

- Backend: Python, FastAPI
- Frontend: React, TypeScript, Vite
- AI providers: Mistral by default, OpenAI-compatible providers supported
- Game state: in-memory backend state

## Quick Start

Install backend dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Set AI credentials:

```bash
export AI_PROVIDER=mistral
export MISTRAL_API_KEY=...
export MISTRAL_MODEL=mistral-small-latest
```

Start the backend:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Install and start the frontend in another terminal:

```bash
npm install
npm run dev
```

Open the Vite URL, usually:

```text
http://127.0.0.1:5173
```

For another backend port:

```bash
BACKEND_PORT=9000 npm run dev
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
