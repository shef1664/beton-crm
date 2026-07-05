"""
Единый клиентский бот заказа бетона «Бетон Экспресс».

Вешается на QR-код / ссылку в рекламе. Это ЕДИНСТВЕННЫЙ клиентский бот
(внутренний @otdprod_bot остаётся только для админа и уведомлений).

Сценарий:
  1. /start → выбор марки (кнопки М100…М450)
  2. объём в м³
  3. адрес доставки  → backend POST /api/quote (цена + доставка по адресу,
     бесплатный геокодинг Nominatim/DaData + OSRM) → показ стоимости
  4. когда нужна доставка (Сегодня / Завтра / На неделе / Не срочно)
  5. способ оплаты (Наличные / Безнал / Перевод на карту)
  6. телефон (кнопка «отправить контакт»)
        → backend POST /webhooks/telegram → полный пайплайн:
          антидубль → автоматизация продаж → AmoCRM + SQLite + Telegram + Notion

Бот тонкий: логика цены и геокодинга — на backend. Здесь только диалог.

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

GRADES = ["М100", "М150", "М200", "М250", "М300", "М350", "М400", "М450"]

# Варианты даты доставки → значение urgency для автоматики воронки.
# «Сегодня» = today → sales_automation поднимает приоритет (hot_urgency_values).
DATE_OPTIONS = ["Сегодня", "Завтра", "На неделе", "Не срочно"]
DATE_TO_URGENCY = {
    "Сегодня": "today",
    "Завтра": "normal",
    "На неделе": "normal",
    "Не срочно": "normal",
}
PAYMENT_OPTIONS = ["Наличные", "Безналичный расчёт", "Перевод на карту"]

# Состояния диалога
VOLUME, ADDRESS, DATE, PAYMENT, PHONE = range(5)


def grades_keyboard() -> InlineKeyboardMarkup:
    """Кнопки выбора марки — по 2 в ряд."""
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
    return ReplyKeyboardMarkup(
        [["Сегодня", "Завтра"], ["На неделе", "Не срочно"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def payment_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["Наличные", "Безналичный расчёт"], ["Перевод на карту"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    btn = KeyboardButton("📱 Отправить мой номер", request_contact=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Здравствуйте! Это бот заказа бетона «Бетон Экспресс», Кемерово.\n\n"
        "Рассчитаю стоимость с доставкой за минуту.\n\n"
        "1️⃣ Выберите марку бетона:",
        reply_markup=grades_keyboard(),
    )
    return VOLUME


async def choose_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    grade = query.data.split(":", 1)[1]
    context.user_data["grade"] = grade
    await query.edit_message_text(
        f"Марка: {grade} ✅\n\n2️⃣ Сколько кубов нужно? Напишите число (м³), например: 6"
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
        "3️⃣ Напишите адрес доставки (город, улица, дом), например:\n"
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

    await update.message.reply_text(
        "4️⃣ Когда нужна доставка?", reply_markup=date_keyboard()
    )
    return DATE


async def enter_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip()
    context.user_data["delivery_date"] = choice
    context.user_data["urgency"] = DATE_TO_URGENCY.get(choice, "normal")
    await update.message.reply_text(
        "5️⃣ Способ оплаты?", reply_markup=payment_keyboard()
    )
    return PAYMENT


async def enter_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["payment_method"] = update.message.text.strip()
    await update.message.reply_text(
        "6️⃣ Оставьте номер телефона — менеджер подтвердит заказ и время доставки 👇",
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

    await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Отменил. Напишите /start, чтобы рассчитать заново.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("CLIENT_BOT_TOKEN не задан. См. .env.example")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
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
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    logger.info("🤖 Клиентский бот заказа бетона запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
