"""Telegram бот @otdprod - сбор заявок на бетон"""
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import settings

logger = logging.getLogger(__name__)

# Состояния диалога
AWAITING_NAME = 1
AWAITING_VOLUME = 2
AWAITING_GRADE = 3
AWAITING_ADDRESS = 4
AWAITING_DATE = 5
AWAITING_URGENCY = 6
AWAITING_PAYMENT = 7
AWAITING_PHONE = 8

# Клавиатуры
GRADES_KB = ReplyKeyboardMarkup([
    ["М100", "М150", "М200"],
    ["М250", "М300", "М350"],
    ["М400", "М450"]
], resize_keyboard=True)

URGENCY_KB = ReplyKeyboardMarkup([
    ["Сегодня", "Завтра"],
    ["На неделе", "Не срочно"]
], resize_keyboard=True)

PAYMENT_KB = ReplyKeyboardMarkup([
    ["Наличные", "Безналичный расчёт"],
    ["Перевод на карту"]
], resize_keyboard=True)

# Хранение данных пользователя
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога"""
    await update.message.reply_text(
        "👋 Здравствуйте! Я помогу рассчитать стоимость бетона с доставкой.\n\n"
        "Как вас зовут?",
        reply_markup=ReplyKeyboardRemove()
    )
    return AWAITING_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение имени"""
    context.user_data["name"] = update.message.text
    user_data[update.message.from_user.id] = context.user_data
    
    await update.message.reply_text(
        "📦 Какой объём бетона нужен (в м³)?\n"
        "Например: 5 или 7.5"
    )
    return AWAITING_VOLUME

async def get_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение объёма"""
    try:
        volume = float(update.message.text.replace(",", "."))
        context.user_data["volume"] = volume
    except ValueError:
        await update.message.reply_text("❌ Введите число. Например: 5")
        return AWAITING_VOLUME
    
    await update.message.reply_text(
        "🏗 Выберите марку бетона:",
        reply_markup=GRADES_KB
    )
    return AWAITING_GRADE

async def get_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение марки бетона"""
    context.user_data["concrete_grade"] = update.message.text
    
    await update.message.reply_text(
        "📍 Укажите адрес доставки:",
        reply_markup=ReplyKeyboardRemove()
    )
    return AWAITING_ADDRESS

async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение адреса"""
    context.user_data["address"] = update.message.text
    
    await update.message.reply_text(
        "📅 Когда нужна доставка?",
        reply_markup=URGENCY_KB
    )
    return AWAITING_DATE

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение даты"""
    context.user_data["delivery_date"] = update.message.text
    
    await update.message.reply_text(
        "💳 Какой способ оплаты предпочитаете?",
        reply_markup=PAYMENT_KB
    )
    return AWAITING_PAYMENT

async def get_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение способа оплаты"""
    context.user_data["payment_method"] = update.message.text
    
    await update.message.reply_text("📞 Ваш телефон для связи:")
    return AWAITING_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение телефона и отправка данных"""
    phone = update.message.text
    context.user_data["phone"] = phone
    
    # Отправка данных на backend
    import httpx
    backend_url = f"{settings.BACKEND_URL}/webhooks/telegram"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                backend_url,
                json={
                    "lead_data": {
                        "name": context.user_data.get("name"),
                        "phone": phone,
                        "concrete_grade": context.user_data.get("concrete_grade"),
                        "volume": context.user_data.get("volume"),
                        "address": context.user_data.get("address"),
                        "delivery_date": context.user_data.get("delivery_date"),
                        "payment_method": context.user_data.get("payment_method"),
                        "source": "telegram"
                    }
                }
            )
            
            result = response.json()
            
            if result.get("status") == "duplicate":
                await update.message.reply_text(
                    "✅ Вы уже оставляли заявку!\n\n"
                    "Мы свяжемся с вами в ближайшее время."
                )
            else:
                await update.message.reply_text(
                    "✅ Заявка принята!\n\n"
                    "📞 Перезвоним за 5 минут для уточнения деталей.\n\n"
                    "Спасибо за обращение!"
                )
                
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        await update.message.reply_text(
            "✅ Данные приняты! Мы свяжемся с вами."
        )
    
    return 0

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена диалога"""
    await update.message.reply_text(
        "❌ Диалог отменён.\n\n"
        "Напишите /start чтобы начать заново."
    )
    return 0

def create_bot() -> Application:
    """Создание бота"""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("Токен бота не задан")
        return None
    
    # Создание приложения
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    
    # Добавление обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    
    # Обработчики сообщений
    app.add_handler(MessageHandler(filters.Regex("^(М100|М150|М200|М250|М300|М350|М400|М450)$"), get_grade))
    app.add_handler(MessageHandler(filters.Regex("^(Сегодня|Завтра|На неделе|Не срочно)$"), get_date))
    app.add_handler(MessageHandler(filters.Regex("^(Наличные|Безналичный расчёт|Перевод на карту)$"), get_payment))
    
    return app

async def start_bot():
    """Запуск бота"""
    app = create_bot()
    if not app:
        return
    
    logger.info("🤖 Запуск Telegram бота @otdprod...")
    
    await app.initialize()
    await app.start()
    
    # Polling loop
    offset = None
    while True:
        try:
            updates = await app.bot.get_updates(offset=offset, timeout=30)
            for update in updates:
                offset = update.update_id + 1
                await app.process_update(update)
        except Exception as e:
            logger.error(f"Ошибка polling: {e}")
            await asyncio.sleep(5)
