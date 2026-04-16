"""Конфигурация backend"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class Settings:
    # amoCRM
    AMOCRM_DOMAIN: str = os.getenv("AMOCRM_DOMAIN", "")  # example.amocrm.ru
    AMOCRM_CLIENT_ID: str = os.getenv("AMOCRM_CLIENT_ID", "")
    AMOCRM_CLIENT_SECRET: str = os.getenv("AMOCRM_CLIENT_SECRET", "")
    AMOCRM_REDIRECT_URI: str = os.getenv("AMOCRM_REDIRECT_URI", "")
    AMOCRM_ACCESS_TOKEN: str = os.getenv("AMOCRM_ACCESS_TOKEN", "")
    AMOCRM_PIPELINE_ID: int = int(os.getenv("AMOCRM_PIPELINE_ID", "0"))
    
    # Backend URL (для Telegram webhook и внешних сервисов)
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    
    # API ключ для админских операций (обновление лендинга и т.д.)
    API_SECRET_KEY: str = os.getenv("API_SECRET_KEY", "change-me-in-production")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_ID: int = int(os.getenv("TELEGRAM_ADMIN_ID", "150420"))

    # Baserow
    BASEROW_URL: str = os.getenv("BASEROW_URL", "https://api.baserow.io")
    BASEROW_TOKEN: str = os.getenv("BASEROW_TOKEN", "")
    BASEROW_LEADS_TABLE_ID: int = int(os.getenv("BASEROW_LEADS_TABLE_ID", "0"))
    BASEROW_LOGS_TABLE_ID: int = int(os.getenv("BASEROW_LOGS_TABLE_ID", "0"))
    
    # Калькулятор
    BETON_PRICES: dict = {
        "М100": 5800,
        "М150": 6100,
        "М200": 6400,
        "М250": 6800,
        "М300": 7200,
        "М350": 7600,
        "М400": 8000,
        "М450": 8400
    }
    DELIVERY_PRICE_PER_KM: float = 150  # ₽/км
    MIXER_VOLUME: float = 7  # м³ в миксере
    
    # Pipeline статусы
    PIPELINE_STATUSES: dict = {
        "new": 5311172,      # Новый лид
        "data_collection": 5311174,  # Сбор данных
        "qualification": 5311176,    # Квалификация
        "calculation": 5311178,      # Расчёт
        "follow_up": 5311180,        # Дожим
        "hot_lead": 5311182,         # Горячий лид
        "confirmed": 5311184,        # Сделка подтверждена
        "completed": 5311186,        # Завершено
        "lost": 5311188              # Проиграно
    }

settings = Settings()

# Предупреждения о незаполненных настройках
if not settings.AMOCRM_ACCESS_TOKEN:
    logger.warning("⚠️  AMOCRM_ACCESS_TOKEN не задан — заявки не будут попадать в amoCRM")
if not settings.TELEGRAM_BOT_TOKEN:
    logger.warning("⚠️  TELEGRAM_BOT_TOKEN не задан — уведомления в Telegram отключены")
if not settings.BASEROW_TOKEN:
    logger.warning("⚠️  BASEROW_TOKEN не задан — логирование в Baserow отключено")
if settings.API_SECRET_KEY == "change-me-in-production" or settings.API_SECRET_KEY == "your-secret-key-change-this":
    logger.warning("⚠️  API_SECRET_KEY не изменён! Сгенерируйте ключ: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")

