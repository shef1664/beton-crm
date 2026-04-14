"""
API сервер для PULSAR MiniApp.
Обрабатывает fetch() запросы из MiniApp и записывает данные в Google Sheets.
Запускается вместе с ботом на одном процессе через aiohttp.
"""

import json
import logging
import asyncio
from datetime import datetime
from aiohttp import web
import sheets
from config import BOT_TOKEN

logger = logging.getLogger(__name__)

API_SECRET = "pulsar-api-secret-2026"  # Простая авторизация

# Telegram приложение (создаётся при запуске)
_telegram_app = None


def check_auth(request):
    """Проверить API ключ в заголовке."""
    auth = request.headers.get("X-API-Key", "")
    if auth and auth != API_SECRET:
        return False
    return True


def ok(data):
    return web.json_response({"status": "ok", **data})


def err(msg, code=400):
    return web.json_response({"status": "error", "message": msg}, status=code)


async def handle_api(request):
    """Основной обработчик API."""
    if not check_auth(request):
        return err("Unauthorized", 401)

    try:
        body = await request.json()
    except Exception:
        return err("Invalid JSON")

    action = body.get("action", "")
    data = body.get("data", {})

    # Добавить дату если нет
    if "date" not in data:
        data["date"] = datetime.now().strftime("%d.%m.%Y")
    if "time" not in data:
        data["time"] = datetime.now().strftime("%H:%M")

    try:
        # ─── ТОНАРЫ ───
        if action == "tonar_trip":
            row_id = sheets.save_tonar_trip(data)
            return ok({"id": row_id, "message": "Рейс тонара сохранён"})

        # ─── МИКСЕРЫ ───
        elif action == "mixer_trip":
            row_id = sheets.save_mixer_trip(data)
            return ok({"id": row_id, "message": "Рейс миксера сохранён"})

        # ─── ДЛИННОМЕРЫ ───
        elif action == "dlinn_trip":
            row_id = sheets.save_dlinn_trip(data)
            return ok({"id": row_id, "message": "Рейс длинномера сохранён"})

        elif action == "dlinn_fuel":
            row_id = sheets.save_dlinn_fuel(data)
            return ok({"id": row_id, "message": "Заправка сохранена"})

        elif action == "dlinn_expense":
            row_id = sheets.save_dlinn_expense(data)
            return ok({"id": row_id, "message": "Расход сохранён"})

        elif action == "dlinn_repair":
            row_id = sheets.save_dlinn_repair(data)
            return ok({"id": row_id, "message": "Ремонт сохранён"})

        elif action == "dlinn_parts":
            row_id = sheets.save_dlinn_parts(data)
            return ok({"id": row_id, "message": "Запчасти сохранены"})

        # ─── СЛЕСАРЬ ───
        elif action == "mechanic_record":
            row_id = sheets.save_mechanic_record(data)
            return ok({"id": row_id, "message": "Запись сохранена"})

        # ─── ДИРЕКТОР ───
        elif action == "trip_price":
            if "created_at" not in data:
                data["created_at"] = datetime.now().strftime("%d.%m.%Y %H:%M")
            row_id = sheets.save_director_trip_price(data)
            return ok({"id": row_id, "message": "Цена рейса сохранена"})

        elif action == "quarry_plan":
            if "created_at" not in data:
                data["created_at"] = datetime.now().strftime("%d.%m.%Y %H:%M")
            row_id = sheets.save_director_quarry_plan(data)
            return ok({"id": row_id, "message": "План карьера сохранён"})

        # ─── ЧТЕНИЕ ───
        elif action == "read":
            table = data.get("table", "")
            sheet_name = data.get("sheet", "")
            if not table or not sheet_name:
                return err("Нужны table и sheet")
            records = sheets.read_sheet(table, sheet_name)
            return ok({"data": records, "count": len(records)})

        else:
            return err(f"Неизвестное действие: {action}")

    except Exception as e:
        logger.error(f"API ошибка [{action}]: {e}", exc_info=True)
        return err(str(e))


async def health_check(request):
    return web.json_response({"status": "alive", "service": "PULSAR API"})


def create_app():
    """Создать aiohttp приложение."""
    app = web.Application()
    app.router.add_post("/api", handle_api)
    app.router.add_get("/health", health_check)

    return app


if __name__ == "__main__":
    from config import API_PORT
    app = create_app()
    logger.info(f"🚀 PULSAR API запущен на порту {API_PORT}")
    web.run_app(app, host="0.0.0.0", port=API_PORT)
