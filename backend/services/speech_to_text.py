"""Short voice-message transcription through Russian SaluteSpeech."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid

import httpx

logger = logging.getLogger(__name__)

_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_RECOGNIZE_URL = "https://smartspeech.sber.ru/rest/v1/speech:recognize"
_MAX_AUDIO_BYTES = 2 * 1024 * 1024
_token: str | None = None
_token_expires_at = 0.0
_token_lock = asyncio.Lock()


class TranscriptionError(RuntimeError):
    """The voice message could not be transcribed safely."""


def is_configured() -> bool:
    return bool(os.getenv("SALUTE_AUTH_KEY") or os.getenv("SALUTE_TOKEN"))


async def _access_token(*, force_refresh: bool = False) -> str:
    global _token, _token_expires_at
    async with _token_lock:
        if not force_refresh and _token and time.time() < _token_expires_at - 60:
            return _token

        auth_key = os.getenv("SALUTE_AUTH_KEY") or os.getenv("SALUTE_TOKEN")
        if not auth_key:
            raise TranscriptionError("SaluteSpeech is not configured")

        headers = {
            "Authorization": f"Basic {auth_key}",
            "RqUID": str(uuid.uuid4()),
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                _OAUTH_URL,
                headers=headers,
                data={"scope": os.getenv("SALUTE_SCOPE", "SALUTE_SPEECH_PERS")},
            )
        if response.status_code != 200:
            raise TranscriptionError(f"SaluteSpeech authorization failed ({response.status_code})")

        payload = response.json()
        _token = payload.get("access_token")
        if not _token:
            raise TranscriptionError("SaluteSpeech returned no access token")
        _token_expires_at = (payload.get("expires_at", 0) / 1000) or (time.time() + 1500)
        return _token


def _parse_result(payload: dict) -> str:
    result = payload.get("result", [])
    if not isinstance(result, list):
        return str(result or "").strip()
    parts = []
    for item in result:
        if isinstance(item, dict):
            parts.append(str(item.get("normalized_text") or item.get("text") or ""))
        else:
            parts.append(str(item))
    return " ".join(part for part in parts if part).strip()


async def transcribe_ogg(audio: bytes) -> str:
    """Transcribe one Ogg/Opus message without persisting the audio."""
    if not audio or len(audio) > _MAX_AUDIO_BYTES:
        raise TranscriptionError("Voice message must be shorter than one minute and 2 MB")

    for attempt in range(2):
        token = await _access_token(force_refresh=attempt == 1)
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                _RECOGNIZE_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "audio/ogg;codecs=opus",
                },
                content=audio,
            )
        if response.status_code == 401 and attempt == 0:
            continue
        if response.status_code != 200:
            raise TranscriptionError(f"SaluteSpeech recognition failed ({response.status_code})")
        text = _parse_result(response.json())
        if not text:
            raise TranscriptionError("No speech recognized")
        return text
    raise TranscriptionError("SaluteSpeech authorization expired")
