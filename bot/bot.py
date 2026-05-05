"""
PULSAR — Telegram-бот + API сервер для MiniApp.
Запуск: python bot.py
"""

import logging
import json
import os
import tempfile
from datetime import datetime
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes

import sheets
import transcribe
from api_server import create_app
from config import BOT_TOKEN, WEBAPP_URL, DIRECTOR_CHAT_ID, API_PORT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROLES = {}

ROLE_LABELS = {
    "driver":    "🚛 Водитель",
    "mechanic":  "🔧 Слесарь",
    "economist": "💰 Экономист",
    "logist":    "🚚 Логист",
    "director":  "📊 Директор",
}

ROLE_DESC = {
    "driver":    "Рейсы · топливо · кабинет",
    "mechanic":  "Ремонты · запчасти · кабинет",
    "economist": "Миксеры · наличные",
    "logist":    "Длинномеры · заказы",
    "director":  "Полный доступ · дашборд",
}


async def notify_director(context, message):
    if DIRECTOR_CHAT_ID:
        try:
            await context.bot.send_message(DIRECTOR_CHAT_ID, message)
        except Exception as e:
            logger.error(f"Ошибка уведомления: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    role = ROLES.get(user.id)
    if not role:
        await update.message.reply_text(
            f"👋 Добрый день, {user.first_name}!\n\n"
            f"Ваш ID: `{user.id}`\n\n"
            f"Для доступа к системе обратитесь к директору.",
            parse_mode="Markdown"
        )
        if DIRECTOR_CHAT_ID:
            await notify_director(context,
                f"🔔 Новый пользователь:\n{user.first_name} {user.last_name or ''}\n"
                f"@{user.username or 'нет'}\nID: `{user.id}`\n\n"
                f"Назначьте роль:\n`/setrole {user.id} driver`",
            )
        return

    label = ROLE_LABELS.get(role, role)
    desc = ROLE_DESC.get(role, "")
    # Cache-busting: добавляем timestamp чтобы Telegram не кэшировал
    cache_key = int(datetime.now().timestamp() // 3600)  # Обновляется каждый час
    webapp_url = f"{WEBAPP_URL}?role={role}&v={cache_key}"
    btn = KeyboardButton(f"📱 Открыть приложение", web_app=WebAppInfo(url=webapp_url))
    kb = ReplyKeyboardMarkup([[btn]], resize_keyboard=True)
    await update.message.reply_text(
        f"👋 {user.first_name}!\n\nРоль: {label}\n{desc}\n\nНажмите кнопку ниже 👇",
        reply_markup=kb
    )


async def setrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != DIRECTOR_CHAT_ID and DIRECTOR_CHAT_ID != 0:
        await update.message.reply_text("❌ Только для директора.")
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /setrole <id> <роль>\n"
            "Роли: driver, mechanic, economist, logist, director\n"
            "Пример: /setrole 123456789 driver"
        )
        return
    target = int(context.args[0])
    role = context.args[1].lower()
    if role not in ROLE_LABELS:
        await update.message.reply_text(f"❌ Неизвестная роль. Доступные: {', '.join(ROLE_LABELS)}")
        return
    ROLES[target] = role
    await update.message.reply_text(f"✅ {ROLE_LABELS[role]} назначен пользователю {target}")
    try:
        await context.bot.send_message(target, f"✅ Вам назначена роль: {ROLE_LABELS[role]}\nНапишите /start")
    except:
        pass


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    role = ROLES.get(u.id, "не назначена")
    await update.message.reply_text(f"👤 {u.first_name}\nID: `{u.id}`\nРоль: {ROLE_LABELS.get(role, role)}", parse_mode="Markdown")


async def roles_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != DIRECTOR_CHAT_ID and DIRECTOR_CHAT_ID != 0:
        await update.message.reply_text("❌ Только для директора.")
        return
    if not ROLES:
        await update.message.reply_text("Ни одной роли не назначено.")
        return
    text = "👥 Пользователи:\n\n" + "\n".join(f"{uid} — {ROLE_LABELS.get(r,r)}" for uid, r in ROLES.items())
    await update.message.reply_text(text)


TG_FILE_LIMIT_MB = 20  # Лимит Bot API на скачивание файла


async def _send_long_text(update: Update, prefix: str, text: str):
    """Отправляет длинный текст, разбивая на куски ≤ 4000 символов."""
    full = (prefix + text) if prefix else text
    chunk_size = 4000
    for i in range(0, len(full), chunk_size):
        await update.message.reply_text(full[i:i + chunk_size])


async def transcribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/transcribe <url> — расшифровать видео по ссылке (YouTube и др.)."""
    if not context.args:
        await update.message.reply_text(
            "Использование: /transcribe <ссылка на видео>\n"
            "Пример: /transcribe https://youtu.be/xxxxx\n\n"
            "Можно также прислать видео или голосовое сообщение — расшифрую автоматически."
        )
        return

    url = context.args[0].strip()
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("⚠️ Нужна ссылка, начинающаяся с http(s)://")
        return

    status = await update.message.reply_text("⏳ Скачиваю аудио и расшифровываю...")
    try:
        text = await transcribe.transcribe_youtube(url)
        await status.delete()
        if not text:
            await update.message.reply_text("⚠️ Whisper вернул пустой текст.")
            return
        await _send_long_text(update, "📝 Расшифровка:\n\n", text)
    except Exception as e:
        logger.exception("Ошибка транскрипции по ссылке")
        await status.edit_text(f"⚠️ Не удалось расшифровать: {e}")


async def media_transcribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расшифровка прикреплённого видео / голосового / аудио."""
    msg = update.message
    media = msg.voice or msg.audio or msg.video or msg.video_note or msg.document
    if not media:
        return

    file_size = getattr(media, "file_size", 0) or 0
    if file_size > TG_FILE_LIMIT_MB * 1024 * 1024:
        await msg.reply_text(
            f"⚠️ Файл {file_size // 1024 // 1024} МБ — больше лимита Telegram Bot API "
            f"({TG_FILE_LIMIT_MB} МБ). Пришлите ссылку через /transcribe."
        )
        return

    status = await msg.reply_text("⏳ Расшифровываю...")
    try:
        tg_file = await context.bot.get_file(media.file_id)
        with tempfile.TemporaryDirectory() as tmp:
            ext = (getattr(media, "mime_type", "") or "").split("/")[-1] or "ogg"
            path = os.path.join(tmp, f"input.{ext}")
            await tg_file.download_to_drive(path)
            text = await transcribe.transcribe_file(path)

        await status.delete()
        if not text:
            await msg.reply_text("⚠️ Whisper вернул пустой текст.")
            return
        await _send_long_text(update, "📝 Расшифровка:\n\n", text)
    except Exception as e:
        logger.exception("Ошибка транскрипции медиа")
        await status.edit_text(f"⚠️ Не удалось расшифровать: {e}")


async def webapp_data(update: "Update", context: ContextTypes.DEFAULT_TYPE):
    """Обработка данных от MiniApp (fallback если API недоступен)."""
    user = update.effective_user
    try:
        payload = json.loads(update.message.web_app_data.data)
        action = payload.get("action", "")
        data = payload.get("data", {})
        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        if action == "tonar_trip":
            row_id = sheets.save_tonar_trip(data)
            await update.message.reply_text(f"✅ Рейс тонара сохранён! ID: {row_id}")
            await notify_director(context, f"🚛 Рейс тонара · {now}\nВодитель: {data.get('driver','?')}\nМашина: {data.get('truck','?')}\n{data.get('quarry','?')} → {data.get('client','?')}\n{data.get('load_tonnage','?')} т")

        elif action == "mixer_trip":
            row_id = sheets.save_mixer_trip(data)
            await update.message.reply_text(f"✅ Рейс миксера сохранён! ID: {row_id}")
            await notify_director(context, f"🔄 Рейс миксера · {now}\nВодитель: {data.get('driver','?')}\n{data.get('plant','?')} → {data.get('client','?')}\n{data.get('volume','?')} м³")

        elif action == "mechanic_record":
            row_id = sheets.save_mechanic_record(data)
            await update.message.reply_text(f"✅ Запись слесаря сохранена! ID: {row_id}")

        elif action == "trip_price":
            if "created_at" not in data:
                data["created_at"] = now
            row_id = sheets.save_director_trip_price(data)
            await update.message.reply_text(f"✅ Цена рейса сохранена! ID: {row_id}")
            await notify_director(context, f"💰 Цена рейса · {now}\n{data.get('driver','?')} | {data.get('quarry','?')} → {data.get('client','?')}: ₽{data.get('price','?')}")

        elif action == "quarry_plan":
            if "created_at" not in data:
                data["created_at"] = now
            row_id = sheets.save_director_quarry_plan(data)
            await update.message.reply_text(f"✅ План карьера сохранён! ID: {row_id}")
            await notify_director(context, f"📋 План карьера · {now}\n{data.get('quarry','?')}: {data.get('planned_tonnage','?')} т ({data.get('period','?')})")

        else:
            await update.message.reply_text("✅ Данные сохранены.")

    except Exception as e:
        logger.error(f"Ошибка обработки данных: {e}")
        await update.message.reply_text(f"⚠️ Ошибка: {e}")


def main():
    """Запуск PULSAR (API сервер + бот)."""
    from aiohttp import web
    from telegram.ext import Application, CommandHandler, MessageHandler, filters
    import asyncio

    logger.info("🚛 PULSAR запускается...")

    # Создаём Telegram бота
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("setrole", setrole))
    telegram_app.add_handler(CommandHandler("myid", myid))
    telegram_app.add_handler(CommandHandler("roles", roles_list))
    telegram_app.add_handler(CommandHandler("transcribe", transcribe_cmd))
    telegram_app.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO | filters.VIDEO | filters.VIDEO_NOTE,
        media_transcribe,
    ))
    telegram_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data))

    # Создаём API сервер
    api_app = create_app()

    async def start_bot(app):
        """Запустить Telegram бота при старте сервера."""
        await telegram_app.initialize()
        await telegram_app.start()
        logger.info("🤖 Telegram бот запущен")
        # Запускаем polling в фоне
        asyncio.create_task(polling(telegram_app))

    async def polling(app):
        """Цикл опроса обновлений."""
        offset = None
        while True:
            try:
                updates = await app.bot.get_updates(offset=offset, timeout=30)
                for update in updates:
                    offset = update.update_id + 1
                    await app.process_update(update)
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(5)

    async def stop_bot(app):
        """Остановить бота при выключении."""
        await telegram_app.stop()
        await telegram_app.shutdown()
        logger.info("🤖 Telegram бот остановлен")

    # Добавляем хуки запуска/остановки
    api_app.on_startup.append(start_bot)
    api_app.on_cleanup.append(stop_bot)

    logger.info(f"🚀 PULSAR API запущен на порту {API_PORT}")
    web.run_app(api_app, host="0.0.0.0", port=API_PORT)


if __name__ == "__main__":
    main()
