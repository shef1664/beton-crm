"""Telegram notifications for leads and system events."""

import logging

import httpx

from config import settings
from services.lead_utils import coerce_amount

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.admin_id = settings.TELEGRAM_ADMIN_ID
        self.is_configured = bool(self.bot_token and self.admin_id)

    def is_available(self) -> bool:
        return self.is_configured

    async def _send_message(self, text: str):
        if not self.is_configured:
            logger.warning("Telegram is not configured: %s", text)
            return

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.admin_id,
            "text": text,
            "parse_mode": "HTML",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except Exception as exc:
            logger.error("Telegram notification failed: %s", exc)

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
