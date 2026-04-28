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
