#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import azure.cognitiveservices.speech as speechsdk
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: azure-cognitiveservices-speech. "
        "Run: python3 -m pip install -r requirements.txt"
    ) from exc

from voice_usage import record_usage


PROJECT_DIR = Path(__file__).resolve().parent
INJECT_SCRIPT = PROJECT_DIR / "inject-text.sh"


def env_first(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recognize one utterance with Azure Speech and inject it into the active input."
    )
    parser.add_argument(
        "--language",
        default=os.environ.get("AZURE_SPEECH_LANGUAGE", "zh-CN"),
        help="Azure recognition language, for example zh-CN or en-US. Default: zh-CN",
    )
    parser.add_argument(
        "--mode",
        default="terminal",
        choices=["terminal", "gui", "type"],
        help="Injection mode passed to inject-text.sh. Default: terminal",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print recognized text and skip injection.",
    )
    parser.add_argument(
        "--append-newline",
        action="store_true",
        help="Append a newline before injection. Use only when you want terminal commands to execute.",
    )
    parser.add_argument(
        "--delay-ms",
        default="120",
        help="Delay before paste/type in milliseconds. Default: 120",
    )
    parser.add_argument(
        "--initial-silence-ms",
        default=os.environ.get("AZURE_SPEECH_INITIAL_SILENCE_MS"),
        help="Optional initial silence timeout in milliseconds.",
    )
    parser.add_argument(
        "--end-silence-ms",
        default=os.environ.get("AZURE_SPEECH_END_SILENCE_MS"),
        help="Optional end silence timeout in milliseconds.",
    )
    return parser


def make_speech_config(args: argparse.Namespace):
    key = env_first("AZURE_SPEECH_KEY", "SPEECH_KEY")
    endpoint = env_first("AZURE_SPEECH_ENDPOINT", "SPEECH_ENDPOINT", "ENDPOINT")
    region = env_first("AZURE_SPEECH_REGION", "SPEECH_REGION")

    if not key:
        raise SystemExit(
            "Set AZURE_SPEECH_KEY or SPEECH_KEY before running this script."
        )

    if endpoint:
        speech_config = speechsdk.SpeechConfig(subscription=key, endpoint=endpoint)
    elif region:
        speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    else:
        raise SystemExit(
            "Set AZURE_SPEECH_REGION/SPEECH_REGION or AZURE_SPEECH_ENDPOINT/SPEECH_ENDPOINT."
        )

    speech_config.speech_recognition_language = args.language

    if args.initial_silence_ms:
        speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs,
            str(args.initial_silence_ms),
        )

    if args.end_silence_ms:
        speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs,
            str(args.end_silence_ms),
        )

    return speech_config


def recognize_once(args: argparse.Namespace) -> str:
    speech_config = make_speech_config(args)
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    print("Speak now. Recognition returns after silence or about 30 seconds.", file=sys.stderr)
    result = recognizer.recognize_once_async().get()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text.strip()

    if result.reason == speechsdk.ResultReason.NoMatch:
        details = result.no_match_details
        reason = details.reason if details else "unknown"
        raise SystemExit(f"No speech recognized: {reason}")

    if result.reason == speechsdk.ResultReason.Canceled:
        details = result.cancellation_details
        if not details:
            raise SystemExit("Azure recognition canceled without details.")
        message = f"Azure recognition canceled: {details.reason}"
        message += f"\nError code: {details.code}"
        if details.error_details:
            message += f"\nError details: {details.error_details}"
        raise SystemExit(message)

    raise SystemExit(f"Unexpected Azure result reason: {result.reason}")


def inject_text(text: str, args: argparse.Namespace) -> None:
    if args.append_newline:
        text += "\n"

    command = [
        str(INJECT_SCRIPT),
        "--mode",
        args.mode,
        "--delay-ms",
        str(args.delay_ms),
    ]
    subprocess.run(command, input=text, text=True, check=True)


def main() -> int:
    args = build_parser().parse_args()
    started_at = time.monotonic()
    transcript = recognize_once(args)
    elapsed_seconds = time.monotonic() - started_at

    if not transcript:
        print("Azure returned empty text.", file=sys.stderr)
        return 1

    record_usage(
        elapsed_seconds,
        language=args.language,
        mode="print-only" if args.print_only else args.mode,
        transcript_chars=len(transcript),
    )

    print(transcript)

    if not args.print_only:
        inject_text(transcript, args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
