#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="terminal"
APPEND_NEWLINE="0"
END_SILENCE_MS="${AZURE_SPEECH_END_SILENCE_MS:-700}"
MAX_SECONDS="${VOICE_INPUT_MAX_SECONDS:-45}"
LOCK_FILE="${XDG_RUNTIME_DIR:-/tmp}/voice-input-online.lock"

usage() {
  cat <<'EOF'
Usage:
  voice-input-once.sh [--mode terminal|gui|type] [--append-newline]

Starts one Azure Speech recognition pass from the default microphone and
injects the recognized text into the active input.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --append-newline)
      APPEND_NEWLINE="1"
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

notify() {
  if command -v notify-send >/dev/null; then
    notify-send "$@"
  fi
}

if ! command -v flock >/dev/null; then
  printf 'flock is required.\n' >&2
  exit 1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  notify "Azure 语音输入" "正在识别中，请继续说话或等待结束。"
  exit 0
fi

notify "Azure 语音输入" "开始说话，停顿后自动输入。"

args=(
  "--mode" "$MODE"
  "--end-silence-ms" "$END_SILENCE_MS"
)

if [[ "$APPEND_NEWLINE" == "1" ]]; then
  args+=("--append-newline")
fi

run_command=("$SCRIPT_DIR/run-azure-voice-input.sh" "${args[@]}")
if command -v timeout >/dev/null; then
  run_command=(timeout --kill-after=5s "${MAX_SECONDS}s" "${run_command[@]}")
fi

output_file="$(mktemp "${TMPDIR:-/tmp}/voice-input-online.XXXXXX")"
error_file="$(mktemp "${TMPDIR:-/tmp}/voice-input-online.err.XXXXXX")"
trap 'rm -f "$output_file" "$error_file"' EXIT

if "${run_command[@]}" >"$output_file" 2>"$error_file"; then
  transcript="$(tail -n 1 "$output_file" | sed 's/[[:space:]]*$//')"
  if [[ -n "$transcript" ]]; then
    notify "Azure 语音输入" "$transcript"
  else
    notify "Azure 语音输入" "已完成。"
  fi
else
  status="$?"
  message="$(tail -n 3 "$error_file" | sed '/^[[:space:]]*$/d' | tr '\n' ' ')"
  if [[ "$status" == "124" || "$status" == "137" ]]; then
    message="识别超时，已自动结束。请重新触发后再说。"
  elif [[ -z "$message" ]]; then
    message="识别失败，请检查网络、密钥或麦克风。"
  fi
  notify "Azure 语音输入失败" "$message"
  printf '%s\n' "$message" >&2
  exit 1
fi
