"""
Клиентский бот заказа бетона «Бетон Экспресс».

Сценарий (для QR-кода / ссылки в рекламе):
  1. Клиент открывает бота по ссылке/QR → /start
  2. Выбирает марку бетона (кнопки М100…М450)
  3. Вводит объём в м³
  4. Пишет адрес доставки
  5. Бот считает стоимость + доставку (бесплатный геокодинг на backend)
     и говорит, возможна ли доставка
  6. Клиент оставляет телефон → создаётся лид в CRM (менеджеру летит уведомление)

Бот — тонкий: вся логика цены и геокодинга живёт в backend (/api/quote,
/api/leads/create). Здесь только диалог.

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

# Состояния диалога
VOLUME, ADDRESS, PHONE = range(3)


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
            data = resp.json()
    except Exception as exc:
        logger.error("quote failed: %s", exc)
        await update.message.reply_text(
            "⚠️ Не удалось рассчитать автоматически. Оставьте телефон — менеджер "
            "посчитает вручную и перезвонит.",
            reply_markup=phone_keyboard(),
        )
        return PHONE

    context.user_data["quote"] = data
    await update.message.reply_text(format_quote(context.user_data), parse_mode="HTML")
    await update.message.reply_text(
        "Оставьте номер телефона — менеджер подтвердит заказ и время доставки 👇",
        reply_markup=phone_keyboard(),
    )
    return PHONE


def phone_keyboard() -> ReplyKeyboardMarkup:
    btn = KeyboardButton("📱 Отправить мой номер", request_contact=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)


def format_quote(ud: dict) -> str:
    q = ud["quote"]
    calc = q.get("calculation", {})
    grade = ud["grade"]
    volume = ud["volume"]
    lines = [f"<b>Расчёт заказа</b>", f"Бетон {grade}, {volume:g} м³"]

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
    quote = ud.get("quote", {})
    calc = quote.get("calculation", {})
    lead = {
        "name": name,
        "phone": phone,
        "source": "telegram",
        "source_platform": "telegram",
        "source_channel": "chat",
        "concrete_grade": ud.get("grade"),
        "volume": ud.get("volume"),
        "address": ud.get("address"),
        "distance": quote.get("distance_km"),
        "calculated_amount": calc.get("total"),
        "comment": "Заявка из клиентского Telegram-бота",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(f"{BACKEND_URL}/api/leads/create", json=lead)
            resp.raise_for_status()
    except Exception as exc:
        logger.error("lead create failed: %s", exc)

    await update.message.reply_text(
        "✅ Заявка принята! Менеджер перезвонит в ближайшее время и подтвердит "
        "стоимость и время доставки.\n\nСпасибо, что выбрали «Бетон Экспресс»! 🚛",
        reply_markup=ReplyKeyboardRemove(),
    )
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
            PHONE: [
                MessageHandler(filters.CONTACT, enter_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_phone),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )
    app.add_handler(conv)
    logger.info("🤖 Клиентский бот заказа бетона запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
