#!/usr/bin/env python3
"""
backend-maria.py — FastAPI wrapper для Марии (Claude AI консультант).

Endpoint: POST /api/voice/maria
Получает: {chat_id, text, history, caller}
Возвращает: {text, transfer_needed, transfer_phone, ...}

Деплой на Render:
    pip install fastapi uvicorn anthropic requests
    uvicorn backend-maria:app --host 0.0.0.0 --port 8080
"""

import json
import logging
import os
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
import requests

# Импортируем Марию
import sys
sys.path.insert(0, str(Path(__file__).parent))
from maria_integration import MariaBotHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("maria-backend")

app = FastAPI(title="Бетон42 Maria voice bot")

# Кэш обработчиков по chat_id (в памяти для простоты)
HANDLERS = {}
SESSIONS = {}

AMOCRM_BASE_URL = os.getenv("AMOCRM_BASE_URL", "https://shef1664.amocrm.ru").rstrip("/")
AMOCRM_ACCESS_TOKEN = os.getenv("AMOCRM_ACCESS_TOKEN", "")
AMOCRM_PHONE_FIELD_ID = int(os.getenv("AMOCRM_PHONE_FIELD_ID", "1503041"))
AMOCRM_PIPELINE_ID = int(os.getenv("AMOCRM_PIPELINE_ID", "10818570"))
AMOCRM_NEW_STATUS_ID = int(os.getenv("AMOCRM_NEW_STATUS_ID", "85162970"))
AMOCRM_TRANSFER_STATUS_ID = os.getenv("AMOCRM_TRANSFER_STATUS_ID", "85162982")
VOICE_TAG = "voice-bot-635588"
TRANSFER_TAG = "требует-менеджера"
MANAGER_PHONE = "8 903 916 40 40"
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")


def normalize_phone(phone: str) -> str:
    """Return phone in +7XXXXXXXXXX form when possible."""
    digits = re.sub(r"\D+", "", phone or "")
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    return f"+{digits}" if digits else phone or ""


