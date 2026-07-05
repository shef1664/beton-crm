"""
Клиентский AI-бот заказа бетона «Бетон Экспресс», встроенный в backend-процесс.

Работает на существующем @otdprod_bot (settings.TELEGRAM_BOT_TOKEN), опрос идёт
внутри backend (start_bot/stop_bot вызываются из main.py). Нового бота регистрировать
не нужно. Админ-панель убрана; уведомления менеджеру шлёт notifier (по HTTP).

Гибрид:
  • Консультация (свободный чат) → POST /api/ai/chat (Claude, tool-use).
  • Оформление заказа (кнопки): марка → объём → адрес → /api/quote (зоны доставки)
    → дата → оплата → телефон(кнопка) → /webhooks/telegram → CRM.
  • Отдел продаж: карточка заявки в группу + живая передача менеджеру (оператор).

Персональные данные (телефон, адрес) в нейросеть не передаются.
"""

import asyncio
import logging
import os
import re
from typing import Optional

import httpx
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import settings

logger = logging.getLogger(__name__)

# Бот и backend в одном процессе — зовём свои эндпоинты по localhost.
_PORT = os.getenv("PORT", "8000")
BACKEND_URL = f"http://127.0.0.1:{_PORT}"
# Группа отдела продаж (добавьте @otdprod_bot в группу, укажите её chat_id).
SALES_CHAT_ID = int(os.getenv("SALES_CHAT_ID", "0") or 0)

GRADES = ["М100", "М150", "М200", "М250", "М300", "М350", "М400", "М450"]
DATE_TO_URGENCY = {"Сегодня": "today", "Завтра": "normal", "На неделе": "normal", "Не срочно": "normal"}
VOLUME, ADDRESS, DATE, PAYMENT, PHONE = range(5)
AI_HISTORY_MAX = 20

telegram_app: Optional[Application] = None
polling_task: Optional[asyncio.Task] = None


# ── Клавиатуры / утилиты ─────────────────────────────────────────────────────

def client_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧮 Рассчитать и заказать", callback_data="order")],
        [InlineKeyboardButton("👤 Позвать менеджера", callback_data="human")],
    ])


def grades_keyboard() -> InlineKeyboardMarkup:
    rows, row = [], []
    for grade in GRADES:
        row.append(InlineKeyboardButton(grade, callback_data=f"grade:{grade}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def date_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["Сегодня", "Завтра"], ["На неделе", "Не срочно"]],
                               resize_keyboard=True, one_time_keyboard=True)


def payment_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["Наличные", "Безналичный расчёт"], ["Перевод на карту"]],
                               resize_keyboard=True, one_time_keyboard=True)


def phone_keyboard() -> ReplyKeyboardMarkup:
    btn = KeyboardButton("📱 Отправить мой номер", request_contact=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)


def _rub(n) -> str:
    return f"{int(n):,} ₽".replace(",", " ")


def _range(a, b) -> str:
    return _rub(a) if a == b else f"{_rub(a)}–{_rub(b)}"


# ── Приветствие и консультация (AI) ──────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _operators(context).discard(update.effective_user.id)
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Здравствуйте! Меня зовут Максим, я из «Бетон Экспресс», Кемерово.\n\n"
        "Спросите что угодно про бетон — какая марка под ваш фундамент, сколько кубов "
        "нужно, сколько будет стоить. Или сразу нажмите «Рассчитать и заказать» 👇",
        reply_markup=client_keyboard(),
    )


