#!/usr/bin/env python3
"""
Smoke test for Yandex SpeechKit key.

Usage after key is issued:
  python3 voice-robot/test-speechkit.py
"""

import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path("/Users/a0000/Documents/Бетон-deploy")
KEY_FILE = ROOT / "secrets" / "speechkit_api_key.txt"
OUT = ROOT / "voice-robot" / "speechkit-test.wav"


def read_key() -> str:
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    return os.environ.get("SPEECHKIT_API_KEY", "").strip()


def main() -> int:
    key = read_key()
    if not key:
        print("missing SpeechKit key")
        return 2
    data = urllib.parse.urlencode({
        "text": "Проверка голоса Бетон42. Сколько кубов бетона нужно?",
        "lang": "ru-RU",
        "voice": "alena",
        "format": "wav",
    }).encode()
    req = urllib.request.Request(
        "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize",
        data=data,
        method="POST",
        headers={"Authorization": f"Api-Key {key}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        OUT.write_bytes(r.read())
    print(f"ok: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
