#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  printf 'Virtual environment not found: %s\n' "$VENV_DIR" >&2
  printf 'Create it with:\n' >&2
  printf '  cd %q && python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt\n' "$SCRIPT_DIR" >&2
  exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/azure_voice_input.py" "$@"