async def consult(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id in _operators(context):
        await relay_to_sales(update, context)
        return

    text = update.message.text.strip()
    # Клиент печатает телефон текстом, когда бот его ждёт (AI-заказ)
    if context.user_data.get("ai_order") and sum(c.isdigit() for c in text) >= 6:
        await create_ai_lead(update, context, text, update.effective_user.first_name or "Клиент")
        return

    history = context.user_data.setdefault("ai_history", [])
    history.append({"role": "user", "content": text})

    await update.message.chat.send_action("typing")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{BACKEND_URL}/api/ai/chat",
                                     json={"messages": history[-AI_HISTORY_MAX:]})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.error("ai chat failed: %s", exc)
        data = {"reply": None, "action": {"type": "fallback"}}

    reply = data.get("reply")
    action = data.get("action") or {}
    if reply:
        history.append({"role": "assistant", "content": reply})
        del history[:-AI_HISTORY_MAX]

    if action.get("type") == "start_order":
        context.user_data["prefill"] = {"grade": action.get("grade"), "volume": action.get("volume")}
        if reply:
            await update.message.reply_text(reply)
        await update.message.reply_text("Готов оформить — нажмите кнопку 👇", reply_markup=client_keyboard())
        return

    if action.get("type") == "request_phone":
        context.user_data["ai_order"] = action.get("order") or {}
        context.user_data["ai_quote"] = action.get("quote")
        if reply:
            await update.message.reply_text(reply)
        await update.message.reply_text(
            "Оставьте номер телефона — менеджер подтвердит заказ и время доставки 👇",
            reply_markup=phone_keyboard())
        return

    if action.get("type") == "call_human":
        if reply:
            await update.message.reply_text(reply)
        await start_operator(update, context, reason=action.get("reason", ""))
        return

    if not reply or action.get("type") == "fallback":
        await update.message.reply_text(
            "Давайте посчитаю точно — нажмите «Рассчитать и заказать» 👇",
            reply_markup=client_keyboard(),
        )
        return

    await update.message.reply_text(reply, reply_markup=client_keyboard())


# ── Живая передача менеджеру (режим оператора) ───────────────────────────────

def _operators(context) -> set:
    return context.bot_data.setdefault("operators", set())


def _relay_map(context) -> dict:
    return context.bot_data.setdefault("relay", {})


async def start_operator(update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str = "") -> None:
    msg = update.effective_message
    if not SALES_CHAT_ID:
        await msg.reply_text(
            "Передаю менеджеру — он свяжется с вами. Можете оставить заявку кнопкой ниже.",
            reply_markup=client_keyboard(),
        )
        return
    user = update.effective_user
    _operators(context).add(user.id)

    hist = context.user_data.get("ai_history", [])
    tail = "\n".join(f"{'Клиент' if m['role'] == 'user' else 'Бот'}: {m['content']}" for m in hist[-6:])
    header = (
        f"🔔 Клиент просит менеджера\n"
        f"Имя: {user.first_name} @{user.username or '—'} (id {user.id})"
    )
    if reason:
        header += f"\nПричина: {reason}"
    if tail:
        header += f"\n\nПоследние сообщения:\n{tail}"
    header += "\n\nОтветьте reply на это сообщение, чтобы написать клиенту. «/end» — завершить."
    try:
        sent = await context.bot.send_message(SALES_CHAT_ID, header)
        _relay_map(context)[sent.message_id] = user.id
    except Exception as exc:
        logger.error("sales notify failed: %s", exc)
        _operators(context).discard(user.id)
        await msg.reply_text("Менеджер свяжется с вами. Оставьте, пожалуйста, заявку 👇",
                             reply_markup=client_keyboard())
        return
    await msg.reply_text("✅ Передал менеджеру отдела продаж — скоро ответит. Пишите прямо здесь.")


