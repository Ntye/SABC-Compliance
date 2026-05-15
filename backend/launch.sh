#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR"

cd "$ROOT"

# Check Python 3.11+
if ! python3 --version 2>&1 | grep -qE "3\.(1[1-9]|[2-9][0-9])"; then
    echo "ERROR: Python 3.11+ required. Found: $(python3 --version 2>&1)"
    exit 1
fi

# Create venv
if [ ! -d "$ROOT/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$ROOT/.venv"
fi

# Install deps if needed
if ! "$ROOT/.venv/bin/python" -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    "$ROOT/.venv/bin/pip" install -q --upgrade pip
    "$ROOT/.venv/bin/pip" install -q -r "$ROOT/requirements.txt"
fi

# Create directories
mkdir -p "$ROOT/keys" "$ROOT/data"

# Generate SSH key if missing
SSH_KEY_PATH="${SSH_KEY_PATH:-$ROOT/keys/ansible_id_rsa}"
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "Generating SSH key pair..."
    ssh-keygen -t rsa -b 4096 -f "$SSH_KEY_PATH" -N "" -C "bdc-ansible"
fi

# Load .env
if [ -f "$ROOT/.env" ]; then
    set -a; source "$ROOT/.env"; set +a
fi

# Defaults
export PORT="${PORT:-3000}"
export DB_PATH="${DB_PATH:-./data/platform.db}"
export SSH_KEY_PATH="${SSH_KEY_PATH:-./keys/ansible_id_rsa}"
export ANSIBLE_DIR="${ANSIBLE_DIR:-./ansible}"

# Kill existing process on PORT
if command -v lsof &>/dev/null; then
    EXISTING_PID=$(lsof -ti :"$PORT" 2>/dev/null || true)
    if [ -n "$EXISTING_PID" ]; then
        echo "Killing existing process on port $PORT (PID: $EXISTING_PID)"
        kill -9 "$EXISTING_PID" 2>/dev/null || true
    fi
fi

# Run
source "$ROOT/.venv/bin/activate"
if [ "${ENVIRONMENT:-development}" = "production" ]; then
    exec uvicorn src.main:app --host 0.0.0.0 --port "$PORT"
else
    exec uvicorn src.main:app --host 0.0.0.0 --port "$PORT" --reload
fi
