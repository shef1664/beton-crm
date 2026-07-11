"""
Клиентский AI-бот заказа бетона «Бетон Экспресс», встроенный в backend-процесс.

Работает на существующем @otdprod_bot (settings.TELEGRAM_BOT_TOKEN), опрос идёт
внутри backend (start_bot/stop_bot вызываются из main.py). Нового бота регистрировать
не нужно. Админ-панель убрана; уведомления менеджеру шлёт notifier (по HTTP).

Гибрид:
  • Консультация (свободный чат) → POST /api/ai/chat (Claude, tool-use).
  • Оформление заказа (кнопки): марка → объём → адрес → /api/quote (зоны доставки)
    → дата → оплата → телефон вручную → /webhooks/telegram → CRM.
  • Отдел продаж: карточка заявки в группу + живая передача менеджеру (оператор).

Персональные данные (телефон, адрес) в нейросеть не передаются.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

import httpx
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.error import TelegramError
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
from services.speech_to_text import TranscriptionError, transcribe_ogg, voice_input_enabled

logger = logging.getLogger(__name__)

# Бот и backend в одном процессе — зовём свои эндпоинты по localhost.
_PORT = os.getenv("PORT", "8000")
BACKEND_URL = f"http://127.0.0.1:{_PORT}"
# Группа отдела продаж (добавьте @otdprod_bot в группу, укажите её chat_id).
SALES_CHAT_ID = int(os.getenv("SALES_CHAT_ID", "0") or 0)
# Бот сам запоминает id группы из сообщений в ней (устойчиво к апгрейду в супергруппу,
# когда id меняется). Сохраняется в файл, чтобы пережить рестарт инстанса.
_SALES_CHAT_STATE = Path(os.getenv("SALES_CHAT_STATE", "/tmp/beton-sales-chat.json"))
_detected_sales_chat_id: Optional[int] = None


def _load_detected_sales_chat() -> None:
    global _detected_sales_chat_id
    try:
        if _SALES_CHAT_STATE.exists():
            _detected_sales_chat_id = int(json.loads(_SALES_CHAT_STATE.read_text()).get("chat_id") or 0) or None
    except Exception:  # noqa: BLE001
        _detected_sales_chat_id = None


def _save_detected_sales_chat(chat_id: int) -> None:
    global _detected_sales_chat_id
    _detected_sales_chat_id = chat_id
    try:
        _SALES_CHAT_STATE.write_text(json.dumps({"chat_id": chat_id}))
    except Exception as exc:  # noqa: BLE001
        logger.error("save sales chat id failed: %s", exc)


def effective_sales_chat() -> int:
    """Актуальный id группы отдела продаж: авто-определённый приоритетнее env."""
    return _detected_sales_chat_id or SALES_CHAT_ID


_load_detected_sales_chat()

GRADES = ["М100", "М150", "М200", "М250", "М300", "М350", "М400", "М450"]
DATE_TO_URGENCY = {"Сегодня": "today", "Завтра": "normal", "На неделе": "normal", "Не срочно": "normal"}
VOLUME, ADDRESS, DATE, PAYMENT, PHONE = range(5)
AI_HISTORY_MAX = 20
SALES_PHONE = "+73842635555"
SALES_PHONE_DISPLAY = "+7 (3842) 63-55-55"

telegram_app: Optional[Application] = None
polling_task: Optional[asyncio.Task] = None


# ── Клавиатуры / утилиты ─────────────────────────────────────────────────────

def client_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Начать заново", callback_data="restart")],
        [InlineKeyboardButton("🧱 Оформить новый заказ", callback_data="order")],
        [InlineKeyboardButton("📋 Помочь с расчётом", callback_data="ai_chat")],
        [InlineKeyboardButton("💬 Написать менеджеру", callback_data="human")],
        [InlineKeyboardButton("📞 Позвонить / контакты", callback_data="contacts")],
    ])


def order_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧱 Оформить заказ", callback_data="order")],
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


def phone_keyboard() -> ReplyKeyboardRemove:
    """Телефон принимается только ручным вводом, без передачи контакта Telegram."""
    return ReplyKeyboardRemove()


def _manual_phone(text: str) -> Optional[str]:
    digits = re.sub(r"\D", "", text or "")
    return digits if 6 <= len(digits) <= 15 else None


def _rub(n) -> str:
    return f"{int(n):,} ₽".replace(",", " ")


def _range(a, b) -> str:
    return _rub(a) if a == b else f"{_rub(a)}–{_rub(b)}"


async def send_sales_card(order: dict, quote: dict, name: str, phone: str,
                          source: str = "бота (AI)") -> None:
    """Карточка заявки в группу отдела продаж через работающего TG-бота.

    Используется и Telegram-, и МАКС-ботом (оба в одном backend-процессе), чтобы
    заявки из любого канала одинаково падали в группу отдела продаж.
    """
    if not effective_sales_chat() or telegram_app is None:
        return
    q = quote or {}
    order = order or {}
    amount = q.get("total_max") or q.get("total_min") or q.get("beton_cost")
    rows = [f"🧱 <b>Новая заявка из {source}</b>", f"Имя: {name}", f"Телефон: {phone}",
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
        await telegram_app.bot.send_message(effective_sales_chat(), "\n".join(rows), parse_mode="HTML")
    except Exception as exc:
        logger.error("sales card failed: %s", exc)


# ── Приветствие и консультация (AI) ──────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _operators(context).discard(update.effective_user.id)
    context.user_data.clear()
    await update.effective_message.reply_text(
        "👋 Здравствуйте! Меня зовут Максим, я из «Бетон Экспресс», Кемерово.\n\n"
        "Можно оформить новый заказ или получить помощь с расчётом: подобрать марку, "
        "посчитать объём и стоимость бетона. 👇",
        reply_markup=client_keyboard(),
    )


async def restart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Вернуть главное меню и очистить текущий сценарий."""
    await update.callback_query.answer()
    await start(update, context)
    return ConversationHandler.END