def amo_headers():
    if not AMOCRM_ACCESS_TOKEN:
        raise RuntimeError("AMOCRM_ACCESS_TOKEN is not configured")
    return {
        "Authorization": f"Bearer {AMOCRM_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def amo_request(method: str, path: str, **kwargs):
    url = f"{AMOCRM_BASE_URL}{path}"
    response = requests.request(method, url, headers=amo_headers(), timeout=20, **kwargs)
    response.raise_for_status()
    if response.content:
        return response.json()
    return {}


def find_or_create_contact(caller: str) -> Optional[int]:
    phone = normalize_phone(caller)
    if not phone:
        return None

    data = amo_request("GET", "/api/v4/contacts", params={"filter[phone]": phone})
    contacts = data.get("_embedded", {}).get("contacts", [])
    if contacts:
        return contacts[0]["id"]

    payload = [
        {
            "name": phone,
            "custom_fields_values": [
                {
                    "field_id": AMOCRM_PHONE_FIELD_ID,
                    "values": [{"value": phone}],
                }
            ],
        }
    ]
    created = amo_request("POST", "/api/v4/contacts", json=payload)
    contacts = created.get("_embedded", {}).get("contacts", [])
    return contacts[0]["id"] if contacts else None


def create_lead(contact_id: Optional[int], caller: str) -> Optional[int]:
    phone = normalize_phone(caller)
    payload = [
        {
            "name": f"Звонок 635588 {phone or caller or 'без номера'}",
            "pipeline_id": AMOCRM_PIPELINE_ID,
            "status_id": AMOCRM_NEW_STATUS_ID,
            "_embedded": {
                "tags": [{"name": VOICE_TAG}],
            },
        }
    ]
    if contact_id:
        payload[0]["_embedded"]["contacts"] = [{"id": contact_id}]

    created = amo_request("POST", "/api/v4/leads", json=payload)
    leads = created.get("_embedded", {}).get("leads", [])
    return leads[0]["id"] if leads else None


def add_lead_note(lead_id: int, text: str):
    payload = [
        {
            "entity_id": lead_id,
            "note_type": "common",
            "params": {"text": text},
        }
    ]
    amo_request("POST", f"/api/v4/leads/{lead_id}/notes", json=payload)


def mark_transfer_needed(lead_id: int):
    payload = {
        "_embedded": {
            "tags": [
                {"name": VOICE_TAG},
                {"name": TRANSFER_TAG},
            ]
        }
    }
    if AMOCRM_TRANSFER_STATUS_ID:
        payload["status_id"] = int(AMOCRM_TRANSFER_STATUS_ID)
    amo_request("PATCH", f"/api/v4/leads/{lead_id}", json=payload)


def log_to_amocrm(chat_id, caller, client_text, response_text, action, transfer_needed):
    """Log one Maria dialog turn to AmoCRM. Errors are logged, not raised."""
    if not AMOCRM_ACCESS_TOKEN:
        log.warning("AmoCRM logging skipped: AMOCRM_ACCESS_TOKEN is not configured")
        return None

    try:
        session = SESSIONS.setdefault(chat_id, {})
        if "lead_id" not in session:
            contact_id = find_or_create_contact(caller)
            lead_id = create_lead(contact_id, caller)
            session["contact_id"] = contact_id
            session["lead_id"] = lead_id
            log.info("AmoCRM lead created: chat_id=%s lead_id=%s", chat_id, lead_id)

        lead_id = session.get("lead_id")
        if not lead_id:
            log.warning("AmoCRM logging skipped: no lead_id for chat_id=%s", chat_id)
            return None

        timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        note = (
            f"[635588] {timestamp}\n"
            f"Клиент {normalize_phone(caller)}: {client_text or '(тишина)'}\n"
            f"Мария: {response_text}\n"
            f"Действие: {action}"
        )
        add_lead_note(lead_id, note)

        if transfer_needed:
            mark_transfer_needed(lead_id)
            log.info("AmoCRM lead marked transfer: chat_id=%s lead_id=%s", chat_id, lead_id)

        return lead_id
    except Exception as exc:
        log.error("AmoCRM logging failed: chat_id=%s error=%s", chat_id, exc, exc_info=True)
        return None


@app.post("/api/voice/maria")
async def handle_voice_turn(request: Request):
    """
    Обрабатывает один ход разговора.

    Request:
        {
            "chat_id": "caller-timestamp",
            "text": "Привет, сколько стоит бетон?",
            "history": [...],
            "caller": "+7-913-120-0300"
        }

    Response:
        {
            "text": "Ответ Марии",
            "transfer_needed": false,
            "transfer_phone": "8 903 916 40 40",
            "action": "continue" | "transfer" | "hangup"
        }
    """
    try:
        data = await request.json()
        chat_id = data.get("chat_id")
        client_text = data.get("text", "").strip()
        caller = data.get("caller", "")

        log.info(f"chat_id={chat_id}, caller={caller}, text={client_text[:50]}")

        # Получаем или создаём обработчик для этой сессии
        if chat_id not in HANDLERS:
            HANDLERS[chat_id] = MariaBotHandler()
            log.info(f"Создана новая сессия: {chat_id}")

        handler = HANDLERS[chat_id]

        # Обрабатываем сообщение
        result = handler.process_client_message(client_text)

        # Формируем ответ
        response = {
            "text": result["text"],
            "transfer_needed": result["transfer_needed"],
            "transfer_phone": result["transfer_phone"],
            "action": "transfer" if result["transfer_needed"] else "continue",
        }

        lead_id = log_to_amocrm(
            chat_id=chat_id,
            caller=caller,
            client_text=client_text,
            response_text=response["text"],
            action=response["action"],
            transfer_needed=response["transfer_needed"],
        )
        if lead_id:
            response["amocrm_lead_id"] = lead_id

        log.info(
            "chat_id=%s, caller=%s, action=%s, text=%r",
            chat_id,
            caller,
            response["action"],
            response["text"][:120],
        )

        return JSONResponse(response)

    except Exception as e:
        log.error(f"Error: {e}", exc_info=True)
        return JSONResponse({
            "text": "Извините, произошла ошибка. Передаю менеджеру.",
            "transfer_needed": True,
            "transfer_phone": MANAGER_PHONE,
            "action": "transfer",
            "error": str(e)
        }, status_code=500)


@app.post("/api/voice/event")
async def handle_event(request: Request):
    """
    Обработчик событий от Voximplant (конец звонка, ошибки).
    """
    try:
        data = await request.json()
        event = data.get("event")
        chat_id = data.get("chat_id")

        log.info(f"Event: {event}, chat_id={chat_id}")

        if event == "call_end" and chat_id in HANDLERS:
            # Очищаем сессию
            del HANDLERS[chat_id]
            SESSIONS.pop(chat_id, None)
            log.info(f"Сессия закрыта: {chat_id}")

        if event == "transfer_to_manager":
            session = SESSIONS.get(chat_id, {})
            lead_id = session.get("lead_id")
            if lead_id:
                add_lead_note(
                    lead_id,
                    f"[635588] Передача менеджеру: {data.get('manager_phone') or MANAGER_PHONE}",
                )
                mark_transfer_needed(lead_id)

        return JSONResponse({"ok": True})

    except Exception as e:
        log.error(f"Event handler error: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/voice/tts")
async def handle_tts(request: Request):
    """
    TTS proxy for the Asterisk AGI bridge.

    The Selectel VPS can be blocked by ElevenLabs geofencing, while Render can
    call ElevenLabs from Frankfurt. The AGI downloads the MP3 and converts it to
    Asterisk WAV locally before playback.
    """
    try:
        if not ELEVENLABS_API_KEY:
            return JSONResponse({"error": "ELEVENLABS_API_KEY is not configured"}, status_code=503)

        data = await request.json()
        text = (data.get("text") or "").strip()
        if not text:
            return JSONResponse({"error": "text is required"}, status_code=400)
        if len(text) > 1200:
            text = text[:1200]

        voice_id = data.get("voice_id") or ELEVENLABS_VOICE_ID
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY,
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.55,
                "similarity_boost": 0.75,
                "style": 0.10,
                "use_speaker_boost": True,
            },
        }
        response = requests.post(url, headers=headers, json=payload, timeout=35)
        response.raise_for_status()
        return Response(content=response.content, media_type="audio/mpeg")
    except Exception as e:
        log.error(f"TTS proxy error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/health")
async def health():
    """Проверка здоровья."""
    return {"status": "ok", "service": "maria-voice-bot"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
