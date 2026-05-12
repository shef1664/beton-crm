"""
Notion sync — duplicates each new lead from backend into the 📥 Лиды database
under «🤖 Автоматизированный отдел продаж — Бетон42».

Failure to sync NEVER blocks lead creation in AmoCRM/SQLite/Telegram.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"

# Маппинг наших internal keys → Notion property names в базе «📥 Лиды»
SOURCE_TO_OPTION = {
    "site": "Сайт",
    "site-form": "Сайт",
    "landing-beton-express": "Сайт",
    "landing-main": "Сайт",
    "landing-speed": "Сайт",
    "landing-calc": "Сайт",
    "avito": "Авито",
    "telegram": "Telegram",
    "phone": "Звонок",
    "call": "Звонок",
    "yandex_maps": "Яндекс.Карты",
    "2gis": "2ГИС",
    "vk": "ВК",
    "whatsapp": "WhatsApp",
    "email": "Email",
}

URGENCY_TO_OPTION = {
    "urgent": "Срочно",
    "normal": "Норма",
    "later": "Можно подождать",
}

CLIENT_TYPE_TO_OPTION = {
    "private": "Физлицо",
    "business": "Юрлицо",
    "legal": "Юрлицо",
    "contractor": "Подрядчик",
}


class NotionLeadsSync:
    def __init__(self) -> None:
        self.token = os.getenv("NOTION_API_TOKEN", "")
        self.data_source_id = os.getenv(
            "NOTION_LEADS_DATA_SOURCE_ID",
            "4cec5918-8482-43d8-8028-88f44480d284",  # public ID — not a secret
        )

    def is_available(self) -> bool:
        return bool(self.token)

    @staticmethod
    def _truncate(value: Any, limit: int = 2000) -> str:
        s = "" if value is None else str(value)
        return s[:limit]

    def _build_properties(self, lead: dict[str, Any], amo_lead_id: int | None) -> dict:
        name = lead.get("name") or "Лид без имени"
        title = name
        if lead.get("concrete_grade") and lead.get("volume"):
            title = f"{name} — {lead['concrete_grade']}, {lead['volume']} м³"

        props: dict[str, Any] = {
            "Лид": {"title": [{"text": {"content": self._truncate(title, 200)}}]},
            "Имя": {"rich_text": [{"text": {"content": self._truncate(name, 200)}}]},
        }

        if lead.get("phone"):
            props["Телефон"] = {"phone_number": self._truncate(lead["phone"], 50)}

        source = lead.get("source_platform") or lead.get("source")
        opt = SOURCE_TO_OPTION.get(str(source).lower()) if source else None
        if opt:
            props["Источник"] = {"select": {"name": opt}}

        for k_in, k_out in [
            ("utm_source", "UTM Source"),
            ("utm_medium", "UTM Medium"),
            ("utm_campaign", "UTM Campaign"),
            ("address", "Адрес доставки"),
            ("comment", "Комментарий"),
            ("assigned_manager", "Менеджер"),
        ]:
            if lead.get(k_in):
                props[k_out] = {"rich_text": [{"text": {"content": self._truncate(lead[k_in])}}]}

        if lead.get("concrete_grade"):
            props["Марка бетона"] = {"select": {"name": str(lead["concrete_grade"])}}

        if lead.get("volume") is not None:
            try:
                props["Объём м³"] = {"number": float(lead["volume"])}
            except (TypeError, ValueError):
                pass

        if lead.get("delivery_date"):
            props["Дата доставки"] = {"date": {"start": str(lead["delivery_date"])[:10]}}

        urgency_opt = URGENCY_TO_OPTION.get(str(lead.get("urgency", "")).lower())
        if urgency_opt:
            props["Срочность"] = {"select": {"name": urgency_opt}}

        ct = CLIENT_TYPE_TO_OPTION.get(str(lead.get("client_type", "")).lower())
        if ct:
            props["Тип клиента"] = {"select": {"name": ct}}

        if lead.get("calculated_amount") is not None:
            try:
                props["Расчётная сумма"] = {"number": float(lead["calculated_amount"])}
            except (TypeError, ValueError):
                pass

        if lead.get("distance") is not None:
            try:
                props["Расстояние км"] = {"number": float(lead["distance"])}
            except (TypeError, ValueError):
                pass

        if amo_lead_id:
            props["AmoCRM ID"] = {"number": int(amo_lead_id)}

        return props

    async def push_lead(self, lead: dict[str, Any], amo_lead_id: int | None = None) -> str | None:
        """Returns Notion page ID on success, None on failure (non-blocking)."""
        if not self.is_available():
            return None

        payload = {
            "parent": {"type": "data_source_id", "data_source_id": self.data_source_id},
            "properties": self._build_properties(lead, amo_lead_id),
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.post(f"{NOTION_API_BASE}/pages", headers=headers, json=payload)
                if resp.status_code in (200, 201):
                    page_id = resp.json().get("id")
                    logger.info("Notion lead page created: %s", page_id)
                    return page_id
                logger.warning("Notion lead sync failed: %s %s", resp.status_code, resp.text[:400])
        except Exception as exc:
            logger.warning("Notion lead sync exception: %s", exc)
        return None
