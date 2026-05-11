#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="${VENV_DIR-}"
PYTHON_BIN="${PYTHON_BIN-}"
BACKEND_PORT="${BACKEND_PORT-}"
FRONTEND_PORT="${FRONTEND_PORT-}"
INSTALL_ONLY=0

usage() {
  cat <<'EOF'
Usage: ./scripts/dev.sh [--install-only]

Installs local dependencies and starts both development servers:
- FastAPI backend on 127.0.0.1:8000 by default
- Vite frontend on 0.0.0.0:5173 by default

Environment:
- Copy .env.example to .env, then fill API keys.
- Existing shell environment variables override .env values and defaults.
EOF
}

log() {
  printf '\n[%s] %s\n' "ai-contact-game" "$*"
}

die() {
  printf '\n[ai-contact-game] ERROR: %s\n' "$*" >&2
  exit 1
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

unquote() {
  local value="$1"
  local length=${#value}
  if [[ "$length" -ge 2 ]]; then
    if [[ "${value:0:1}" == '"' && "${value:$((length - 1)):1}" == '"' ]]; then
      printf '%s' "${value:1:$((length - 2))}"
      return
    fi
    if [[ "${value:0:1}" == "'" && "${value:$((length - 1)):1}" == "'" ]]; then
      printf '%s' "${value:1:$((length - 2))}"
      return
    fi
  fi
  printf '%s' "$value"
}

load_env_file() {
  local file="$1"
  local line key value
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="$(trim "$line")"
    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
    [[ "$line" == export\ * ]] && line="$(trim "${line#export }")"
    key="$(trim "${line%%=*}")"
    value="$(trim "${line#*=}")"
    [[ "$line" == *"="* ]] || die "Invalid .env line without '=': $line"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "Invalid .env key: $key"
    if [[ -z "${!key+x}" ]]; then
      export "$key=$(unquote "$value")"
    fi
  done < "$file"
}

for arg in "$@"; do
  case "$arg" in
    --install-only)
      INSTALL_ONLY=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $arg"
      ;;
  esac
done

cd "$ROOT_DIR"

if [[ -f ".env" ]]; then
  log "Loading .env"
  load_env_file ".env"
fi

VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Python executable not found: $PYTHON_BIN"
command -v npm >/dev/null 2>&1 || die "npm is required but was not found"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  log "Creating Python virtual environment"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

log "Installing Python dependencies"
"$VENV_DIR/bin/python" -m pip install -r requirements.txt

log "Installing Node dependencies"
npm install --prefix "$FRONTEND_DIR"

if [[ -z "${MISTRAL_API_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
  log "No provider API key found. The app will open, but games will fail until MISTRAL_API_KEY or OPENAI_API_KEY is set."
  log "Copy .env.example to .env and fill in credentials."
fi

if [[ "$INSTALL_ONLY" == "1" ]]; then
  log "Install-only mode complete"
  exit 0
fi

cleanup() {
  log "Stopping development servers"
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

log "Starting backend on http://127.0.0.1:$BACKEND_PORT"
"$VENV_DIR/bin/uvicorn" backend.app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!

log "Starting frontend on http://127.0.0.1:$FRONTEND_PORT"
BACKEND_PORT="$BACKEND_PORT" npm --prefix "$FRONTEND_DIR" run dev -- --port "$FRONTEND_PORT" &
FRONTEND_PID=$!

log "Open http://127.0.0.1:$FRONTEND_PORT"
while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID"
    exit $?
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    wait "$FRONTEND_PID"
    exit $?
  fi
  sleep 1
done
