#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from voice_config import DEFAULTS, PROJECT_DIR, parse_env


STATE_DIR = PROJECT_DIR / ".state"
USAGE_PATH = STATE_DIR / "usage.json"


def _month_key(moment: dt.datetime | None = None) -> str:
    moment = moment or dt.datetime.now()
    return moment.strftime("%Y-%m")


def load_usage(path: Path = USAGE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"records": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"records": []}
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        return {"records": []}
    return data


def save_usage(data: dict[str, Any], path: Path = USAGE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def record_usage(
    seconds: float,
    *,
    language: str,
    mode: str,
    transcript_chars: int,
    path: Path = USAGE_PATH,
) -> None:
    seconds = max(0.0, float(seconds))
    data = load_usage(path)
    data["records"].append(
        {
            "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            "month": _month_key(),
            "seconds": round(seconds, 3),
            "language": language,
            "mode": mode,
            "transcript_chars": int(transcript_chars),
        }
    )
    save_usage(data, path)


def monthly_summary(month: str | None = None, path: Path = USAGE_PATH) -> dict[str, Any]:
    month = month or _month_key()
    records = [
        record
        for record in load_usage(path).get("records", [])
        if record.get("month") == month
    ]
    used_seconds = sum(float(record.get("seconds", 0)) for record in records)
    env = parse_env()
    free_seconds = float(
        env.get("AZURE_SPEECH_FREE_TIER_SECONDS")
        or DEFAULTS["AZURE_SPEECH_FREE_TIER_SECONDS"]
    )
    remaining_seconds = max(0.0, free_seconds - used_seconds)
    percent = 0.0 if free_seconds <= 0 else min(100.0, used_seconds / free_seconds * 100.0)
    return {
        "month": month,
        "records": len(records),
        "used_seconds": used_seconds,
        "free_seconds": free_seconds,
        "remaining_seconds": remaining_seconds,
        "percent": percent,
        "path": str(path),
    }


def format_minutes(seconds: float) -> str:
    minutes = seconds / 60
    return f"{minutes:.1f} 分钟"
