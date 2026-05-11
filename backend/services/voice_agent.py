"""Voice sales agent orchestration."""

from __future__ import annotations

from datetime import datetime
import uuid
from typing import Any

from config import settings
from services.sales_dialogue import SalesDialogueEngine
from services.stt import SpeechToTextService
from services.tts import TextToSpeechService


class VoiceAgentService:
    def __init__(self, calculator, storage):
        self.calculator = calculator
        self.storage = storage
        self.dialogue = SalesDialogueEngine()
        self.stt = SpeechToTextService()
        self.tts = TextToSpeechService()
        self.sessions: dict[str, dict[str, Any]] = {}

    async def start_call(
        self,
        *,
        phone: str,
        provider: str = "telephony",
        direction: str = "inbound",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        call_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        response_text = self.dialogue.opening_message()
        session = {
            "call_id": call_id,
            "phone": phone,
            "provider": provider,
            "direction": direction,
            "status": "active",
            "stage": "qualification",
            "metadata": metadata or {},
            "collected_data": {},
            "sales_context": {
                "funnel_stage": "qualification",
                "objections": [],
                "close_attempts": 0,
            },
            "transcript": [
                {"role": "assistant", "text": response_text, "timestamp": now},
            ],
            "lead_result": None,
            "handoff_required": False,
            "handoff_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        self.sessions[call_id] = session
        await self.storage.log_error(
            "voice_call_start",
            "",
            {
                "call_id": call_id,
                "phone": phone,
                "provider": provider,
                "direction": direction,
            },
        )
        return self._compose_response(session, response_text)

    async def process_turn(
        self,
        call_id: str,
        *,
        text: str | None = None,
        transcript: str | None = None,
        provider_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        session = self.sessions.get(call_id)
        if not session:
            return None

        user_text = self.stt.resolve_text(text=text, transcript=transcript, provider_payload=provider_payload)
        now = datetime.now().isoformat()
        if user_text:
            session["transcript"].append({"role": "user", "text": user_text, "timestamp": now})

        result = self.dialogue.process_turn(session, user_text)

        if result.get("action") == "ready_for_quote":
            collected = session["collected_data"]
            calculation = self.calculator.calculate(
                collected["concrete_grade"],
                float(collected["volume"]),
                float(collected["distance"]),
            )
            session["quote"] = calculation
            session["stage"] = "quote_confirmation"
            session["sales_context"]["funnel_stage"] = "offer"
            response_text = self.dialogue.build_quote_message(collected, calculation)
        else:
            response_text = result["response_text"]

        if result.get("action") == "handoff":
            session["handoff_required"] = True
            session["handoff_reason"] = result.get("handoff_reason") or "manual_review"
            session["status"] = "handoff"
            session["sales_context"]["funnel_stage"] = "handoff"
        elif result.get("action") == "create_lead":
            session["status"] = "pending_lead_creation"
            session["sales_context"]["funnel_stage"] = "closing"

        session["updated_at"] = now
        session["transcript"].append({"role": "assistant", "text": response_text, "timestamp": now})

        await self.storage.log_error(
            "voice_call_turn",
            "",
            {
                "call_id": call_id,
                "status": session["status"],
                "stage": session["stage"],
                "funnel_stage": session["sales_context"].get("funnel_stage"),
                "user_text": user_text,
                "action": result.get("action"),
            },
        )

        result["response_text"] = response_text
        return {
            "session": session,
            "result": result,
            "tts": self.tts.render(response_text),
        }

    async def mark_lead_created(self, call_id: str, lead_result: dict[str, Any]):
        session = self.sessions.get(call_id)
        if not session:
            return

        session["lead_result"] = lead_result
        session["status"] = "completed"
        session["stage"] = "completed"
        session["sales_context"]["funnel_stage"] = "completed"
        session["updated_at"] = datetime.now().isoformat()

        await self.storage.log_error(
            "voice_call_complete",
            "",
            {
                "call_id": call_id,
                "lead_result": lead_result,
                "quote": session.get("quote"),
            },
        )

    async def handoff_call(self, call_id: str, reason: str = "manual_review") -> dict[str, Any] | None:
        session = self.sessions.get(call_id)
        if not session:
            return None

        session["handoff_required"] = True
        session["handoff_reason"] = reason
        session["status"] = "handoff"
        session["sales_context"]["funnel_stage"] = "handoff"
        session["updated_at"] = datetime.now().isoformat()

        response_text = settings.VOICE_HANDOFF_MESSAGE
        session["transcript"].append(
            {"role": "assistant", "text": response_text, "timestamp": session["updated_at"]}
        )

        await self.storage.log_error(
            "voice_call_handoff",
            "",
            {"call_id": call_id, "reason": reason, "phone": session.get("phone")},
        )
        return self._compose_response(session, response_text)

    def get_session(self, call_id: str) -> dict[str, Any] | None:
        return self.sessions.get(call_id)

    def list_sessions(self, limit: int = 20, status: str | None = None) -> list[dict[str, Any]]:
        sessions = list(self.sessions.values())
        sessions.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        if status:
            sessions = [item for item in sessions if item.get("status") == status]
        return sessions[:limit]

    def build_lead_payload(self, call_id: str) -> dict[str, Any] | None:
        session = self.sessions.get(call_id)
        if not session:
            return None

        collected = session.get("collected_data", {})
        quote = session.get("quote", {})
        if not collected:
            return None

        transcript_text = "\n".join(f"{turn['role']}: {turn['text']}" for turn in session.get("transcript", []))[:3500]
        objections = ", ".join(session.get("sales_context", {}).get("objections", [])) or "none"

        return {
            "name": collected.get("name") or "Телефонный лид",
            "phone": session.get("phone"),
            "source": "voice-bot",
            "source_platform": "phone",
            "source_channel": "call",
            "source_account": session.get("provider") or "telephony",
            "source_listing": session.get("metadata", {}).get("line_name") or "voice-agent",
            "source_campaign": session.get("metadata", {}).get("campaign"),
            "concrete_grade": collected.get("concrete_grade"),
            "volume": collected.get("volume"),
            "address": collected.get("address"),
            "delivery_date": collected.get("delivery_date"),
            "payment_method": collected.get("payment_method"),
            "urgency": collected.get("urgency"),
            "distance": collected.get("distance"),
            "calculated_amount": quote.get("total"),
            "client_type": "private",
            "comment": (
                "Лид квалифицирован голосовым менеджером.\n"
                f"Сессия: {call_id}\n"
                "Playbook: voice_inbound_close\n"
                f"Funnel stage: {session.get('sales_context', {}).get('funnel_stage')}\n"
                f"Urgency: {collected.get('urgency')}\n"
                f"Objections: {objections}\n\n"
                f"Транскрипт:\n{transcript_text}"
            ),
        }

    def _compose_response(self, session: dict[str, Any], response_text: str) -> dict[str, Any]:
        return {
            "status": "success",
            "call": session,
            "assistant": {
                "text": response_text,
                "tts": self.tts.render(response_text),
            },
        }
