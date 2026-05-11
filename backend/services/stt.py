"""Speech-to-text abstraction for voice sales flows."""

from __future__ import annotations

from typing import Any

from config import settings


class SpeechToTextService:
    """Provider-neutral STT wrapper.

    MVP mode accepts already recognized text from telephony/webhook payloads.
    """

    def __init__(self):
        self.provider = settings.VOICE_STT_PROVIDER

    def resolve_text(
        self,
        *,
        text: str | None = None,
        transcript: str | None = None,
        provider_payload: dict[str, Any] | None = None,
    ) -> str:
        payload = provider_payload or {}
        for candidate in (
            text,
            transcript,
            payload.get("text"),
            payload.get("transcript"),
            payload.get("recognized_text"),
            payload.get("result"),
            payload.get("utterance"),
            (payload.get("stt") or {}).get("text") if isinstance(payload.get("stt"), dict) else None,
        ):
            if isinstance(candidate, str) and candidate.strip():
                return " ".join(candidate.strip().split())
        return ""
