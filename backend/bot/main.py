"""Telegram bot for lead capture and simple admin control panel."""

import asyncio
import logging
from typing import Optional

import httpx
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import settings
from services.amocrm import AmoCRMService
from services.baserow import BaserowService
from services.notifier import TelegramNotifier

logger = logging.getLogger(__name__)

AWAITING_NAME = 1
AWAITING_VOLUME = 2
AWAITING_GRADE = 3
AWAITING_ADDRESS = 4
AWAITING_DATE = 5
AWAITING_PAYMENT = 6
AWAITING_PHONE = 7

GRADES_KB = ReplyKeyboardMarkup(
    [["М100", "М150", "М200"], ["М250", "М300", "М350"], ["М400", "М450"]],
    resize_keyboard=True,
)
URGENCY_KB = ReplyKeyboardMarkup(
    [["Сегодня", "Завтра"], ["На неделе", "Не срочно"]],
    resize_keyboard=True,
)
PAYMENT_KB = ReplyKeyboardMarkup(
    [["Наличные", "Безналичный расчёт"], ["Перевод на карту"]],
    resize_keyboard=True,
)
USER_MENU_KB = ReplyKeyboardMarkup([["Оставить заявку"], ["Помощь"]], resize_keyboard=True)
ADMIN_MENU_KB = ReplyKeyboardMarkup(
    [["Оставить заявку", "Последние лиды"], ["Статистика", "Статус системы"], ["Помощь"]],
    resize_keyboard=True,
)

amocrm = AmoCRMService()
storage = BaserowService()
notifier = TelegramNotifier()

telegram_app: Optional[Application] = None
polling_task: Optional[asyncio.Task] = None


def is_admin(user_id: int) -> bool:
    return bool(settings.TELEGRAM_ADMIN_ID and user_id == settings.TELEGRAM_ADMIN_ID)


def main_menu(user_id: int) -> ReplyKeyboardMarkup:
    return ADMIN_MENU_KB if is_admin(user_id) else USER_MENU_KB


def format_lead_row(lead: dict) -> str:
    created_at = (lead.get("created_at") or "").replace("T", " ")[:16]
    return (
        f"#{lead.get('id', '?')} | {lead.get('name', 'Без имени')}\n"
        f"Телефон: {lead.get('phone', 'не указан')}\n"
        f"Источник: {lead.get('source', 'unknown')}\n"
        f"Объем: {lead.get('volume') or '-'} м3\n"
        f"Марка: {lead.get('concrete_grade') or '-'}\n"
        f"Время: {created_at or '-'}"
    )


async def send_main_menu(update: Update, text: str):
    await update.message.reply_text(
        text,
        reply_markup=main_menu(update.effective_user.id),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        await update.message.reply_text(
            "Пульт управления подключен.\n\n"
            "Доступно:\n"
            "- Последние лиды\n"
            "- Статистика\n"
            "- Статус системы\n"
            "- Оставить заявку\n\n"
            "Можно использовать кнопки ниже или команды /leads, /stats, /status.",
            reply_markup=ADMIN_MENU_KB,
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Здравствуйте! Я помогу оформить заявку на бетон с доставкой.\n\n"
        "Нажмите «Оставить заявку» или используйте команду /new.",
        reply_markup=USER_MENU_KB,
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Команды:\n"
        "/start - открыть меню\n"
        "/new - оставить заявку\n"
        "/cancel - отменить текущий диалог\n"
    )
    if is_admin(update.effective_user.id):
        text += "/leads - последние лиды\n/stats - сводка\n/status - статус системы\n"
    await update.message.reply_text(text, reply_markup=main_menu(update.effective_user.id))


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Эта команда доступна только администратору.")
        return

    text = (
        "Статус системы:\n"
        f"- amoCRM: {'ok' if amocrm.is_available() else 'not configured'}\n"
        f"- Storage: {'ok' if storage.is_available() else 'error'}\n"
        f"- Telegram notifications: {'ok' if notifier.is_available() else 'not configured'}\n"
        f"- Backend URL: {settings.BACKEND_URL}"
    )
    await update.message.reply_text(text, reply_markup=ADMIN_MENU_KB)


async def leads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Эта команда доступна только администратору.")
        return

    leads = storage.get_leads(limit=5)
    if not leads:
        await update.message.reply_text("Лидов пока нет.", reply_markup=ADMIN_MENU_KB)
        return

    chunks = ["Последние лиды:"]
    for lead in leads:
        chunks.append(format_lead_row(lead))
    await update.message.reply_text("\n\n".join(chunks), reply_markup=ADMIN_MENU_KB)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Эта команда доступна только администратору.")
        return

    stats = storage.get_dashboard_stats()
    sources = stats.get("sources") or []
    source_text = "\n".join(
        f"- {item['source']}: {item['cnt']}" for item in sources[:8]
    ) or "- нет данных"

    latest = stats.get("latest")
    latest_text = (
        f"\n\nПоследний лид: {latest.get('name', 'Без имени')} | {latest.get('phone', '-')}"
        if latest
        else ""
    )

    text = (
        "Сводка по лидам:\n"
        f"- Всего: {stats.get('total', 0)}\n"
        f"- Сегодня: {stats.get('today', 0)}\n"
        f"- За 7 дней: {stats.get('week', 0)}\n\n"
        "Источники за 7 дней:\n"
        f"{source_text}{latest_text}"
    )
    await update.message.reply_text(text, reply_markup=ADMIN_MENU_KB)


async def start_lead_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Как вас зовут?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return AWAITING_NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "Какой объем бетона нужен (в м3)?\nНапример: 5 или 7.5"
    )
    return AWAITING_VOLUME


