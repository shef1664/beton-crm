"""
Клиентский AI-бот заказа бетона для мессенджера МАКС (max.ru), встроен в backend.

МАКС Bot API — наследник TamTam Bot API: long-polling, инлайн-кнопки (callback),
кнопка request_contact для телефона. Ядро (AI, зоны, цены, лид) переиспользуется —
адаптер дёргает те же backend-эндпоинты по localhost.

⚠️ СВЕРИТЬ на живом токене (докой из окружения не достучаться): base URL, точные
имена полей update/message, формат contact-вложения. Всё вынесено в _max_* функции —
если формат отличается, правки только там.

Env: MAX_BOT_TOKEN (обязателен), MAX_API_BASE (по умолчанию botapi.max.ru),
RUN_MAX_BOT=true чтобы включить опрос.
"""

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN", "")
# ⚠️ Сверить базовый URL Bot API МАКС. TamTam: https://botapi.tamtam.chat
MAX_API_BASE = os.getenv("MAX_API_BASE", "https://botapi.max.ru").rstrip("/")
_PORT = os.getenv("PORT", "8000")
BACKEND_URL = f"http://127.0.0.1:{_PORT}"

GRADES = ["М100", "М150", "М200", "М250", "М300", "М350", "М400", "М450"]
DATE_TO_URGENCY = {"Сегодня": "today", "Завтра": "normal", "На неделе": "normal", "Не срочно": "normal"}
AI_HISTORY_MAX = 20

# Состояния FSM per user
IDLE, VOLUME, ADDRESS, DATE, PAYMENT, PHONE = "idle", "volume", "address", "date", "payment", "phone"

_sessions: dict = {}       # user_id -> dict(state, grade, volume, address, quote, ai_history, ...)
_poll_task = None
_running = False


def _sess(uid: int) -> dict:
    return _sessions.setdefault(uid, {"state": IDLE, "ai_history": []})


# ── MAX Bot API (тонкий слой; сверить форматы) ───────────────────────────────

async def _max_get_updates(client: httpx.AsyncClient, marker):
    params = {"access_token": MAX_BOT_TOKEN, "timeout": 30, "limit": 100}
    if marker is not None:
        params["marker"] = marker
    r = await client.get(f"{MAX_API_BASE}/updates", params=params)
    r.raise_for_status()
    return r.json()


async def _max_send(client: httpx.AsyncClient, user_id: int, text: str, buttons=None):
    """Отправить сообщение пользователю. buttons — список рядов callback/request_contact."""
    body = {"text": text}
    if buttons:
        body["attachments"] = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
    try:
        await client.post(f"{MAX_API_BASE}/messages",
                          params={"access_token": MAX_BOT_TOKEN, "user_id": user_id},
                          json=body)
    except Exception as exc:
        logger.error("MAX send failed: %s", exc)


def _btn_cb(text: str, payload: str) -> dict:
    return {"type": "callback", "text": text, "payload": payload}


