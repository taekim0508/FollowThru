#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$ROOT_DIR/server"
VENV_DIR="$ROOT_DIR/.venv"
ENV_FILE="$SERVER_DIR/.env"
ENV_EXAMPLE="$SERVER_DIR/.env.example"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if ! python3 -c "import fastapi, uvicorn, sqlmodel, pydantic_settings, openai" >/dev/null 2>&1; then
  echo "Installing backend dependencies..."
  python3 -m pip install -r "$SERVER_DIR/requirements.txt"
fi

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "Created $ENV_FILE from .env.example"
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${OPENAI_API_KEY:-}" || "${OPENAI_API_KEY:-}" == "sk-your-openai-key-here" ]]; then
  echo "OPENAI_API_KEY is missing in $ENV_FILE"
  echo "Add your real OpenAI key, then rerun ./run_backend_ai.sh"
  exit 1
fi

export AI_PROVIDER="openai"
export OPENAI_MODEL="${OPENAI_MODEL:-gpt-4o-mini}"
cd "$SERVER_DIR"
echo "Starting backend in AI mode on http://127.0.0.1:8000"
exec python3 -m uvicorn app.main:app --port 8000
