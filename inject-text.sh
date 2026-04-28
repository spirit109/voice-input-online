#!/usr/bin/env bash

set -euo pipefail

MODE="terminal"
DELAY_MS="120"
TEXT=""
TEXT_FILE=""
DRY_RUN="0"

usage() {
  cat <<'EOF'
Usage:
  inject-text.sh [--mode terminal|gui|type] [--delay-ms N] [--text TEXT]
  inject-text.sh [--mode terminal|gui|type] [--delay-ms N] --file PATH
  printf 'text' | inject-text.sh [--mode terminal|gui|type]

Modes:
  terminal  Copy to Wayland clipboard, then press Ctrl+Shift+V.
  gui       Copy to Wayland clipboard, then press Ctrl+V.
  type      Type text through ydotool directly. Slower, but avoids clipboard.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --delay-ms)
      DELAY_MS="${2:-}"
      shift 2
      ;;
    --text)
      TEXT="${2:-}"
      shift 2
      ;;
    --file)
      TEXT_FILE="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$MODE" in
  terminal|gui|type) ;;
  *)
    printf 'Invalid mode: %s\n' "$MODE" >&2
    exit 2
    ;;
esac

if [[ -n "$TEXT_FILE" ]]; then
  if [[ "$TEXT_FILE" == "-" ]]; then
    TEXT="$(cat)"
  elif [[ -f "$TEXT_FILE" ]]; then
    TEXT="$(<"$TEXT_FILE")"
  else
    printf 'Text file not found: %s\n' "$TEXT_FILE" >&2
    exit 1
  fi
elif [[ -z "$TEXT" && ! -t 0 ]]; then
  TEXT="$(cat)"
fi

if [[ -z "$TEXT" ]]; then
  printf 'No text provided.\n' >&2
  exit 1
fi

if [[ "$DRY_RUN" == "1" ]]; then
  printf '%s' "$TEXT"
  exit 0
fi

command -v ydotool >/dev/null || {
  printf 'ydotool is required for injection.\n' >&2
  exit 1
}

if [[ "$MODE" == "type" ]]; then
  printf '%s' "$TEXT" | ydotool type --delay "$DELAY_MS" --file -
  exit 0
fi

command -v wl-copy >/dev/null || {
  printf 'wl-copy is required for clipboard paste mode.\n' >&2
  exit 1
}

printf '%s' "$TEXT" | wl-copy

if [[ "$MODE" == "terminal" ]]; then
  ydotool key --delay "$DELAY_MS" ctrl+shift+v
else
  ydotool key --delay "$DELAY_MS" ctrl+v
fi
