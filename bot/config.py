"""Конфигурация бота PULSAR"""
import os
import json

# Токен бота от @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# WebApp URL
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.railway.app")

# Chat ID директора
DIRECTOR_CHAT_ID = int(os.getenv("DIRECTOR_ID", "0"))

# Путь к credentials
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json.json")

# Google Sheets — 5 таблиц (загрузить из файла или env)
SPREADSHEETS = {}
_ids_file = os.path.join(os.path.dirname(__file__), "spreadsheet_ids.json")
if os.path.exists(_ids_file):
    with open(_ids_file, "r", encoding="utf-8") as f:
        SPREADSHEETS = json.load(f)
# Fallback из env если файл не найден
_spreadsheets_env = os.getenv("SPREADSHEET_IDS")
if _spreadsheets_env and not SPREADSHEETS:
    SPREADSHEETS = json.loads(_spreadsheets_env)

# Порт для API сервера (Railway задаёт PORT)
API_PORT = int(os.getenv("API_PORT", os.getenv("PORT", "8080")))
