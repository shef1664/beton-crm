"""Telegram notifications for leads and system events."""

import json
import logging
import os
from pathlib import Path

import httpx

from config import settings
from services.lead_utils import coerce_amount

logger = logging.getLogger(__name__)

# Тот же файл, куда клиентский бот сохраняет авто-определённый id группы отдела продаж.
_SALES_CHAT_STATE = Path(os.getenv("SALES_CHAT_STATE", "/tmp/beton-sales-chat.json"))


class TelegramNotifier:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.admin_id = settings.TELEGRAM_ADMIN_ID
        self.is_configured = bool(self.bot_token and self.admin_id)

    def is_available(self) -> bool:
        return self.is_configured

    def _sales_chat_id(self) -> int:
        """Id группы отдела продаж: env SALES_CHAT_ID или авто-определённый ботом."""
        env_id = int(os.getenv("SALES_CHAT_ID", "0") or 0)
        if env_id:
            return env_id
        try:
            if _SALES_CHAT_STATE.exists():
                return int(json.loads(_SALES_CHAT_STATE.read_text()).get("chat_id") or 0)
        except Exception:  # noqa: BLE001
            pass
        return 0

    async def _post(self, chat_id: int, text: str):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
                r.raise_for_status()
        except Exception as exc:
            logger.error("Telegram send to %s failed: %s", chat_id, exc)

    async def _send_message(self, text: str):
        if not self.is_configured:
            logger.warning("Telegram is not configured: %s", text)
            return
        await self._post(self.admin_id, text)

    async def notify_sales_group(self, lead_data: dict, lead_id: int):
        """Карточка заявки в группу отдела продаж (для не-Telegram источников — напр. МАКС).

        Telegram-бот шлёт свою карточку сам, поэтому для source=telegram здесь пропускаем,
        чтобы не было дублей. Идёт по прямому каналу (api.telegram.org) — надёжно и не
        зависит от опроса бота.
        """
        if not self.bot_token:
            return
        source = str(lead_data.get("source") or "").lower()
        if source == "telegram":
            return
        chat_id = self._sales_chat_id()
        if not chat_id:
            logger.warning("SALES_CHAT_ID неизвестен — карточка в группу не отправлена (source=%s)", source)
            return
        amount = coerce_amount(lead_data.get("calculated_amount")) or 0
        src_label = {"max": "МАКС"}.get(source, source or "сайт/бот")
        rows = [
            f"🧱 <b>Новая заявка из {src_label}</b>",
            f"Имя: {self._clean_value(lead_data.get('name'))}",
            f"Телефон: {self._clean_value(lead_data.get('phone'))}",
            f"Марка: {self._clean_value(lead_data.get('concrete_grade'))}",
            f"Объём: {self._clean_value(lead_data.get('volume'))} м³",
            f"Адрес: {self._clean_value(lead_data.get('address'))}",
            f"Когда: {self._clean_value(lead_data.get('delivery_date'))}",
            f"Оплата: {self._clean_value(lead_data.get('payment_method'))}",
        ]
        if amount:
            rows.append(f"Сумма (ориент.): {amount:,.0f} ₽".replace(",", " "))
        rows.append(f"ID: {lead_id}")
        await self._post(chat_id, "\n".join(rows))

    @staticmethod
    def _clean_value(value, default: str = "не указано") -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text or default

    async def notify_new_lead(self, lead_data: dict, lead_id: int):
        amount = coerce_amount(lead_data.get("calculated_amount")) or 0
        text = (
            "<b>Новая заявка</b>\n\n"
            f"Имя: {self._clean_value(lead_data.get('name'))}\n"
            f"Телефон: {self._clean_value(lead_data.get('phone'))}\n"
            f"Марка: {self._clean_value(lead_data.get('concrete_grade'))}\n"
            f"Объем: {self._clean_value(lead_data.get('volume'))} м3\n"
            f"Адрес: {self._clean_value(lead_data.get('address'))}\n"
            f"Сумма: {amount:,.0f} RUB\n"
            f"Срочность: {self._clean_value(lead_data.get('urgency'), 'normal')}\n"
            f"Источник: {self._clean_value(lead_data.get('source'))}\n"
            f"Платформа: {self._clean_value(lead_data.get('source_platform'))}\n"
            f"Канал: {self._clean_value(lead_data.get('source_channel'))}\n"
            f"Аккаунт: {self._clean_value(lead_data.get('source_account'))}\n"
            f"Объявление: {self._clean_value(lead_data.get('source_listing'))}\n"
            f"Кампания: {self._clean_value(lead_data.get('source_campaign'))}\n"
            f"UTM: {self._clean_value(lead_data.get('utm_source'))} / "
            f"{self._clean_value(lead_data.get('utm_medium'))} / "
            f"{self._clean_value(lead_data.get('utm_campaign'))}\n"
            f"Тип клиента: {self._clean_value(lead_data.get('client_type'), 'private')}\n"
            f"Менеджер: {self._clean_value(lead_data.get('assigned_manager'))}\n"
            f"Приоритет: {self._clean_value(lead_data.get('sales_priority'))}\n"
            f"Playbook: {self._clean_value(lead_data.get('sales_playbook'))}\n"
            f"SLA: {self._clean_value(lead_data.get('sla_minutes'))} min\n"
            f"До контакта: {self._clean_value(lead_data.get('contact_deadline_at'))}\n"
            f"Следующий шаг: {self._clean_value(lead_data.get('next_action'))}\n\n"
            f"ID: {lead_id}"
        )
        await self._send_message(text)
        # Карточка в группу отдела продаж (для не-Telegram источников, напр. МАКС)
        await self.notify_sales_group(lead_data, lead_id)

    async def notify_hot_lead(self, lead_id: int):
        text = (
            "<b>Горячий лид</b>\n\n"
            f"Лид #{lead_id} перешел в статус горячего.\n"
            "Нужен быстрый контакт менеджера."
        )
        await self._send_message(text)

    async def notify_error(self, error: str):
        text = f"<b>Ошибка в системе</b>\n\n{error}"
        await self._send_message(text)
