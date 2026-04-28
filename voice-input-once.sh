#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

MODE="terminal"
APPEND_NEWLINE="0"
END_SILENCE_MS="${AZURE_SPEECH_END_SILENCE_MS:-700}"
MAX_SECONDS="${VOICE_INPUT_MAX_SECONDS:-45}"
UI_LANGUAGE="${VOICE_INPUT_UI_LANGUAGE:-zh-CN}"
LOCK_FILE="${XDG_RUNTIME_DIR:-/tmp}/voice-input-online.lock"

msg() {
  local key="$1"
  case "$UI_LANGUAGE:$key" in
    en*:app) printf 'Azure Voice Input' ;;
    en*:failed_title) printf 'Azure Voice Input Failed' ;;
    en*:busy) printf 'Recognition is already running. Keep speaking or wait for it to finish.' ;;
    en*:start) printf 'Speak now. Text will be inserted after silence.' ;;
    en*:done) printf 'Done.' ;;
    en*:timeout) printf 'Recognition timed out and was stopped. Trigger it again before speaking.' ;;
    en*:failed) printf 'Recognition failed. Check network, credentials, or microphone.' ;;
    en*:flock) printf 'flock is required.' ;;
    en*:invalid_mode) printf 'Invalid mode: %s' "${2:-}" ;;
    *:app) printf 'Azure 语音输入' ;;
    *:failed_title) printf 'Azure 语音输入失败' ;;
    *:busy) printf '正在识别中，请继续说话或等待结束。' ;;
    *:start) printf '开始说话，停顿后自动输入。' ;;
    *:done) printf '已完成。' ;;
    *:timeout) printf '识别超时，已自动结束。请重新触发后再说。' ;;
    *:failed) printf '识别失败，请检查网络、密钥或麦克风。' ;;
    *:flock) printf '缺少 flock 命令。' ;;
    *:invalid_mode) printf '无效模式：%s' "${2:-}" ;;
  esac
}

usage() {
  if [[ "$UI_LANGUAGE" == en* ]]; then
  cat <<'EOF'
Usage:
  voice-input-once.sh [--mode terminal|gui|type] [--append-newline]

Starts one Azure Speech recognition pass from the default microphone and
injects the recognized text into the active input.
EOF
  else
  cat <<'EOF'
用法：
  voice-input-once.sh [--mode terminal|gui|type] [--append-newline]

从默认麦克风启动一次 Azure 语音识别，并将识别文本输入到当前光标位置。
EOF
  fi
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
    printf '%s\n' "$(msg invalid_mode "$MODE")" >&2
    exit 2
    ;;
esac

notify() {
  if command -v notify-send >/dev/null; then
    notify-send "$@"
  fi
}

if ! command -v flock >/dev/null; then
  printf '%s\n' "$(msg flock)" >&2
  exit 1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  notify "$(msg app)" "$(msg busy)"
  exit 0
fi

notify "$(msg app)" "$(msg start)"

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
    notify "$(msg app)" "$transcript"
  else
    notify "$(msg app)" "$(msg done)"
  fi
else
  status="$?"
  detail="$(tail -n 3 "$error_file" | sed '/^[[:space:]]*$/d' | tr '\n' ' ')"
  if [[ "$status" == "124" || "$status" == "137" ]]; then
    message="$(msg timeout)"
  else
    message="$(msg failed)"
  fi
  notify "$(msg failed_title)" "$message"
  printf '%s\n' "$message" >&2
  if [[ -n "$detail" ]]; then
    printf '%s\n' "$detail" >&2
  fi
  exit 1
fi
