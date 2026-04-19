"""Backend configuration."""

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)


def _load_json_map(env_name: str) -> dict:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("%s contains invalid JSON and will be ignored", env_name)
        return {}
    if not isinstance(data, dict):
        logger.warning("%s must be a JSON object and will be ignored", env_name)
        return {}
    return data


class Settings:
    AMOCRM_DOMAIN: str = os.getenv("AMOCRM_DOMAIN", "")
    AMOCRM_CLIENT_ID: str = os.getenv("AMOCRM_CLIENT_ID", "")
    AMOCRM_CLIENT_SECRET: str = os.getenv("AMOCRM_CLIENT_SECRET", "")
    AMOCRM_REDIRECT_URI: str = os.getenv("AMOCRM_REDIRECT_URI", "")
    AMOCRM_ACCESS_TOKEN: str = os.getenv("AMOCRM_ACCESS_TOKEN", "")
    AMOCRM_PIPELINE_ID: int = int(os.getenv("AMOCRM_PIPELINE_ID", "0"))

    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    API_SECRET_KEY: str = os.getenv("API_SECRET_KEY", "change-me-in-production")

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_ID: int = int(os.getenv("TELEGRAM_ADMIN_ID", "150420"))

    BASEROW_URL: str = os.getenv("BASEROW_URL", "https://api.baserow.io")
    BASEROW_TOKEN: str = os.getenv("BASEROW_TOKEN", "")
    BASEROW_LEADS_TABLE_ID: int = int(os.getenv("BASEROW_LEADS_TABLE_ID", "0"))
    BASEROW_LOGS_TABLE_ID: int = int(os.getenv("BASEROW_LOGS_TABLE_ID", "0"))

    BETON_PRICES: dict = {
        "М100": 5800,
        "М150": 6100,
        "М200": 6400,
        "М250": 6800,
        "М300": 7200,
        "М350": 7600,
        "М400": 8000,
        "М450": 8400,
    }
    DELIVERY_PRICE_PER_KM: float = 150
    MIXER_VOLUME: float = 7

    SUPPORTED_SOURCE_PLATFORMS: tuple[str, ...] = (
        "site",
        "landing-main",
        "landing-calc",
        "landing-kdm",
        "landing-speed",
        "landing-trust",
        "landing-vedro",
        "telegram",
        "phone",
        "yandex_maps",
        "2gis",
        "avito",
        "vk",
        "max",
        "whatsapp",
        "email",
    )
    SUPPORTED_SOURCE_CHANNELS: tuple[str, ...] = (
        "form",
        "call",
        "chat",
        "message",
        "callback",
        "manual",
        "import",
    )
    REQUIRED_MANAGER_FIELDS: tuple[str, ...] = (
        "name",
        "phone",
        "source_platform",
        "source_channel",
        "client_type",
    )

    PIPELINE_STATUSES: dict = {
        "new": 85162970,
        "data_collection": 85162974,
        "qualification": 85162976,
        "calculation": 85162978,
        "follow_up": 85162980,
        "hot_lead": 85162982,
        "confirmed": 85162986,
        "closed_won": 142,
        "closed_lost": 143,
    }
    PIPELINE_STATUS_OVERRIDES: dict = _load_json_map("AMOCRM_PIPELINE_STATUSES_JSON")
    AMOCRM_CUSTOM_FIELD_IDS: dict = _load_json_map("AMOCRM_CUSTOM_FIELD_IDS_JSON")
    INTEGRATION_KEYS: dict = _load_json_map("INTEGRATION_KEYS_JSON")
    INTEGRATION_DEFAULTS: dict = {
        "telephony": {"source": "phone", "source_platform": "phone", "source_channel": "call"},
        "yandex_maps": {"source": "yandex_maps", "source_platform": "yandex_maps", "source_channel": "chat"},
        "2gis": {"source": "2gis", "source_platform": "2gis", "source_channel": "chat"},
        "avito": {"source": "avito", "source_platform": "avito", "source_channel": "chat"},
        "vk": {"source": "vk", "source_platform": "vk", "source_channel": "message"},
        "max": {"source": "max", "source_platform": "max", "source_channel": "message"},
        "email": {"source": "email", "source_platform": "email", "source_channel": "message"},
        "whatsapp": {"source": "whatsapp", "source_platform": "whatsapp", "source_channel": "message"},
    }
    SALES_MANAGERS: dict = _load_json_map("SALES_MANAGERS_JSON") or {
        "geo": "geo-team",
        "marketplaces": "marketplace-team",
        "messengers": "messenger-team",
        "phone": "call-team",
        "default": "sales-team",
    }
    SALES_AUTOMATION_RULES: dict = {
        "high_priority_sources": ("phone", "yandex_maps", "2gis", "whatsapp"),
        "marketplace_sources": ("avito",),
        "messenger_sources": ("telegram", "vk", "max", "whatsapp", "email"),
        "high_priority_amount": 70000,
        "hot_urgency_values": ("urgent", "asap", "today", "hot"),
    }
    SALES_PLAYBOOKS: dict = {
        "default": {
            "sales_playbook": "standard_followup",
            "sla_minutes": 30,
            "qualification_script": "Уточнить объем, марку, адрес, дату и способ оплаты.",
        },
        "geo": {
            "sales_playbook": "geo_fast_capture",
            "sla_minutes": 10,
            "qualification_script": "Перехватить лида из геосервиса, подтвердить телефон, адрес объекта и потребность в бетоне.",
        },
        "marketplaces": {
            "sales_playbook": "marketplace_reactivation",
            "sla_minutes": 15,
            "qualification_script": "Привязать лид к объявлению и аккаунту, уточнить объект, объем и готовность к звонку.",
        },
        "messengers": {
            "sales_playbook": "messenger_to_call",
            "sla_minutes": 15,
            "qualification_script": "Быстро перевести переписку в телефонный разговор и собрать параметры заказа.",
        },
        "phone": {
            "sales_playbook": "hot_call_close",
            "sla_minutes": 5,
            "qualification_script": "Обработать как горячий звонок: подтвердить наличие, цену, время доставки и закрыть на расчет.",
        },
    }


settings = Settings()
settings.PIPELINE_STATUSES.update(settings.PIPELINE_STATUS_OVERRIDES)

if not settings.AMOCRM_ACCESS_TOKEN:
    logger.warning("AMOCRM_ACCESS_TOKEN is not set, leads will stay local")
if not settings.TELEGRAM_BOT_TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN is not set, Telegram notifications are disabled")
if not settings.BASEROW_TOKEN:
    logger.warning("BASEROW_TOKEN is not set, external Baserow is disabled and SQLite fallback is active")
if settings.API_SECRET_KEY in ("change-me-in-production", "your-secret-key-change-this"):
    logger.warning("API_SECRET_KEY is not changed, generate a new one before production")