async def call_manager(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await start_operator(update, context)


async def relay_to_sales(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text
    try:
        sent = await context.bot.send_message(SALES_CHAT_ID, f"💬 {user.first_name} (id {user.id}): {text}")
        _relay_map(context)[sent.message_id] = user.id
    except Exception as exc:
        logger.error("relay to sales failed: %s", exc)


def _client_id_from_reply(context, reply_to) -> Optional[int]:
    """id клиента: сперва из карты (в памяти), иначе парсим из текста «(id 12345)».
    Так ответ работает даже после рестарта и при смене id группы (супергруппа)."""
    cid = _relay_map(context).get(reply_to.message_id)
    if cid:
        return cid
    m = re.search(r"id\s+(\d+)", reply_to.text or reply_to.caption or "")
    return int(m.group(1)) if m else None


async def sales_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply_to = update.message.reply_to_message
    if not reply_to:
        return
    # отвечаем только на сообщения бота (карточки/реле), не на чужие
    if not (reply_to.from_user and reply_to.from_user.id == context.bot.id):
        return
    client_id = _client_id_from_reply(context, reply_to)
    if not client_id:
        return
    text = (update.message.text or "").strip()
    if text == "/end":
        _operators(context).discard(client_id)
        try:
            await context.bot.send_message(client_id, "Менеджер завершил диалог. Спросите ещё что-нибудь или оформите заказ 👇",
                                           reply_markup=client_keyboard())
        except Exception:
            pass
        await update.message.reply_text("Диалог с клиентом завершён.")
        return
    try:
        await context.bot.send_message(client_id, f"👨‍💼 Менеджер: {text}")
    except Exception as exc:
        logger.error("sales_reply deliver failed: %s", exc)


# ── Оформление заказа ────────────────────────────────────────────────────────

async def order_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    prefill = context.user_data.get("prefill") or {}
    grade = prefill.get("grade")
    if grade in GRADES:
        context.user_data["grade"] = grade
        vol = prefill.get("volume")
        if vol:
            try:
                context.user_data["volume"] = float(vol)
                await query.message.reply_text(
                    f"Марка {grade}, объём {float(vol):g} м³ ✅\n\n"
                    "Напишите адрес доставки (город, улица, дом):",
                    reply_markup=ReplyKeyboardRemove(),
                )
                return ADDRESS
            except (TypeError, ValueError):
                pass
        await query.message.reply_text(
            f"Марка {grade} ✅\n\nСколько кубов нужно? Напишите число (м³), например: 6"
        )
        return VOLUME
    await query.message.reply_text("Выберите марку бетона:", reply_markup=grades_keyboard())
    return VOLUME


async def choose_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    grade = query.data.split(":", 1)[1]
    context.user_data["grade"] = grade
    await query.edit_message_text(
        f"Марка: {grade} ✅\n\nСколько кубов нужно? Напишите число (м³), например: 6"
    )
    return VOLUME


async def enter_volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.replace(",", ".").strip()
    try:
        volume = float(raw)
        if volume <= 0 or volume > 1000:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите объём числом в м³, например: 6")
        return VOLUME
    context.user_data["volume"] = volume
    await update.message.reply_text(
        f"Объём: {volume:g} м³ ✅\n\n"
        "Напишите адрес доставки (город, улица, дом), например:\n"
        "Кемерово, проспект Ленина 90"
    )
    return ADDRESS


async def enter_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    address = update.message.text.strip()
    if len(address) < 3:
        await update.message.reply_text("Уточните адрес, пожалуйста (улица и дом).")
        return ADDRESS
    context.user_data["address"] = address
    await update.message.reply_text("⏳ Считаю стоимость и доставку…")

    payload = {
        "concrete_grade": context.user_data["grade"],
        "volume": context.user_data["volume"],
        "address": address,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(f"{BACKEND_URL}/api/quote", json=payload)
            resp.raise_for_status()
            context.user_data["quote"] = resp.json()
    except Exception as exc:
        logger.error("quote failed: %s", exc)
        context.user_data["quote"] = None
        await update.message.reply_text(
            "⚠️ Не удалось рассчитать автоматически — менеджер посчитает вручную."
        )

    if context.user_data.get("quote"):
        await update.message.reply_text(format_quote(context.user_data), parse_mode="HTML")

    await update.message.reply_text("Когда нужна доставка?", reply_markup=date_keyboard())
    return DATE


async def enter_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip()
    context.user_data["delivery_date"] = choice
    context.user_data["urgency"] = DATE_TO_URGENCY.get(choice, "normal")
    await update.message.reply_text("Способ оплаты?", reply_markup=payment_keyboard())
    return PAYMENT


async def enter_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["payment_method"] = update.message.text.strip()
    await update.message.reply_text(
        "Оставьте номер телефона — менеджер подтвердит заказ и время доставки 👇",
        reply_markup=phone_keyboard(),
    )
    return PHONE


def format_quote(ud: dict) -> str:
    q = ud.get("quote") or {}
    grade = ud["grade"]
    volume = ud["volume"]
    lines = ["<b>Расчёт заказа</b>", f"Бетон {grade}, {volume:g} м³"]
    if q.get("zone"):
        lines.append(f"Зона доставки: {q['zone']}")
    if q.get("mixers", 1) > 1:
        lines.append(f"Подач миксера: {q['mixers']}")

    beton = q.get("beton_cost")
    if beton is not None:
        lines.append(f"\nБетон: {_rub(beton)}")

    if q.get("needs_manager"):
        lines.append("Доставка: <b>уточнит менеджер</b> (ваш адрес — по договорённости)")
    elif q.get("delivery_min") is not None:
        lines.append(f"Доставка: {_range(q['delivery_min'], q['delivery_max'])}")
        if q.get("total_min") is not None:
            lines.append(f"<b>Итого: {_range(q['total_min'], q['total_max'])}</b>")

    lines.append("\n<i>Цена ориентировочная, финальную подтвердит менеджер.</i>")
    return "\n".join(lines)


async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.contact:
        phone = update.message.contact.phone_number
        name = update.message.contact.first_name or update.effective_user.first_name
    else:
        phone = update.message.text.strip()
        name = update.effective_user.first_name or "Клиент"
    if len(phone) < 6:
        await update.message.reply_text("Похоже, номер неполный. Отправьте телефон кнопкой ниже.")
        return PHONE

    ud = context.user_data
    quote = ud.get("quote") or {}
    amount = quote.get("total_max") or quote.get("total_min") or quote.get("beton_cost")
    payload = {
        "lead_data": {
            "name": name,
            "phone": phone,
            "concrete_grade": ud.get("grade"),
            "volume": ud.get("volume"),
            "address": ud.get("address"),
            "delivery_date": ud.get("delivery_date"),
            "urgency": ud.get("urgency", "normal"),
            "payment_method": ud.get("payment_method"),
            "distance": quote.get("distance_km"),
            "calculated_amount": amount,
            "comment": f"Заявка из Telegram-бота (tg_user={update.effective_user.id})",
        }
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(f"{BACKEND_URL}/webhooks/telegram", json=payload)
            resp.raise_for_status()
            result = resp.json()
        if result.get("status") == "duplicate":
            text = "Вы уже оставляли заявку — менеджер уже с ней работает и свяжется с вами."
        else:
            text = (
                "✅ Заявка принята! Менеджер перезвонит в ближайшее время и подтвердит "
                "стоимость и время доставки.\n\nСпасибо, что выбрали «Бетон Экспресс»! 🚛"
            )
    except Exception as exc:
        logger.error("lead create failed: %s", exc)
        text = "✅ Данные приняты. Менеджер свяжется с вами вручную."

    if SALES_CHAT_ID:
        rows = [
            "🧱 <b>Новая заявка из бота</b>",
            f"Имя: {name}",
            f"Телефон: {phone}",
            f"Марка: {ud.get('grade') or '—'}",
            f"Объём: {ud.get('volume') or '—'} м³",
            f"Адрес: {ud.get('address') or '—'}",
            f"Когда: {ud.get('delivery_date') or '—'}",
            f"Оплата: {ud.get('payment_method') or '—'}",
            f"Зона: {quote.get('zone') or '—'}",
        ]
        if quote.get("needs_manager"):
            rows.append("Доставка: ⚠️ уточнить у клиента (вне тарифных зон)")
        elif quote.get("delivery_min") is not None:
            rows.append(f"Доставка: {_range(quote['delivery_min'], quote['delivery_max'])}")
        if amount:
            rows.append(f"Сумма (ориент.): {_rub(amount)}")
        try:
            await context.bot.send_message(SALES_CHAT_ID, "\n".join(rows), parse_mode="HTML")
        except Exception as exc:
            logger.error("sales card failed: %s", exc)

    await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Отменил оформление. Можете спросить меня о бетоне или начать заново.",
        reply_markup=client_keyboard(),
    )
    return ConversationHandler.END


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await start(update, context)
    return ConversationHandler.END


# ── AI-заказ: телефон кнопкой → лид (без ConversationHandler) ────────────────

async def ai_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Клиент поделился контактом в AI-режиме (после request_phone)."""
    if not context.user_data.get("ai_order"):
        return
    c = update.message.contact
    await create_ai_lead(update, context, c.phone_number, c.first_name or update.effective_user.first_name)


async def create_ai_lead(update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str, name: str) -> None:
    order = context.user_data.get("ai_order") or {}
    quote = None
    if order.get("grade") and order.get("volume") and order.get("address"):
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(f"{BACKEND_URL}/api/quote", json={
                    "concrete_grade": order.get("grade"), "volume": order.get("volume"),
                    "address": order.get("address")})
                if r.status_code == 200:
                    quote = r.json()
        except Exception as exc:
            logger.error("ai lead quote failed: %s", exc)
    # запасной вариант — расчёт, собранный нейросетью по ходу диалога
    q = quote or context.user_data.get("ai_quote") or {}
    amount = q.get("total_max") or q.get("total_min") or q.get("beton_cost")
    payload = {"lead_data": {
        "name": name or "Клиент", "phone": phone,
        "concrete_grade": order.get("grade"), "volume": order.get("volume"),
        "address": order.get("address"), "delivery_date": order.get("delivery_date"),
        "urgency": DATE_TO_URGENCY.get(order.get("delivery_date"), "normal"),
        "payment_method": order.get("payment_method"), "distance": q.get("distance_km"),
        "calculated_amount": amount,
        "comment": f"AI-заказ из Telegram (tg_user={update.effective_user.id})",
    }}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{BACKEND_URL}/webhooks/telegram", json=payload)
            r.raise_for_status()
            res = r.json()
        txt = ("Вы уже оставляли заявку — менеджер уже с ней работает."
               if res.get("status") == "duplicate"
               else "✅ Заявка принята! Менеджер перезвонит и подтвердит стоимость и время доставки. Спасибо! 🚛")
    except Exception as exc:
        logger.error("ai lead create failed: %s", exc)
        txt = "✅ Данные приняты. Менеджер свяжется с вами вручную."

    if SALES_CHAT_ID:
        rows = ["🧱 <b>Новая заявка из бота (AI)</b>", f"Имя: {name}", f"Телефон: {phone}",
                f"Марка: {order.get('grade') or '—'}", f"Объём: {order.get('volume') or '—'} м³",
                f"Адрес: {order.get('address') or '—'}", f"Когда: {order.get('delivery_date') or '—'}",
                f"Оплата: {order.get('payment_method') or '—'}", f"Зона: {q.get('zone') or '—'}"]
        if q.get("needs_manager"):
            rows.append("Доставка: ⚠️ уточнить у клиента (вне тарифных зон)")
        elif q.get("delivery_min") is not None:
            rows.append(f"Доставка: {_range(q['delivery_min'], q['delivery_max'])}")
        if amount:
            rows.append(f"Сумма (ориент.): {_rub(amount)}")
        try:
            await context.bot.send_message(SALES_CHAT_ID, "\n".join(rows), parse_mode="HTML")
        except Exception as exc:
            logger.error("sales card (ai) failed: %s", exc)

    context.user_data.pop("ai_order", None)
    context.user_data.pop("ai_quote", None)
    context.user_data["ai_history"] = []
    await update.message.reply_text(txt, reply_markup=ReplyKeyboardRemove())


# ── Сборка и запуск (в backend-процессе) ─────────────────────────────────────

def create_bot() -> Optional[Application]:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN не задан — клиентский бот отключён")
        return None

    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_entry, pattern=r"^order$")],
        states={
            VOLUME: [
                CallbackQueryHandler(choose_grade, pattern=r"^grade:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_volume),
            ],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_address)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_date)],
            PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_payment)],
            PHONE: [
                MessageHandler(filters.CONTACT, enter_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_phone),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", restart)],
        allow_reentry=True,
    )

    app.add_handler(order_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(call_manager, pattern=r"^human$"))
    # Ответ менеджера из группы: любой reply в группе на сообщение бота (не зависит
    # от точного SALES_CHAT_ID — устойчиво к смене id при апгрейде в супергруппу).
    app.add_handler(MessageHandler(
        (~filters.ChatType.PRIVATE) & filters.REPLY & filters.TEXT, sales_reply))
    # AI-заказ: контакт (телефон) в личке вне оформления → создать лид
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.CONTACT, ai_contact))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, consult))

    return app


async def _polling_loop(app: Application):
    offset = None
    while True:
        try:
            updates = await app.bot.get_updates(offset=offset, timeout=30)
            for update in updates:
                offset = update.update_id + 1
                await app.process_update(update)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Telegram polling failed: {e}")
            await asyncio.sleep(5)


async def start_bot() -> bool:
    global telegram_app, polling_task
    if telegram_app is not None:
        return True
    telegram_app = create_bot()
    if not telegram_app:
        return False
    try:
        await telegram_app.initialize()
        await telegram_app.start()
        polling_task = asyncio.create_task(_polling_loop(telegram_app), name="telegram-bot-polling")
        logger.info("Клиентский AI-бот запущен (в backend)")
        return True
    except Exception as e:
        logger.error(f"Telegram bot start failed: {e}")
        try:
            await telegram_app.shutdown()
        except Exception:
            pass
        telegram_app = None
        polling_task = None
        return False


async def stop_bot():
    global telegram_app, polling_task
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        polling_task = None
    if telegram_app:
        try:
            await telegram_app.stop()
            await telegram_app.shutdown()
            logger.info("Telegram бот остановлен")
        except Exception as e:
            logger.error(f"Telegram bot stop failed: {e}")
        telegram_app = None