def _kb_grades():
    rows, row = [], []
    for g in GRADES:
        row.append(_btn_cb(g, f"grade:{g}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return rows


def _kb_main():
    return [[_btn_cb("🧮 Рассчитать и заказать", "order")],
            [_btn_cb("👤 Позвать менеджера", "human")]]


def _kb_date():
    return [[_btn_cb("Сегодня", "date:Сегодня"), _btn_cb("Завтра", "date:Завтра")],
            [_btn_cb("На неделе", "date:На неделе"), _btn_cb("Не срочно", "date:Не срочно")]]


def _kb_pay():
    return [[_btn_cb("Наличные", "pay:Наличные")],
            [_btn_cb("Безналичный расчёт", "pay:Безналичный расчёт")],
            [_btn_cb("Перевод на карту", "pay:Перевод на карту")]]


def _kb_phone():
    # ⚠️ Сверить: тип кнопки запроса контакта в МАКС (TamTam: "request_contact").
    return [[{"type": "request_contact", "text": "📱 Отправить мой номер"}]]


def _rub(n):
    return f"{int(n):,} ₽".replace(",", " ")


def _range(a, b):
    return _rub(a) if a == b else f"{_rub(a)}–{_rub(b)}"


def _format_quote(s: dict) -> str:
    q = s.get("quote") or {}
    lines = ["Расчёт заказа", f"Бетон {s['grade']}, {s['volume']:g} м³"]
    if q.get("zone"):
        lines.append(f"Зона доставки: {q['zone']}")
    if q.get("mixers", 1) > 1:
        lines.append(f"Подач миксера: {q['mixers']}")
    if q.get("beton_cost") is not None:
        lines.append(f"Бетон: {_rub(q['beton_cost'])}")
    if q.get("needs_manager"):
        lines.append("Доставка: уточнит менеджер (ваш адрес — по договорённости)")
    elif q.get("delivery_min") is not None:
        lines.append(f"Доставка: {_range(q['delivery_min'], q['delivery_max'])}")
        if q.get("total_min") is not None:
            lines.append(f"Итого: {_range(q['total_min'], q['total_max'])}")
    lines.append("Цена ориентировочная, финальную подтвердит менеджер.")
    return "\n".join(lines)


# ── Диалог (та же логика, что в Telegram) ────────────────────────────────────

async def _greet(client, uid):
    s = _sess(uid)
    s.update({"state": IDLE, "ai_history": []})
    await _max_send(client, uid,
        "👋 Здравствуйте! Я Максим из «Бетон Экспресс», Кемерово.\n"
        "Спросите про бетон (марка под фундамент, объём, цена) или нажмите «Рассчитать и заказать».",
        _kb_main())


async def _consult(client, uid, text):
    s = _sess(uid)
    hist = s["ai_history"]
    hist.append({"role": "user", "content": text})
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{BACKEND_URL}/api/ai/chat", json={"messages": hist[-AI_HISTORY_MAX:]})
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.error("MAX ai chat failed: %s", exc)
        data = {"reply": None, "action": {"type": "fallback"}}
    reply = data.get("reply")
    action = data.get("action") or {}
    if reply:
        hist.append({"role": "assistant", "content": reply})
        del hist[:-AI_HISTORY_MAX]
    if action.get("type") == "start_order":
        s["prefill"] = {"grade": action.get("grade"), "volume": action.get("volume")}
        if reply:
            await _max_send(client, uid, reply)
        await _order_entry(client, uid)
        return
    if action.get("type") == "request_phone":
        order = action.get("order") or {}
        s.update({"grade": order.get("grade"), "volume": order.get("volume"),
                  "address": order.get("address"), "delivery_date": order.get("delivery_date"),
                  "urgency": DATE_TO_URGENCY.get(order.get("delivery_date"), "normal"),
                  "payment_method": order.get("payment_method"), "state": PHONE})
        # расчёт, собранный нейросетью по ходу диалога — чтобы сумма попала в заявку
        if action.get("quote"):
            s["quote"] = action["quote"]
        if reply:
            await _max_send(client, uid, reply)
        await _max_send(client, uid, "Оставьте номер — менеджер подтвердит заказ и время доставки 👇", _kb_phone())
        return
    if action.get("type") == "call_human":
        if reply:
            await _max_send(client, uid, reply)
        await _human(client, uid)
        return
    if not reply or action.get("type") == "fallback":
        await _max_send(client, uid, "Давайте посчитаю точно — нажмите «Рассчитать и заказать».", _kb_main())
        return
    await _max_send(client, uid, reply, _kb_main())


async def _order_entry(client, uid):
    s = _sess(uid)
    prefill = s.get("prefill") or {}
    grade = prefill.get("grade")
    if grade in GRADES:
        s["grade"] = grade
        vol = prefill.get("volume")
        if vol:
            try:
                s["volume"] = float(vol); s["state"] = ADDRESS
                await _max_send(client, uid, f"Марка {grade}, объём {float(vol):g} м³ ✅\nНапишите адрес доставки:")
                return
            except (TypeError, ValueError):
                pass
        s["state"] = VOLUME
        await _max_send(client, uid, f"Марка {grade} ✅\nСколько кубов нужно? Напишите число (м³):")
        return
    s["state"] = VOLUME  # ждём выбор марки кнопкой
    await _max_send(client, uid, "Выберите марку бетона:", _kb_grades())


async def _human(client, uid):
    # v1 для МАКС: просим телефон, помечаем заявку как «просит менеджера».
    s = _sess(uid)
    s["human"] = True
    s["state"] = PHONE
    await _max_send(client, uid,
        "Передаю менеджеру. Оставьте номер — перезвонит в ближайшее время.", _kb_phone())


async def _do_quote(client, uid):
    s = _sess(uid)
    await _max_send(client, uid, "⏳ Считаю стоимость и доставку…")
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{BACKEND_URL}/api/quote",
                             json={"concrete_grade": s["grade"], "volume": s["volume"], "address": s["address"]})
            r.raise_for_status()
            s["quote"] = r.json()
    except Exception as exc:
        logger.error("MAX quote failed: %s", exc)
        s["quote"] = None
    if s.get("quote"):
        await _max_send(client, uid, _format_quote(s))
    s["state"] = DATE
    await _max_send(client, uid, "Когда нужна доставка?", _kb_date())


async def _create_lead(client, uid, phone, name):
    s = _sess(uid)
    # если котировки ещё нет (AI-заказ) — посчитать по собранным данным
    if not s.get("quote") and s.get("grade") and s.get("volume") and s.get("address"):
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(f"{BACKEND_URL}/api/quote", json={
                    "concrete_grade": s["grade"], "volume": s["volume"], "address": s["address"]})
                if r.status_code == 200:
                    s["quote"] = r.json()
        except Exception as exc:
            logger.error("MAX ai quote failed: %s", exc)
    q = s.get("quote") or {}
    amount = q.get("total_max") or q.get("total_min") or q.get("beton_cost")
    comment = "Заявка из МАКС-бота" + (" (просит менеджера)" if s.get("human") else "")
    lead = {
        "name": name or "Клиент", "phone": phone,
        "source": "max", "source_platform": "max", "source_channel": "message",
        "concrete_grade": s.get("grade"), "volume": s.get("volume"), "address": s.get("address"),
        "delivery_date": s.get("delivery_date"), "urgency": s.get("urgency", "normal"),
        "payment_method": s.get("payment_method"), "distance": q.get("distance_km"),
        "calculated_amount": amount, "comment": comment,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{BACKEND_URL}/api/leads/create", json=lead)
            r.raise_for_status()
            res = r.json()
        if res.get("status") == "duplicate":
            txt = "Вы уже оставляли заявку — менеджер свяжется с вами."
        else:
            txt = "✅ Заявка принята! Менеджер перезвонит и подтвердит стоимость и время доставки. Спасибо! 🚛"
    except Exception as exc:
        logger.error("MAX lead create failed: %s", exc)
        txt = "✅ Данные приняты. Менеджер свяжется с вами вручную."
    _sessions[uid] = {"state": IDLE, "ai_history": []}
    await _max_send(client, uid, txt)


# ── Роутинг апдейтов ─────────────────────────────────────────────────────────

def _extract_phone(message: dict):
    """Достать телефон из contact-вложения (⚠️ сверить формат) или из текста."""
    for att in (message.get("body", {}).get("attachments") or message.get("attachments") or []):
        if att.get("type") == "contact":
            p = att.get("payload") or {}
            # варианты, встречающиеся в TamTam/MAX:
            phone = (p.get("tam_info") or {}).get("phone") or p.get("phone")
            if phone:
                return str(phone)
    return None


async def _handle_message(client, update):
    message = update.get("message") or {}
    sender = message.get("sender") or {}
    uid = sender.get("user_id")
    if not uid:
        return
    name = sender.get("name") or "Клиент"
    text = (message.get("body") or {}).get("text") or ""
    s = _sess(uid)

    # контакт (телефон)
    phone = _extract_phone(message)
    if s["state"] == PHONE and (phone or len(text.strip()) >= 6):
        await _create_lead(client, uid, phone or text.strip(), name)
        return

    if text.strip() in ("/start", "start", "Старт", "старт"):
        await _greet(client, uid)
        return

    st = s["state"]
    if st == VOLUME:
        raw = text.replace(",", ".").strip()
        try:
            v = float(raw)
            if not (0 < v <= 1000):
                raise ValueError
        except ValueError:
            await _max_send(client, uid, "Введите объём числом в м³, например: 6")
            return
        s["volume"] = v; s["state"] = ADDRESS
        await _max_send(client, uid, f"Объём: {v:g} м³ ✅\nНапишите адрес доставки (город, улица, дом):")
        return
    if st == ADDRESS:
        if len(text.strip()) < 3:
            await _max_send(client, uid, "Уточните адрес (улица и дом).")
            return
        s["address"] = text.strip()
        await _do_quote(client, uid)
        return
    if st == PHONE:
        await _max_send(client, uid, "Отправьте номер кнопкой ниже 👇", _kb_phone())
        return

    # иначе — свободный чат с AI
    await _consult(client, uid, text.strip())


async def _handle_callback(client, update):
    cb = update.get("callback") or {}
    payload = cb.get("payload") or ""
    user = cb.get("user") or (update.get("message") or {}).get("sender") or {}
    uid = user.get("user_id")
    if not uid:
        return
    s = _sess(uid)
    if payload == "order":
        await _order_entry(client, uid)
    elif payload == "human":
        await _human(client, uid)
    elif payload.startswith("grade:"):
        s["grade"] = payload.split(":", 1)[1]; s["state"] = VOLUME
        await _max_send(client, uid, f"Марка: {s['grade']} ✅\nСколько кубов нужно? Напишите число (м³):")
    elif payload.startswith("date:"):
        val = payload.split(":", 1)[1]
        s["delivery_date"] = val; s["urgency"] = DATE_TO_URGENCY.get(val, "normal"); s["state"] = PAYMENT
        await _max_send(client, uid, "Способ оплаты?", _kb_pay())
    elif payload.startswith("pay:"):
        s["payment_method"] = payload.split(":", 1)[1]; s["state"] = PHONE
        await _max_send(client, uid, "Оставьте номер телефона — менеджер подтвердит заказ 👇", _kb_phone())


async def _handle_update(client, update):
    t = update.get("update_type")
    try:
        if t in ("message_created",):
            await _handle_message(client, update)
        elif t in ("message_callback",):
            await _handle_callback(client, update)
        elif t in ("bot_started",):
            uid = (update.get("user") or {}).get("user_id") or update.get("chat_id")
            if uid:
                await _greet(client, uid)
    except Exception as exc:
        logger.error("MAX update handling failed: %s", exc)


# ── Запуск в backend-процессе ────────────────────────────────────────────────

async def _poll_loop():
    global _running
    marker = None
    async with httpx.AsyncClient(timeout=40) as client:
        while _running:
            try:
                data = await _max_get_updates(client, marker)
                for upd in data.get("updates", []):
                    await _handle_update(client, upd)
                marker = data.get("marker", marker)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("MAX polling failed: %s", e)
                await asyncio.sleep(5)


async def start_max_bot() -> bool:
    global _poll_task, _running
    if not MAX_BOT_TOKEN:
        logger.warning("MAX_BOT_TOKEN не задан — МАКС-бот отключён")
        return False
    if _poll_task is not None:
        return True
    _running = True
    _poll_task = asyncio.create_task(_poll_loop(), name="max-bot-polling")
    logger.info("МАКС-бот запущен (в backend)")
    return True


async def stop_max_bot():
    global _poll_task, _running
    _running = False
    if _poll_task:
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
        _poll_task = None
