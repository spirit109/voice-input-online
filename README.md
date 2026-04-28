# Voice Input Online

Voice Input Online is a small desktop voice input tool for Ubuntu GNOME
Wayland. It uses Azure Speech to transcribe one utterance from the microphone,
then inserts the recognized text into the active terminal or regular GUI text
field.

The settings app includes Azure credential setup, shortcut configuration,
conflict checks, local quota estimation, diagnostics, and a built-in setup
guide. The interface can switch between Simplified Chinese and English.

English summary: Azure Speech powered voice input for Ubuntu GNOME Wayland,
with a PySide6 settings GUI, GNOME shortcuts, terminal/text-field injection,
and local usage estimation.

## Features

- Azure Speech one-shot recognition from the default microphone.
- Text injection for GNOME Terminal, browsers, editors, and other text fields.
- PySide6 GUI for credentials, language, shortcuts, quota estimate, diagnostics,
  and Azure setup guidance.
- Shortcut capture and GNOME conflict detection before saving.
- Strict UI language switch: Simplified Chinese or English.
- Local usage estimate stored under `.state/`, separate from Azure billing.
- Secret-safe default layout: `.env` is ignored by git; `.env.example` only
  contains placeholders.

## Platform Status

Current implementation targets Ubuntu GNOME on Wayland. The injection layer
uses `ydotool` through `/dev/uinput`, because `xdotool` is not reliable for
native Wayland apps.

Windows, WSL, macOS, KDE, and X11 are not the primary supported targets yet.
The Azure recognition layer is portable Python, but text injection and global
shortcut installation need platform-specific adapters.

## Quick Start

Install system packages on Ubuntu:

```bash
sudo apt install python3-venv ydotool wl-clipboard
```

Clone and install Python dependencies:

```bash
git clone https://github.com/spirit109/voice-input-online.git
cd voice-input-online
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Create local configuration:

```bash
cp .env.example .env
```

Open the settings app:

```bash
./run-gui.sh
```

Fill in the Azure Speech key and region in the GUI, then use the diagnostics
page to test recognition and injection.

## Azure Speech Setup

Create an Azure AI Speech resource in the Azure portal, then copy one key and
the resource region into the app.
For a Chinese step-by-step note, see [docs/azure-setup.zh-CN.md](docs/azure-setup.zh-CN.md).

Minimal `.env` example:

```bash
AZURE_SPEECH_KEY=replace-with-your-azure-speech-key
AZURE_SPEECH_REGION=eastasia
AZURE_SPEECH_LANGUAGE=zh-CN
```

Do not commit your real `.env`. The repository ignores it by default.

## Text Injection

Recognize one utterance and insert it into GNOME Terminal:

```bash
./run-azure-voice-input.sh --mode terminal
```

Recognize and insert into a normal GUI text field:

```bash
./run-azure-voice-input.sh --mode gui
```

Print the recognized text without inserting it:

```bash
./run-azure-voice-input.sh --print-only
```

Pipe text directly into the injection layer:

```bash
printf 'hello world' | ./inject-text.sh --mode gui
```

Modes:

- `terminal`: copy to Wayland clipboard, then press `Ctrl+Shift+V`.
- `gui`: copy to Wayland clipboard, then press `Ctrl+V`.
- `type`: type through `ydotool`; slower, but avoids clipboard.

By default the tool does not press Enter after injection. To execute a terminal
command immediately, add `--append-newline`.

## Desktop Launchers And Shortcuts

Install GNOME application launchers, desktop entries, and default shortcuts:

```bash
./install-shortcuts.sh
```

Default shortcuts:

```text
Ctrl+Alt+Space -> terminal mode
Ctrl+Alt+/     -> GUI text-field mode
```

The installer renders `.desktop` files from `packaging/linux/*.desktop.in` with
the current clone path, so users can clone the repository anywhere.

In the GUI shortcut page, click a shortcut field and press the desired key
combination. The app checks existing GNOME system/custom shortcuts and shows
alternative suggestions when a conflict is found.

GNOME custom shortcuts usually do not distinguish left and right Shift. Avoid
plain `Shift+/`, because it is also the normal `?` text input shortcut.

## Quota Estimate

Each successful transcription records an approximate local duration in:

```text
.state/usage.json
```

The GUI shows monthly local usage against `AZURE_SPEECH_FREE_TIER_SECONDS`
from `.env`. This is only a local estimate for this tool; it is not the Azure
official bill or quota counter.

## Project Structure

```text
.
├── azure_voice_input.py          # Azure Speech recognition CLI
├── voice_input_gui.py            # PySide6 settings GUI
├── voice_config.py               # .env parsing and writing
├── voice_i18n.py                 # Chinese/English UI strings
├── voice_usage.py                # Local usage estimate
├── inject-text.sh                # Wayland text injection helper
├── voice-input-once.sh           # Shortcut-friendly one-shot wrapper
├── run-azure-voice-input.sh      # Loads .env and runs recognition
├── run-gui.sh                    # Starts the settings GUI
├── install-shortcuts.sh          # Installs GNOME launchers and shortcuts
├── packaging/linux/*.desktop.in  # Desktop entry templates
├── requirements.txt              # Python dependencies
└── .env.example                  # Safe configuration template
```

## Development Checks

```bash
.venv/bin/python -m py_compile azure_voice_input.py voice_config.py voice_i18n.py voice_input_gui.py voice_usage.py
bash -n inject-text.sh install-shortcuts.sh run-azure-voice-input.sh run-gui.sh voice-input-once.sh
```

If `desktop-file-validate` is installed, validate rendered desktop templates:

```bash
mkdir -p .state/desktop-validate
for file in packaging/linux/*.desktop.in; do
  out=".state/desktop-validate/$(basename "${file%.in}")"
  sed "s|@PROJECT_DIR@|$PWD|g" "$file" > "$out"
  desktop-file-validate "$out"
done
```

## Security

- Keep real Azure keys in `.env` only.
- `.env`, `.venv/`, `.state/`, and Python cache files are ignored by git.
- Rotate the Azure key immediately if it is ever committed or pasted into an
  issue, log, screenshot, or chat transcript.

## License

MIT License. See [LICENSE](LICENSE).
