"""
Единый клиентский бот заказа бетона «Бетон Экспресс» — ГИБРИД (AI + кнопки).

Два режима:
  • Консультация (свободный чат) — клиент пишет как человеку, AI-продавец (Claude на
    backend, /api/ai/chat) объясняет марки/фундаменты, считает объём по размерам,
    ориентирует по цене и доводит до заказа. Персональные данные СЮДА НЕ идут.
  • Оформление заказа (кнопки) — существующий структурированный поток:
    марка → объём → адрес → /api/quote → дата → оплата → телефон(кнопка) → CRM.

Вешается на QR / ссылку. Единственный клиентский бот (@otdprod_bot — только админ).

Запуск:  python bot.py
Нужны env: CLIENT_BOT_TOKEN, BACKEND_URL (см. .env.example)
"""

import logging
import os

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
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("CLIENT_BOT_TOKEN", "")
BACKEND_URL = os.getenv("BACKEND_URL", "https://beton-backend-wr3w.onrender.com").rstrip("/")
# Группа отдела продаж (добавьте бота в группу и укажите её chat_id, обычно отрицательный)
SALES_CHAT_ID = int(os.getenv("SALES_CHAT_ID", "0") or 0)

GRADES = ["М100", "М150", "М200", "М250", "М300", "М350", "М400", "М450"]

DATE_TO_URGENCY = {"Сегодня": "today", "Завтра": "normal", "На неделе": "normal", "Не срочно": "normal"}

# Состояния диалога ОФОРМЛЕНИЯ (консультация — вне диалога)
VOLUME, ADDRESS, DATE, PAYMENT, PHONE = range(5)

AI_HISTORY_MAX = 20


# ── Клавиатуры ───────────────────────────────────────────────────────────────

def client_keyboard() -> InlineKeyboardMarkup:
    """Кнопки под сообщениями клиенту: оформить заказ / позвать менеджера."""
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
    """Свободный чат с AI-продавцом (вне режима оформления)."""
    # Режим оператора: сообщения клиента идут живому менеджеру, не в AI.
    if update.effective_user.id in _operators(context):
        await relay_to_sales(update, context)
        return

    text = update.message.text.strip()
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
        # ограничиваем историю
        del history[:-AI_HISTORY_MAX]

    if action.get("type") == "start_order":
        context.user_data["prefill"] = {"grade": action.get("grade"), "volume": action.get("volume")}
        if reply:
            await update.message.reply_text(reply)
        await update.message.reply_text("Готов оформить — нажмите кнопку 👇", reply_markup=client_keyboard())
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
    """Подключить живого менеджера: уведомить группу отдела продаж, включить реле."""
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
    """Кнопка «Позвать менеджера»."""
    await update.callback_query.answer()
    await start_operator(update, context)


async def relay_to_sales(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сообщение клиента в режиме оператора → в группу отдела продаж."""
    user = update.effective_user
    text = update.message.text
    try:
        sent = await context.bot.send_message(SALES_CHAT_ID, f"💬 {user.first_name} (id {user.id}): {text}")
        _relay_map(context)[sent.message_id] = user.id
    except Exception as exc:
        logger.error("relay to sales failed: %s", exc)


async def sales_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ответ менеджера в группе (reply) → клиенту. «/end» завершает диалог."""
    reply_to = update.message.reply_to_message
    if not reply_to:
        return
    client_id = _relay_map(context).get(reply_to.message_id)
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
        # Ответы клиента снова придут в группу через relay_to_sales (новые сообщения),
        # поэтому карту reply тут не трогаем.
    except Exception as exc:
        logger.error("sales_reply deliver failed: %s", exc)


# ── Оформление заказа (структурированный поток) ──────────────────────────────

async def order_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Вход в оформление по кнопке. Марка/объём предзаполняются из консультации."""
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
    calc = q.get("calculation", {})
    grade = ud["grade"]
    volume = ud["volume"]
    lines = ["<b>Расчёт заказа</b>", f"Бетон {grade}, {volume:g} м³"]

    if q.get("address_found"):
        km = q.get("distance_km")
        lines.append(f"Адрес: {q.get('matched_address', ud['address'])}")
        if km is not None:
            lines.append(f"Плечо доставки: ~{km:g} км")
        if not q.get("deliverable"):
            lines.append("⚠️ Адрес далеко — доставку подтвердит менеджер.")
    else:
        lines.append("Адрес не распознали автоматически — уточнит менеджер.")

    beton = calc.get("beton_cost")
    delivery = calc.get("delivery_cost")
    total = calc.get("total")
    if beton is not None:
        lines.append(f"\nБетон: {int(beton):,} ₽".replace(",", " "))
    if delivery is not None:
        lines.append(f"Доставка: {int(delivery):,} ₽".replace(",", " "))
    if total is not None:
        lines.append(f"<b>Итого: {int(total):,} ₽</b>".replace(",", " "))
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
    calc = quote.get("calculation", {})
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
            "calculated_amount": calc.get("total"),
            "comment": f"Заявка из клиентского Telegram-бота (tg_user={update.effective_user.id})",
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

    # Карточка заявки в группу отдела продаж
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
        ]
        if calc.get("total"):
            rows.append(f"Сумма (ориент.): {int(calc['total']):,} ₽".replace(",", " "))
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
    """/start во время оформления — сбрасываем и выходим из диалога."""
    await start(update, context)
    return ConversationHandler.END


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("CLIENT_BOT_TOKEN не задан. См. .env.example")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

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

    # Порядок важен: сначала диалог оформления (перехватывает /start только когда
    # клиент внутри оформления — через fallback), затем /start вне оформления,
    # кнопка «Позвать менеджера», ответы менеджеров из группы, и последним —
    # свободный текст в личке → AI-консультация (или реле оператора).
    app.add_handler(order_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(call_manager, pattern=r"^human$"))
    if SALES_CHAT_ID:
        app.add_handler(MessageHandler(
            filters.Chat(SALES_CHAT_ID) & filters.REPLY & filters.TEXT, sales_reply))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, consult))

    logger.info("🤖 Клиентский AI-бот заказа бетона запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
