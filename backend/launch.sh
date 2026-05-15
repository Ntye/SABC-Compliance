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

# Create venv — check for activate, not just the directory,
# because a partial venv (missing activate) must be wiped and rebuilt.
if [ ! -f "$ROOT/.venv/bin/activate" ]; then
    echo "Creating virtual environment..."
    rm -rf "$ROOT/.venv"   # remove any incomplete venv from a previous attempt
    if ! python3 -m venv "$ROOT/.venv" 2>/dev/null || [ ! -f "$ROOT/.venv/bin/activate" ]; then
        echo "python3 -m venv failed — attempting to install python3-venv..."
        sudo apt-get install -y python3-venv python3$(python3 -c "import sys;print(f'.{sys.version_info.minor}')")-venv 2>/dev/null || true
        python3 -m venv "$ROOT/.venv"
    fi
    if [ ! -f "$ROOT/.venv/bin/activate" ]; then
        echo "ERROR: Could not create a Python virtual environment."
        echo "  Run: sudo apt-get install python3.11-venv"
        exit 1
    fi
    echo "Virtual environment created."
fi

# Install deps if needed
if ! "$ROOT/.venv/bin/python" -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    "$ROOT/.venv/bin/python" -m ensurepip --upgrade 2>/dev/null || true
    "$ROOT/.venv/bin/python" -m pip install -q --upgrade pip
    "$ROOT/.venv/bin/python" -m pip install -q -r "$ROOT/requirements.txt"
    echo "Dependencies installed."
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

# Run — use the venv's uvicorn directly; no need to source activate
UVICORN="$ROOT/.venv/bin/uvicorn"
if [ "${ENVIRONMENT:-development}" = "production" ]; then
    exec "$UVICORN" src.main:app --host 0.0.0.0 --port "$PORT"
else
    exec "$UVICORN" src.main:app --host 0.0.0.0 --port "$PORT" --reload
fi
