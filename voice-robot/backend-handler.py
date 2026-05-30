#!/usr/bin/env python3
"""
backend-handler.py — FastAPI handler /api/voice/turn для голосового бота.

Принимает от Voximplant сценария JSON:
    {chat_id, text, history, caller}

Возвращает JSON:
    {text: "...", transfer?: bool, hangup?: bool}

Логика — тот же сценарий-6-вопросов что и `qualify-leads.py`:
  - Сначала собираем 6 полей (volume, grade, address, date, urgency, payment).
  - Если триггер передачи (срочно/НДС/насос/скидки 50+/менеджер) → transfer=True.
  - Когда все поля собраны → benefactor info + завершение.

State — в SQLite (`~/.cache/voice-bot-state.sqlite`).

Запуск локально:
    uvicorn backend-handler:app --host 0.0.0.0 --port 8080

Деплой на Render — отдельный service, та же кодовая база.
"""

import json
import logging
import re
import sqlite3
import time
from pathlib import Path

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
except ImportError:
    print("FastAPI не установлен. pip install fastapi uvicorn")
    raise

DB_PATH = Path.home() / ".cache" / "voice-bot-state.sqlite"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("voice-handler")

app = FastAPI(title="Бетон42 voice bot")

# ---------- Regex (зеркало qualify-leads.py) ----------

VOLUME_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:куб|м[³3]|m3|м/куб)", re.I)
GRADE_RE = re.compile(r"\bм\s*[-]?\s*(50|75|100|150|200|250|300|350|400|450|500|550|600)\b", re.I)
ADDRESS_HINTS = re.compile(
    r"(?:г\.?\s*\w+|улица|ул\.|проспект|пр\.|переулок|пер\.|шоссе|деревня|"
    r"посёлок|пос\.|снт|кп|кемеров|топки|берёзовский|ленинск|кедровк)",
    re.I,
)
URGENCY_HIGH = re.compile(r"срочн|сейчас|сегодня|в\s+течени[ие]\s+часа|немедленн", re.I)
HANDOVER = re.compile(
    r"\bНДС\b|юр\.?\s*лиц|\bООО\b|\bИП\b|счёт[- ]?фактур|насос|бетононасос|"
    r"скидк|менеджер|живой человек|перезвоните|жалоб", re.I,
)

QUESTIONS = [
    ("volume", "Подскажите, пожалуйста, объём — сколько кубов нужно?"),
    ("grade", "Какая марка бетона? М200, М300 — самые ходовые."),
    ("address", "Скажите адрес объекта, можно даже населённый пункт."),
    ("date", "Когда планируете заливку — сегодня, завтра, на этой неделе?"),
    ("payment", "Как удобнее оплачивать — наличными водителю или картой/переводом?"),
]


# ---------- SQLite state ----------

def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS state (
        chat_id TEXT PRIMARY KEY, fields TEXT, asked TEXT, created_at INTEGER
    )""")
    return c


def get_state(chat_id: str) -> dict:
    c = db()
    row = c.execute("SELECT fields, asked FROM state WHERE chat_id=?", (chat_id,)).fetchone()
    c.close()
    if not row:
        return {"fields": {}, "asked": []}
    return {"fields": json.loads(row[0] or "{}"), "asked": json.loads(row[1] or "[]")}


def save_state(chat_id: str, state: dict) -> None:
    c = db()
    c.execute("INSERT OR REPLACE INTO state(chat_id,fields,asked,created_at) VALUES(?,?,?,?)",
              (chat_id, json.dumps(state["fields"], ensure_ascii=False),
               json.dumps(state["asked"]), int(time.time())))
    c.commit()
    c.close()


# ---------- Логика ----------

def extract(text: str) -> dict:
    out: dict = {}
    m = VOLUME_RE.search(text)
    if m:
        try:
            out["volume"] = float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    m = GRADE_RE.search(text)
    if m:
        out["grade"] = f"М{m.group(1)}"
    if ADDRESS_HINTS.search(text) and len(text) > 6:
        out["address"] = text.strip()[:200]
    if URGENCY_HIGH.search(text):
        out["urgency"] = "high"
    return out


def next_question(state: dict) -> "tuple[str, str] | None":
    for key, q in QUESTIONS:
        if key not in state["fields"] and key not in state["asked"]:
            return key, q
    return None


@app.post("/api/voice/turn")
async def voice_turn(req: Request):
    payload = await req.json()
    chat_id = payload.get("chat_id") or payload.get("call_id") or "anon"
    text = (payload.get("text") or payload.get("user_text") or "").strip()
    log.info("turn chat=%s text=%r", chat_id, text[:120])

    if HANDOVER.search(text) or URGENCY_HIGH.search(text):
        return JSONResponse({
            "text": "Передаю заявку руководителю, он перезвонит в течение 15 минут.",
            "reply": "Передаю заявку руководителю, он перезвонит в течение 15 минут.",
            "action": "transfer",
            "transfer": True,
        })

    state = get_state(chat_id)
    state["fields"].update(extract(text))

    nq = next_question(state)
    if nq is None:
        save_state(chat_id, state)
        f = state["fields"]
        summary = (f"Принял заявку: {f.get('volume', '?')} кубов "
                   f"{f.get('grade', '?')}, адрес {f.get('address', '?')[:60]}, "
                   f"оплата {f.get('payment', '?')}. "
                   f"Сейчас перезвонит менеджер с расчётом. Спасибо за обращение!")
        return JSONResponse({"text": summary, "reply": summary, "action": "end", "hangup": True})

    key, q = nq
    state["asked"].append(key)
    save_state(chat_id, state)
    return JSONResponse({"text": q, "reply": q, "action": "continue"})


@app.post("/api/voice/turn/event")
async def voice_event(req: Request):
    payload = await req.json()
    log.info("event chat=%s payload=%s", payload.get("chat_id"), str(payload)[:300])
    return JSONResponse({"ok": True})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/voice/health")
async def voice_health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