async def get_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Введите число. Например: 5")
        return AWAITING_VOLUME

    context.user_data["volume"] = volume
    await update.message.reply_text("Выберите марку бетона:", reply_markup=GRADES_KB)
    return AWAITING_GRADE


async def get_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["concrete_grade"] = update.message.text.strip()
    await update.message.reply_text("Укажите адрес доставки:", reply_markup=ReplyKeyboardRemove())
    return AWAITING_ADDRESS


async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text.strip()
    await update.message.reply_text("Когда нужна доставка?", reply_markup=URGENCY_KB)
    return AWAITING_DATE


async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["delivery_date"] = update.message.text.strip()
    await update.message.reply_text(
        "Какой способ оплаты предпочитаете?",
        reply_markup=PAYMENT_KB,
    )
    return AWAITING_PAYMENT


async def get_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["payment_method"] = update.message.text.strip()
    await update.message.reply_text("Ваш телефон для связи:", reply_markup=ReplyKeyboardRemove())
    return AWAITING_PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text.strip()

    payload = {
        "lead_data": {
            "name": context.user_data.get("name"),
            "phone": context.user_data.get("phone"),
            "concrete_grade": context.user_data.get("concrete_grade"),
            "volume": context.user_data.get("volume"),
            "address": context.user_data.get("address"),
            "delivery_date": context.user_data.get("delivery_date"),
            "payment_method": context.user_data.get("payment_method"),
            "source": "telegram",
            "comment": f"telegram_user={update.effective_user.id}",
        }
    }

    backend_url = f"{settings.BACKEND_URL}/webhooks/telegram"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(backend_url, json=payload)
            result = response.json()

        if response.ok and result.get("status") == "duplicate":
            text = "Вы уже оставляли заявку. Мы свяжемся с вами в ближайшее время."
        elif response.ok and result.get("status") == "success":
            text = "Заявка принята. Перезвоним за 5 минут для уточнения деталей."
        else:
            text = "Данные приняты, но при обработке возникла задержка. Мы свяжемся с вами вручную."
    except Exception as e:
        logger.error(f"Telegram bot lead send failed: {e}")
        text = "Данные приняты. Мы свяжемся с вами вручную."

    context.user_data.clear()
    await update.message.reply_text(text, reply_markup=main_menu(update.effective_user.id))
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Диалог отменен.",
        reply_markup=main_menu(update.effective_user.id),
    )
    return ConversationHandler.END


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if text == "Оставить заявку":
        return await start_lead_flow(update, context)
    if text == "Последние лиды":
        await leads_command(update, context)
        return ConversationHandler.END
    if text == "Статистика":
        await stats_command(update, context)
        return ConversationHandler.END
    if text == "Статус системы":
        await status_command(update, context)
        return ConversationHandler.END
    if text == "Помощь":
        await help_command(update, context)
        return ConversationHandler.END

    await update.message.reply_text(
        "Используйте кнопки меню или /help.",
        reply_markup=main_menu(update.effective_user.id),
    )
    return ConversationHandler.END


def create_bot() -> Optional[Application]:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token is not configured")
        return None

    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("new", start_lead_flow),
            MessageHandler(filters.Regex("^Оставить заявку$"), start_lead_flow),
        ],
        states={
            AWAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AWAITING_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_volume)],
            AWAITING_GRADE: [
                MessageHandler(filters.Regex("^(М100|М150|М200|М250|М300|М350|М400|М450)$"), get_grade)
            ],
            AWAITING_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
            AWAITING_DATE: [
                MessageHandler(filters.Regex("^(Сегодня|Завтра|На неделе|Не срочно)$"), get_date)
            ],
            AWAITING_PAYMENT: [
                MessageHandler(filters.Regex("^(Наличные|Безналичный расчёт|Перевод на карту)$"), get_payment)
            ],
            AWAITING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("leads", leads_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_router))

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
        logger.info("Telegram bot started")
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
            logger.info("Telegram bot stopped")
        except Exception as e:
            logger.error(f"Telegram bot stop failed: {e}")
        telegram_app = None
