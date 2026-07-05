"""Telegram admin control panel for @otdprod_bot (notifications + admin commands).

Клиентский приём заявок вынесен в отдельный бот `client_bot/` (под QR-код).
Здесь остаётся только пульт администратора: последние лиды, статистика, статус.
"""

import asyncio
import logging
from typing import Optional

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import settings
from services.amocrm import AmoCRMService
from services.baserow import BaserowService
from services.notifier import TelegramNotifier

logger = logging.getLogger(__name__)

USER_MENU_KB = ReplyKeyboardMarkup([["Помощь"]], resize_keyboard=True)
ADMIN_MENU_KB = ReplyKeyboardMarkup(
    [["Последние лиды", "Статистика"], ["Статус системы", "Помощь"]],
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
            "- Статус системы\n\n"
            "Можно использовать кнопки ниже или команды /leads, /stats, /status.",
            reply_markup=ADMIN_MENU_KB,
        )
        return

    await update.message.reply_text(
        "Здравствуйте! Это служебный бот компании «Бетон Экспресс».\n\n"
        "Чтобы рассчитать стоимость и оставить заявку на бетон, воспользуйтесь "
        "нашим ботом заказа (ссылка/QR на сайте и в рекламе).",
        reply_markup=USER_MENU_KB,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Команды:\n/start - открыть меню\n"
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


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if text == "Последние лиды":
        await leads_command(update, context)
        return
    if text == "Статистика":
        await stats_command(update, context)
        return
    if text == "Статус системы":
        await status_command(update, context)
        return
    if text == "Помощь":
        await help_command(update, context)
        return

    await update.message.reply_text(
        "Используйте кнопки меню или /help.",
        reply_markup=main_menu(update.effective_user.id),
    )


def create_bot() -> Optional[Application]:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token is not configured")
        return None

    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("leads", leads_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("status", status_command))
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