async def show_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать телефон компании как контакт, который можно сохранить или вызвать."""
    if update.callback_query:
        await update.callback_query.answer()
    await context.bot.send_contact(
        chat_id=update.effective_chat.id,
        phone_number=SALES_PHONE,
        first_name="Бетон Экспресс",
    )
    await update.effective_message.reply_text(
        f"Диспетчер: {SALES_PHONE_DISPLAY}. Нажмите на контакт выше, чтобы позвонить "
        "или сохранить номер.",
        reply_markup=client_keyboard(),
    )
    return ConversationHandler.END


async def ai_chat_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начать новый AI-диалог из меню или командой /ai."""
    if update.callback_query:
        await update.callback_query.answer()
    _operators(context).discard(update.effective_user.id)
    context.user_data.clear()
    await update.effective_message.reply_text(
        "Чтобы быстрее получить расчёт, напишите одним сообщением:\n"
        "1. Что нужно залить.\n"
        "2. Размеры объекта.\n"
        "3. Адрес доставки.\n\n"
        "Например: «Плита 10 × 8 м, толщина 20 см, доставка в Кемерово»."
    )
    return ConversationHandler.END


async def consult_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    if update.effective_user.id in _operators(context):
        await relay_to_sales(update, context, text=text)
        return

    # Режим счёта: текст уходит в генератор счёта, а не в AI-консультанта
    if context.user_data.get("invoice_mode"):
        if update.message.text is None:
            await update.message.reply_text("Реквизиты для счёта пока отправьте текстом.")
            return
        await handle_invoice_text(update, context)
        return

    text = text.strip()
    # Клиент печатает телефон текстом, когда бот его ждёт (AI-заказ)
    manual_phone = _manual_phone(text)
    if context.user_data.get("ai_order") and manual_phone:
        await create_ai_lead(update, context, manual_phone, update.effective_user.first_name or "Клиент")
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
        await update.message.reply_text("Готов оформить — нажмите кнопку 👇", reply_markup=order_keyboard())
        return

    if action.get("type") == "request_phone":
        context.user_data["ai_order"] = action.get("order") or {}
        context.user_data["ai_quote"] = action.get("quote")
        context.user_data["manual_phone_required"] = True
        if reply:
            await update.message.reply_text(reply)
        await update.message.reply_text(
            "Введите номер телефона цифрами вручную, например: 8 923 123-45-67. "
            "Автоматическая отправка контакта отключена.",
            reply_markup=phone_keyboard())
        return

    if action.get("type") == "call_human":
        if reply:
            await update.message.reply_text(reply)
        await start_operator(update, context, reason=action.get("reason", ""))
        return

    if not reply or action.get("type") == "fallback":
        await start_operator(
            update,
            context,
            reason="Нейросеть не смогла уверенно ответить или временно недоступна",
        )
        return

    await update.message.reply_text(reply)


