#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_DIR="$HOME/桌面"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

UI_LANGUAGE="${VOICE_INPUT_UI_LANGUAGE:-zh-CN}"

msg() {
  local key="$1"
  case "$UI_LANGUAGE:$key" in
    en*:terminal_name) printf 'Azure Voice Input (Terminal)' ;;
    en*:gui_name) printf 'Azure Voice Input (Text Fields)' ;;
    en*:apps) printf 'Installed application launchers to: %s\n' "$2" ;;
    en*:desktop) printf 'Installed desktop launchers to: %s\n' "$2" ;;
    en*:shortcut) printf 'Installed GNOME shortcut: %s -> %s\n' "$2" "$3" ;;
    *:terminal_name) printf 'Azure 语音输入（终端）' ;;
    *:gui_name) printf 'Azure 语音输入（普通输入框）' ;;
    *:apps) printf '已安装应用启动器到：%s\n' "$2" ;;
    *:desktop) printf '已安装桌面快捷方式到：%s\n' "$2" ;;
    *:shortcut) printf '已安装 GNOME 快捷键：%s -> %s\n' "$2" "$3" ;;
  esac
}

TERMINAL_KEYBINDING_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/azure-voice-input-terminal/"
TERMINAL_KEYBINDING_NAME="$(msg terminal_name)"
TERMINAL_KEYBINDING_COMMAND="$SCRIPT_DIR/voice-input-once.sh --mode terminal"
TERMINAL_KEYBINDING_ACCEL="${VOICE_INPUT_TERMINAL_SHORTCUT:-<Control><Alt>space}"

GUI_KEYBINDING_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/azure-voice-input-gui/"
GUI_KEYBINDING_NAME="$(msg gui_name)"
GUI_KEYBINDING_COMMAND="$SCRIPT_DIR/voice-input-once.sh --mode gui"
GUI_KEYBINDING_ACCEL="${VOICE_INPUT_GUI_SHORTCUT:-<Control><Alt>slash}"

if [[ ! -d "$DESKTOP_DIR" && -d "$HOME/Desktop" ]]; then
  DESKTOP_DIR="$HOME/Desktop"
fi

install -d "$APP_DIR"
install -m 0644 "$SCRIPT_DIR/azure-voice-input-settings.desktop" "$APP_DIR/azure-voice-input-settings.desktop"
install -m 0644 "$SCRIPT_DIR/azure-voice-input-terminal.desktop" "$APP_DIR/azure-voice-input-terminal.desktop"
install -m 0644 "$SCRIPT_DIR/azure-voice-input-gui.desktop" "$APP_DIR/azure-voice-input-gui.desktop"

if [[ -d "$DESKTOP_DIR" ]]; then
  install -m 0755 "$SCRIPT_DIR/azure-voice-input-settings.desktop" "$DESKTOP_DIR/azure-voice-input-settings.desktop"
  install -m 0755 "$SCRIPT_DIR/azure-voice-input-terminal.desktop" "$DESKTOP_DIR/azure-voice-input-terminal.desktop"
  install -m 0755 "$SCRIPT_DIR/azure-voice-input-gui.desktop" "$DESKTOP_DIR/azure-voice-input-gui.desktop"
  if command -v gio >/dev/null; then
    gio set "$DESKTOP_DIR/azure-voice-input-settings.desktop" metadata::trusted true 2>/dev/null || true
    gio set "$DESKTOP_DIR/azure-voice-input-terminal.desktop" metadata::trusted true 2>/dev/null || true
    gio set "$DESKTOP_DIR/azure-voice-input-gui.desktop" metadata::trusted true 2>/dev/null || true
  fi
fi

if command -v update-desktop-database >/dev/null; then
  update-desktop-database "$APP_DIR" 2>/dev/null || true
fi

if command -v gsettings >/dev/null; then
  current="$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings)"
  updated="$(python3 - "$current" "$TERMINAL_KEYBINDING_PATH" "$GUI_KEYBINDING_PATH" <<'PY'
import ast
import sys

raw, paths = sys.argv[1], sys.argv[2:]
try:
    items = ast.literal_eval(raw.replace("@as ", ""))
except Exception:
    items = []
for path in paths:
    if path not in items:
        items.append(path)
print("[" + ", ".join(repr(item) for item in items) + "]")
PY
)"
  gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$updated"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$TERMINAL_KEYBINDING_PATH" name "$TERMINAL_KEYBINDING_NAME"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$TERMINAL_KEYBINDING_PATH" command "$TERMINAL_KEYBINDING_COMMAND"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$TERMINAL_KEYBINDING_PATH" binding "$TERMINAL_KEYBINDING_ACCEL"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$GUI_KEYBINDING_PATH" name "$GUI_KEYBINDING_NAME"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$GUI_KEYBINDING_PATH" command "$GUI_KEYBINDING_COMMAND"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$GUI_KEYBINDING_PATH" binding "$GUI_KEYBINDING_ACCEL"
fi

msg apps "$APP_DIR"
if [[ -d "$DESKTOP_DIR" ]]; then
  msg desktop "$DESKTOP_DIR"
fi
msg shortcut "$TERMINAL_KEYBINDING_ACCEL" "$TERMINAL_KEYBINDING_COMMAND"
msg shortcut "$GUI_KEYBINDING_ACCEL" "$GUI_KEYBINDING_COMMAND"
