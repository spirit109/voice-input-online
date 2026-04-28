# Ubuntu Wayland Voice Input Injection

This folder contains the small injection layer for online or local speech
transcription tools.

## Current system finding

The machine runs Ubuntu GNOME on Wayland. `xdotool` is not reliable for native
Wayland apps, including GNOME Terminal and Wayland Chrome. Use `ydotool`
through `/dev/uinput` instead.

The required udev rule is:

```text
KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"
```

It is installed at:

```text
/etc/udev/rules.d/99-uinput-ydotool.rules
```

## Inject recognized text

For GNOME Terminal command lines:

```bash
printf 'ls -la' | ./inject-text.sh --mode terminal
```

For regular GUI text fields:

```bash
printf 'hello world' | ./inject-text.sh --mode gui
```

If clipboard paste fails in a specific app, try direct typing:

```bash
printf 'hello world' | ./inject-text.sh --mode type
```

## Online ASR integration point

An online ASR script should send the final recognized text to this command:

```bash
printf '%s' "$TRANSCRIPT" | /home/kk/AI/CODEX/voice-input-online+20260426/inject-text.sh --mode terminal
```

## Azure Speech input

Install dependencies in the project virtual environment:

```bash
cd /home/kk/AI/CODEX/voice-input-online+20260426
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Open the configuration GUI:

```bash
/home/kk/AI/CODEX/voice-input-online+20260426/run-gui.sh
```

The GUI includes Azure credential entry, shortcut configuration, local quota
estimation, diagnostics, and the Azure setup guide.

Set credentials from an Azure AI Speech resource:

```bash
export AZURE_SPEECH_KEY='your-key'
export AZURE_SPEECH_REGION='eastasia'
```

Or create a local `.env` from `.env.example`; `.env` is ignored by git:

```bash
cd /home/kk/AI/CODEX/voice-input-online+20260426
cp .env.example .env
```

Recognize one utterance from the default microphone and inject it into GNOME
Terminal:

```bash
/home/kk/AI/CODEX/voice-input-online+20260426/run-azure-voice-input.sh --mode terminal
```

For regular GUI text fields, use:

```bash
/home/kk/AI/CODEX/voice-input-online+20260426/run-azure-voice-input.sh --mode gui
```

To print the recognized text without injecting:

```bash
/home/kk/AI/CODEX/voice-input-online+20260426/run-azure-voice-input.sh --print-only
```

By default it does not press Enter after injecting. To execute a terminal
command immediately, add:

```bash
--append-newline
```

## Desktop launchers and shortcut

Install GNOME application launchers, desktop icons, and a global shortcut:

```bash
cd /home/kk/AI/CODEX/voice-input-online+20260426
./install-shortcuts.sh
```

This installs three launchers:

```text
Azure 语音输入
Azure 语音输入（终端）
Azure 语音输入（普通输入框）
```

It also binds this GNOME shortcut:

```text
Ctrl+Alt+Space -> Azure 语音输入（终端）
Ctrl+Alt+/     -> Azure 语音输入（普通输入框）
```

The terminal mode uses `Ctrl+Shift+V` paste, which is suitable for GNOME
Terminal. The GUI mode uses `Ctrl+V`, which is suitable for browser and editor
text fields.

Tap the shortcut briefly. Repeated triggers while recognition is active are
ignored, and one recognition pass is capped at 45 seconds by default.

GNOME custom shortcuts usually do not distinguish left and right Shift. Avoid
using plain `Shift+/` because it is the normal `?` text input shortcut.

## Local quota estimate

Each successful Azure transcription records an approximate local duration in:

```text
/home/kk/AI/CODEX/voice-input-online+20260426/.state/usage.json
```

The GUI shows monthly local usage against `AZURE_SPEECH_FREE_TIER_SECONDS`
from `.env`. This is only a local estimate for this tool; it is not the Azure
official bill or quota counter.