async def consult(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await consult_text(update, context, update.message.text or "")


async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recognize a short Telegram voice message and process it as normal text."""
    if not voice_input_enabled():
        await update.message.reply_text(
            "Голосовые временно недоступны. Напишите сообщение текстом — я сразу помогу."
        )
        return
    if context.user_data.get("manual_phone_required"):
        await update.message.reply_text(
            "Номер телефона нужно ввести цифрами вручную, например: 8 923 123-45-67."
        )
        return

    await update.message.reply_text("🎤 Распознаю голос…")
    try:
        tg_file = await update.message.voice.get_file()
        audio = bytes(await tg_file.download_as_bytearray())
        text = await transcribe_ogg(audio)
    except (TranscriptionError, httpx.HTTPError, TelegramError) as exc:
        logger.warning("voice transcription failed: %s", exc)
        await update.message.reply_text(
            "Не получилось разобрать голосовое. Напишите сообщение текстом или нажмите «Написать менеджеру»."
        )
        return

    await update.message.reply_text(f"🎤 Я услышал: «{text}»")
    await consult_text(update, context, text)


# ── Живая передача менеджеру (режим оператора) ───────────────────────────────

def _operators(context) -> set:
    return context.bot_data.setdefault("operators", set())


def _relay_map(context) -> dict:
    return context.bot_data.setdefault("relay", {})


async def start_operator(update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str = "") -> None:
    msg = update.effective_message
    if not effective_sales_chat():
        await msg.reply_text(
            f"Чат менеджера сейчас недоступен. Позвоните диспетчеру: {SALES_PHONE_DISPLAY} "
            "или оставьте заявку кнопкой ниже.",
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
        sent = await context.bot.send_message(effective_sales_chat(), header)
        _relay_map(context)[sent.message_id] = user.id
    except Exception as exc:
        logger.error("sales notify failed: %s", exc)
        _operators(context).discard(user.id)
        await msg.reply_text(
            f"Не удалось подключить чат менеджера. Позвоните: {SALES_PHONE_DISPLAY} "
            "или оставьте заявку 👇",
            reply_markup=client_keyboard(),
        )
        return
    await msg.reply_text("✅ Передал менеджеру отдела продаж — скоро ответит. Пишите прямо здесь.")


async def call_manager(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await start_operator(update, context)


async def call_manager_from_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Прервать оформление и переключить клиента на живого менеджера."""
    await call_manager(update, context)
    return ConversationHandler.END


async def relay_to_sales(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str | None = None
) -> None:
    user = update.effective_user
    text = text if text is not None else update.message.text
    try:
        sent = await context.bot.send_message(effective_sales_chat(), f"💬 {user.first_name} (id {user.id}): {text}")
        _relay_map(context)[sent.message_id] = user.id
    except Exception as exc:
        logger.error("relay to sales failed: %s", exc)


def _client_target_from_reply(context, reply_to) -> Optional[tuple[str, int]]:
    """Площадка и id клиента из карты или текста сообщения отдела продаж."""
    max_match = re.search(r"max_id\s+(\d+)", reply_to.text or reply_to.caption or "", re.IGNORECASE)
    if max_match:
        return "max", int(max_match.group(1))
    cid = _relay_map(context).get(reply_to.message_id)
    if cid:
        return "telegram", cid
    m = re.search(r"id\s+(\d+)", reply_to.text or reply_to.caption or "")
    return ("telegram", int(m.group(1))) if m else None


async def sales_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply_to = update.message.reply_to_message
    if not reply_to:
        return
    # отвечаем только на сообщения бота (карточки/реле), не на чужие
    if not (reply_to.from_user and reply_to.from_user.id == context.bot.id):
        return
    target = _client_target_from_reply(context, reply_to)
    if not target:
        return
    platform, client_id = target
    text = (update.message.text or "").strip()
    if text == "/end":
        if platform == "max":
            from bot_max import main as max_bot

            await max_bot.end_manager_chat(client_id)
        else:
            _operators(context).discard(client_id)
            try:
                await context.bot.send_message(
                    client_id,
                    "Менеджер завершил диалог. Спросите ещё что-нибудь или оформите заказ 👇",
                    reply_markup=client_keyboard(),
                )
            except Exception:
                pass
        await update.message.reply_text("Диалог с клиентом завершён.")
        return
    try:
        if platform == "max":
            from bot_max import main as max_bot

            await max_bot.send_to_max_user(client_id, f"👨‍💼 Менеджер: {text}")
        else:
            await context.bot.send_message(client_id, f"👨‍💼 Менеджер: {text}")
    except Exception as exc:
        logger.error("sales_reply deliver failed: %s", exc)


async def remember_sales_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запомнить id группы отдела продаж из любого сообщения в ней.

    Делает доставку карточек устойчивой к апгрейду группы в супергруппу (id меняется)
    и к незаданному/устаревшему SALES_CHAT_ID: как только в группе появляется сообщение,
    бот берёт актуальный id.
    """
    msg = update.effective_message
    chat = update.effective_chat
    if msg is not None and getattr(msg, "migrate_to_chat_id", None):
        _save_detected_sales_chat(msg.migrate_to_chat_id)
        logger.info("sales chat migrated to supergroup: %s", msg.migrate_to_chat_id)
        return
    if chat is not None and chat.type in ("group", "supergroup") and chat.id != effective_sales_chat():
        _save_detected_sales_chat(chat.id)
        logger.info("sales chat id detected: %s", chat.id)


# ── Оформление заказа ────────────────────────────────────────────────────────

async def order_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    prefill = context.user_data.get("prefill") or {}
    _operators(context).discard(update.effective_user.id)
    context.user_data.clear()
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


async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начать новый заказ командой /order в любой момент."""
    _operators(context).discard(update.effective_user.id)
    context.user_data.clear()
    await update.effective_message.reply_text(
        "Начинаем новый заказ. Выберите марку бетона:",
        reply_markup=grades_keyboard(),
    )
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
    context.user_data["manual_phone_required"] = True
    await update.message.reply_text(
        "Введите номер телефона цифрами вручную, например: 8 923 123-45-67. "
        "Автоматическая отправка контакта отключена.",
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
        await update.message.reply_text(
            "Контакт не принимаю. Введите номер телефона цифрами вручную, например: "
            "8 923 123-45-67."
        )
        return PHONE
    phone = _manual_phone(update.message.text or "")
    name = update.effective_user.first_name or "Клиент"
    if not phone:
        await update.message.reply_text("Похоже, номер неполный. Введите его цифрами вручную.")
        return PHONE

    context.user_data.pop("manual_phone_required", None)
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

    if effective_sales_chat():
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
            await context.bot.send_message(effective_sales_chat(), "\n".join(rows), parse_mode="HTML")
        except Exception as exc:
            logger.error("sales card failed: %s", exc)

    context.user_data.clear()
    await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(
        "Можно сразу оформить ещё один заказ или продолжить общение 👇",
        reply_markup=client_keyboard(),
    )
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


# ── AI-заказ: телефон вручную → лид (без ConversationHandler) ────────────────

async def ai_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Автоматические контакты отключены: просим ручной ввод номера."""
    if not context.user_data.get("ai_order"):
        return
    await update.message.reply_text(
        "Введите номер телефона цифрами вручную, например: 8 923 123-45-67."
    )


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

    await send_sales_card(order, q, name, phone, source="бота (AI)")

    context.user_data.clear()
    await update.message.reply_text(txt, reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(
        "Можно сразу оформить ещё один заказ или задать новый вопрос 👇",
        reply_markup=client_keyboard(),
    )


# ── Счета (встроенный генератор PDF со счётом и QR) ───────────────────────────

INVOICE_HELP = (
    "🧾 Режим счёта.\n\n"
    "Пришлите одним сообщением ИНН покупателя и позиции (по одной в строке):\n\n"
    "Инн 5405042760\n"
    "Бетон М300 6м3 7200\n"
    "Услуги доставки 1 6000\n\n"
    "Название организации, КПП и адрес подтянутся по ИНН автоматически.\n"
    "Продавца можно сменить первой строкой, напр.: «Организация: Пульсар».\n"
    "Выйти из режима счёта — /start."
)


async def invoice_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["invoice_mode"] = True
    await update.message.reply_text(INVOICE_HELP)


async def handle_invoice_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    try:
        from invoice_generator import company, service
    except Exception as exc:  # noqa: BLE001 — отсутствие зависимостей не должно ронять бота
        logger.error("invoice deps missing: %s", exc)
        await update.message.reply_text("Счета временно недоступны. Сообщите менеджеру.")
        return
    if not company.invoices_enabled():
        await update.message.reply_text("Реквизиты организации ещё не настроены. Сообщите менеджеру.")
        return
    try:
        parsed = service.parse_invoice(text)
    except ValueError as err:
        await update.message.reply_text(f"Не смог разобрать счёт: {err}\n\n{INVOICE_HELP}")
        return
    # Название/КПП/адрес покупателя по ИНН (DaData), если не заданы текстом
    if not parsed.buyer.name:
        try:
            from invoice_generator.dadata import find_party_by_inn
            found = await find_party_by_inn(parsed.buyer.inn)
        except Exception as exc:  # noqa: BLE001
            logger.error("dadata lookup failed: %s", exc)
            found = None
        if found:
            parsed.buyer = found
        else:
            await update.message.reply_text(
                "Не нашёл организацию по ИНН. Добавьте строки «Покупатель:», «КПП:», «Адрес:».")
            return
    await update.message.chat.send_action("upload_document")
    try:  # reportlab синхронный — уводим в поток, чтобы не блокировать event loop
        result = await asyncio.to_thread(service.generate_invoice, parsed)
    except Exception as exc:  # noqa: BLE001
        logger.error("invoice generate failed: %s", exc)
        await update.message.reply_text("Ошибка при формировании счёта. Попробуйте ещё раз.")
        return
    if result is None:
        await update.message.reply_text("Реквизиты организации не настроены. Сообщите менеджеру.")
        return
    pdf_path = Path(result.pdf_path)
    caption = f"Счёт №{result.invoice_number} на сумму {result.total_amount} ₽"
    try:
        with pdf_path.open("rb") as doc:
            await update.message.reply_document(document=doc, filename=pdf_path.name, caption=caption)
    except Exception as exc:  # noqa: BLE001
        logger.error("invoice send failed: %s", exc)
        await update.message.reply_text("Счёт создан, но не отправился. Попробуйте ещё раз.")
        return
    if effective_sales_chat():  # копия в отдел продаж
        try:
            with pdf_path.open("rb") as doc:
                await context.bot.send_document(
                    effective_sales_chat(), document=doc, filename=pdf_path.name,
                    caption=f"🧾 {caption}\nПокупатель: {parsed.buyer.name} (ИНН {parsed.buyer.inn})")
        except Exception as exc:  # noqa: BLE001
            logger.error("invoice sales copy failed: %s", exc)


# ── Сборка и запуск (в backend-процессе) ─────────────────────────────────────

def create_bot() -> Optional[Application]:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN не задан — клиентский бот отключён")
        return None

    builder = Application.builder().token(settings.TELEGRAM_BOT_TOKEN)
    proxy_url = os.getenv("TELEGRAM_PROXY_URL", "").strip()
    if proxy_url:
        builder = builder.proxy(proxy_url).get_updates_proxy(proxy_url)
    app = builder.build()

    order_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(order_entry, pattern=r"^order$"),
            CommandHandler("order", order_command),
        ],
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
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", restart),
            CommandHandler("ai", ai_chat_entry),
            CallbackQueryHandler(restart_callback, pattern=r"^restart$"),
            CallbackQueryHandler(ai_chat_entry, pattern=r"^ai_chat$"),
            CallbackQueryHandler(show_contacts, pattern=r"^contacts$"),
            CallbackQueryHandler(call_manager_from_order, pattern=r"^human$"),
        ],
        allow_reentry=True,
    )

    app.add_handler(order_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ai", ai_chat_entry))
    app.add_handler(CommandHandler("schet", invoice_start))
    app.add_handler(CommandHandler("invoice", invoice_start))
    app.add_handler(CallbackQueryHandler(restart_callback, pattern=r"^restart$"))
    app.add_handler(CallbackQueryHandler(ai_chat_entry, pattern=r"^ai_chat$"))
    app.add_handler(CallbackQueryHandler(show_contacts, pattern=r"^contacts$"))
    app.add_handler(CallbackQueryHandler(call_manager, pattern=r"^human$"))
    # Ответ менеджера из группы: любой reply в группе на сообщение бота (не зависит
    # от точного SALES_CHAT_ID — устойчиво к смене id при апгрейде в супергруппу).
    app.add_handler(MessageHandler(
        (~filters.ChatType.PRIVATE) & filters.REPLY & filters.TEXT, sales_reply))
    # AI-заказ: контакт (телефон) в личке вне оформления → создать лид
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.CONTACT, ai_contact))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.VOICE, voice_message))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, consult))
    # Отдельная группа хендлеров: запомнить id группы отдела продаж (в т.ч. миграцию
    # в супергруппу). group=1 — выполняется независимо от остальных обработчиков.
    app.add_handler(MessageHandler(~filters.ChatType.PRIVATE, remember_sales_chat), group=1)
    app.add_handler(MessageHandler(filters.StatusUpdate.MIGRATE, remember_sales_chat), group=1)

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
        try:
            await telegram_app.bot.set_my_commands([
                BotCommand("start", "Главное меню / начать заново"),
                BotCommand("order", "Оформить новый заказ"),
                BotCommand("ai", "Помощь с расчётом"),
                BotCommand("cancel", "Отменить текущее оформление"),
            ])
        except Exception as exc:
            logger.warning("Telegram commands setup failed: %s", exc)
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
