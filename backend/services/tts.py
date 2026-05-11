"""Text-to-speech abstraction for voice sales flows."""

from __future__ import annotations

from config import settings


class TextToSpeechService:
    """Provider-neutral TTS wrapper.

    MVP mode returns metadata that telephony layer can map to a real TTS provider.
    """

    def __init__(self):
        self.provider = settings.VOICE_TTS_PROVIDER
        self.voice_name = settings.VOICE_FEMALE_VOICE

    def render(self, text: str) -> dict:
        return {
            "provider": self.provider,
            "voice": self.voice_name,
            "text": text,
            "style": "conversational_sales",
            "pace": "medium",
            "emotion": "calm_confident",
        }
