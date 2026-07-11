"""
Клиентский AI-бот заказа бетона для мессенджера МАКС (max.ru), встроен в backend.

МАКС Bot API: long-polling и инлайн-кнопки (callback). Телефон клиент вводит
вручную. Ядро (AI, зоны, цены, лид) переиспользуется —
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
import re

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
SALES_PHONE = "+73842635555"
SALES_PHONE_DISPLAY = "+7 (3842) 63-55-55"

# Состояния FSM per user
IDLE, VOLUME, ADDRESS, DATE, PAYMENT, PHONE, MANAGER = (
    "idle", "volume", "address", "date", "payment", "phone", "manager"
)

_sessions: dict = {}       # user_id -> dict(state, grade, volume, address, quote, ai_history, ...)
_poll_task = None
_running = False


def _sess(uid: int) -> dict:
    return _sessions.setdefault(uid, {"state": IDLE, "ai_history": []})


# ── MAX Bot API (тонкий слой; сверить форматы) ───────────────────────────────

# MAX объявил, что токен в query-параметре устаревает — шлём и заголовок Authorization,
# и query-параметр (совместимость). Если сервер игнорирует один — сработает другой.
def _max_headers() -> dict:
    return {"Authorization": MAX_BOT_TOKEN}


async def _max_get_updates(client: httpx.AsyncClient, marker):
    params = {"access_token": MAX_BOT_TOKEN, "timeout": 30, "limit": 100}
    if marker is not None:
        params["marker"] = marker
    r = await client.get(f"{MAX_API_BASE}/updates", params=params, headers=_max_headers())
    r.raise_for_status()
    return r.json()


async def _max_send(client: httpx.AsyncClient, user_id: int, text: str, buttons=None):
    """Отправить сообщение пользователю. buttons — список рядов callback-кнопок."""
    body = {"text": text}
    if buttons:
        body["attachments"] = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
    try:
        r = await client.post(f"{MAX_API_BASE}/messages",
                              params={"access_token": MAX_BOT_TOKEN, "user_id": user_id},
                              json=body, headers=_max_headers())
        if r.status_code >= 400:
            logger.error("MAX send HTTP %s: %s", r.status_code, r.text[:300])
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
    return [
        [_btn_cb("🔄 Начать заново", "restart")],
        [_btn_cb("🧱 Оформить новый заказ", "order")],
        [_btn_cb("📋 Помочь с расчётом", "ai_chat")],
        [_btn_cb("💬 Написать менеджеру", "human")],
        [_btn_cb("📞 Позвонить / контакты", "contacts")],
    ]


def _kb_date():
    return [[_btn_cb("Сегодня", "date:Сегодня"), _btn_cb("Завтра", "date:Завтра")],
            [_btn_cb("На неделе", "date:На неделе"), _btn_cb("Не срочно", "date:Не срочно")]]


def _kb_pay():
    return [[_btn_cb("Наличные", "pay:Наличные")],
            [_btn_cb("Безналичный расчёт", "pay:Безналичный расчёт")],
            [_btn_cb("Перевод на карту", "pay:Перевод на карту")]]


def _manual_phone(text: str):
    digits = re.sub(r"\D", "", text or "")
    return digits if 6 <= len(digits) <= 15 else None


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
    _sessions[uid] = {"state": IDLE, "ai_history": []}
    await _max_send(client, uid,
        "👋 Здравствуйте! Я Максим из «Бетон Экспресс», Кемерово.\n"
        "Оформите новый заказ, получите помощь с расчётом или свяжитесь с менеджером.\n"
        f"Телефон диспетчера: {SALES_PHONE_DISPLAY}.",
        _kb_main())


async def _ai_entry(client, uid):
    _sessions[uid] = {"state": IDLE, "ai_history": []}
    await _max_send(
        client,
        uid,
        "Чтобы быстрее получить расчёт, напишите одним сообщением:\n"
        "1. Что нужно залить.\n"
        "2. Размеры объекта.\n"
        "3. Адрес доставки.\n\n"
        "Например: «Плита 10 × 8 м, толщина 20 см, доставка в Кемерово». "
        "Если не смогу ответить уверенно, сразу подключу менеджера.",
    )


async def _show_contacts(client, uid):
    await _max_send(
        client,
        uid,
        f"📞 Бетон Экспресс\nДиспетчер: {SALES_PHONE_DISPLAY}\n"
        f"Полный номер: {SALES_PHONE}\nНажмите на номер в сообщении, чтобы позвонить, "
        "или выберите «Написать менеджеру».",
        _kb_main(),
    )


async def send_to_max_user(uid: int, text: str, show_menu: bool = False) -> None:
    """Отправить ответ менеджера из Telegram клиенту в MAX."""
    async with httpx.AsyncClient(timeout=20) as client:
        await _max_send(client, uid, text, _kb_main() if show_menu else None)


async def end_manager_chat(uid: int) -> None:
    """Завершить прямой диалог с менеджером и вернуть меню MAX."""
    _sessions[uid] = {"state": IDLE, "ai_history": []}
    await send_to_max_user(
        uid,
        "Менеджер завершил диалог. Можно начать новый заказ или получить помощь с расчётом.",
        show_menu=True,
    )


async def _notify_sales_manager(uid: int, name: str, text: str) -> bool:
    """Передать сообщение MAX-клиента в Telegram-группу отдела продаж."""
    try:
        from bot import main as telegram_bot

        chat_id = telegram_bot.effective_sales_chat()
        if not chat_id or telegram_bot.telegram_app is None:
            return False
        await telegram_bot.telegram_app.bot.send_message(
            chat_id,
            f"💬 Клиент из MAX\nИмя: {name or 'Клиент'} (max_id {uid})\n"
            f"Сообщение: {text}\n\nОтветьте reply на это сообщение. /end — завершить диалог.",
        )
        return True
    except Exception as exc:
        logger.error("MAX manager relay failed: %s", exc)
        return False


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
        await _max_send(
            client,
            uid,
            "Введите номер телефона цифрами вручную, например: 8 923 123-45-67. "
            "Автоматическая отправка контакта отключена.",
        )
        return
    if action.get("type") == "call_human":
        if reply:
            await _max_send(client, uid, reply)
        await _human(client, uid)
        return
    if not reply or action.get("type") == "fallback":
        await _human(client, uid, reason="Нейросеть не смогла уверенно ответить или временно недоступна")
        return
    await _max_send(client, uid, reply)


async def _order_entry(client, uid):
    s = _sess(uid)
    prefill = s.get("prefill") or {}
    name = s.get("name")
    _sessions[uid] = {"state": IDLE, "ai_history": [], "name": name}
    s = _sess(uid)
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


async def _human(client, uid, reason: str = ""):
    """Включить прямой диалог MAX-клиента с отделом продаж в Telegram."""
    s = _sess(uid)
    s["human"] = True
    s["state"] = MANAGER
    intro = reason or "Клиент хочет связаться с менеджером"
    connected = await _notify_sales_manager(uid, s.get("name") or "Клиент", intro)
    if connected:
        await _max_send(
            client,
            uid,
            "✅ Менеджер подключён. Напишите сообщение прямо здесь — ответ придёт в этот чат. "
            f"Также можно позвонить: {SALES_PHONE_DISPLAY}.",
        )
    else:
        await _max_send(
            client,
            uid,
            f"Сейчас чат менеджера недоступен. Позвоните диспетчеру: {SALES_PHONE_DISPLAY}.",
            _kb_main(),
        )


async def _relay_to_manager(client, uid, text):
    s = _sess(uid)
    connected = await _notify_sales_manager(uid, s.get("name") or "Клиент", text)
    if connected:
        await _max_send(client, uid, "✅ Сообщение передано менеджеру. Ожидайте ответ здесь.")
    else:
        await _max_send(client, uid, f"Не удалось передать сообщение. Позвоните: {SALES_PHONE_DISPLAY}.", _kb_main())


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
    # Карточку в группу отдела продаж шлёт backend-уведомитель (notify_sales_group)
    # по прямому каналу api.telegram.org — надёжно и без дублей с TG-ботом.
    _sessions[uid] = {"state": IDLE, "ai_history": []}
    await _max_send(client, uid, txt)
    await _max_send(client, uid, "Можно оформить ещё один заказ или продолжить общение 👇", _kb_main())


# ── Роутинг апдейтов ─────────────────────────────────────────────────────────

def _extract_phone(message: dict):
    """Определить contact-вложение, чтобы отклонить автоматическую передачу номера."""
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
    s["name"] = name

    command = text.strip().lower()
    if command in ("/start", "start", "старт", "начать", "начать заново"):
        await _greet(client, uid)
        return
    if command in ("/order", "заказ", "новый заказ"):
        await _order_entry(client, uid)
        return
    if command in ("/ai", "нейросеть", "спросить нейросеть", "помочь с расчётом"):
        await _ai_entry(client, uid)
        return
    if command in ("/contacts", "контакты", "телефон", "позвонить"):
        await _show_contacts(client, uid)
        return
    if command in ("/manager", "менеджер", "написать менеджеру"):
        await _human(client, uid)
        return

    # Телефон принимается только ручным вводом, контакт-вложение отклоняем.
    if s["state"] == PHONE:
        if _extract_phone(message):
            await _max_send(
                client,
                uid,
                "Контакт не принимаю. Введите номер телефона цифрами вручную, например: "
                "8 923 123-45-67.",
            )
            return
        phone = _manual_phone(text)
        if phone:
            await _create_lead(client, uid, phone, name)
        else:
            await _max_send(client, uid, "Введите корректный номер телефона цифрами вручную.")
        return

    if s["state"] == MANAGER:
        if text.strip():
            await _relay_to_manager(client, uid, text.strip())
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
    s["name"] = user.get("name") or s.get("name") or "Клиент"
    if payload == "restart":
        await _greet(client, uid)
    elif payload == "order":
        await _order_entry(client, uid)
    elif payload == "ai_chat":
        await _ai_entry(client, uid)
    elif payload == "human":
        await _human(client, uid)
    elif payload == "contacts":
        await _show_contacts(client, uid)
    elif payload.startswith("grade:"):
        s["grade"] = payload.split(":", 1)[1]; s["state"] = VOLUME
        await _max_send(client, uid, f"Марка: {s['grade']} ✅\nСколько кубов нужно? Напишите число (м³):")
    elif payload.startswith("date:"):
        val = payload.split(":", 1)[1]
        s["delivery_date"] = val; s["urgency"] = DATE_TO_URGENCY.get(val, "normal"); s["state"] = PAYMENT
        await _max_send(client, uid, "Способ оплаты?", _kb_pay())
    elif payload.startswith("pay:"):
        s["payment_method"] = payload.split(":", 1)[1]; s["state"] = PHONE
        await _max_send(
            client,
            uid,
            "Введите номер телефона цифрами вручную, например: 8 923 123-45-67. "
            "Автоматическая отправка контакта отключена.",
        )


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
