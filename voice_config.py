#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from voice_i18n import DEFAULT_LANGUAGE, tr


PROJECT_DIR = Path(__file__).resolve().parent
ENV_PATH = PROJECT_DIR / ".env"

CONFIG_KEYS = [
    "AZURE_SPEECH_KEY",
    "AZURE_SPEECH_REGION",
    "AZURE_SPEECH_ENDPOINT",
    "AZURE_SPEECH_LANGUAGE",
    "AZURE_SPEECH_INITIAL_SILENCE_MS",
    "AZURE_SPEECH_END_SILENCE_MS",
    "AZURE_SPEECH_FREE_TIER_SECONDS",
    "VOICE_INPUT_MAX_SECONDS",
    "VOICE_INPUT_UI_LANGUAGE",
    "VOICE_INPUT_TERMINAL_SHORTCUT",
    "VOICE_INPUT_GUI_SHORTCUT",
]

DEFAULTS = {
    "AZURE_SPEECH_LANGUAGE": "zh-CN",
    "AZURE_SPEECH_END_SILENCE_MS": "700",
    "AZURE_SPEECH_FREE_TIER_SECONDS": "18000",
    "VOICE_INPUT_MAX_SECONDS": "45",
    "VOICE_INPUT_UI_LANGUAGE": DEFAULT_LANGUAGE,
    "VOICE_INPUT_TERMINAL_SHORTCUT": "<Control><Alt>space",
    "VOICE_INPUT_GUI_SHORTCUT": "<Control><Alt>slash",
}


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_env(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return dict(DEFAULTS)

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        values[key] = _unquote(value)

    merged = dict(DEFAULTS)
    merged.update(values)
    return merged


def _quote(value: str) -> str:
    if not value:
        return ""
    shell_specials = "'\"#<>;&|()$`*?[]{}!\\"
    if any(char.isspace() for char in value) or any(char in value for char in shell_specials):
        return "'" + value.replace("'", "'\"'\"'") + "'"
    return value


def write_env(updates: dict[str, str], path: Path = ENV_PATH) -> None:
    current = parse_env(path)
    current.update({key: value.strip() for key, value in updates.items()})

    lines = [
        "# Azure Speech credentials",
        f"AZURE_SPEECH_KEY={_quote(current.get('AZURE_SPEECH_KEY', ''))}",
        f"AZURE_SPEECH_REGION={_quote(current.get('AZURE_SPEECH_REGION', ''))}",
        f"AZURE_SPEECH_ENDPOINT={_quote(current.get('AZURE_SPEECH_ENDPOINT', ''))}",
        f"AZURE_SPEECH_LANGUAGE={_quote(current.get('AZURE_SPEECH_LANGUAGE', DEFAULTS['AZURE_SPEECH_LANGUAGE']))}",
        "",
        "# Recognition tuning",
        f"AZURE_SPEECH_INITIAL_SILENCE_MS={_quote(current.get('AZURE_SPEECH_INITIAL_SILENCE_MS', ''))}",
        f"AZURE_SPEECH_END_SILENCE_MS={_quote(current.get('AZURE_SPEECH_END_SILENCE_MS', DEFAULTS['AZURE_SPEECH_END_SILENCE_MS']))}",
        f"VOICE_INPUT_MAX_SECONDS={_quote(current.get('VOICE_INPUT_MAX_SECONDS', DEFAULTS['VOICE_INPUT_MAX_SECONDS']))}",
        "",
        "# Interface language: zh-CN or en-US",
        f"VOICE_INPUT_UI_LANGUAGE={_quote(current.get('VOICE_INPUT_UI_LANGUAGE', DEFAULTS['VOICE_INPUT_UI_LANGUAGE']))}",
        "",
        "# Local quota estimate",
        f"AZURE_SPEECH_FREE_TIER_SECONDS={_quote(current.get('AZURE_SPEECH_FREE_TIER_SECONDS', DEFAULTS['AZURE_SPEECH_FREE_TIER_SECONDS']))}",
        "",
        "# GNOME shortcuts",
        f"VOICE_INPUT_TERMINAL_SHORTCUT={_quote(current.get('VOICE_INPUT_TERMINAL_SHORTCUT', DEFAULTS['VOICE_INPUT_TERMINAL_SHORTCUT']))}",
        f"VOICE_INPUT_GUI_SHORTCUT={_quote(current.get('VOICE_INPUT_GUI_SHORTCUT', DEFAULTS['VOICE_INPUT_GUI_SHORTCUT']))}",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


def masked_secret(value: str) -> str:
    if not value:
        return tr("not_configured", parse_env().get("VOICE_INPUT_UI_LANGUAGE"))
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"
