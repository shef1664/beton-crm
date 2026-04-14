"""Telegram уведомления"""
import httpx
import logging
from config import settings

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.admin_id = settings.TELEGRAM_ADMIN_ID
        self.is_configured = bool(self.bot_token and self.admin_id)
    
    def is_available(self) -> bool:
        return self.is_configured
    
    async def _send_message(self, text: str):
        """Отправка сообщения"""
        if not self.is_configured:
            logger.warning(f"Telegram не настроен: {text}")
            return
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.admin_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload)
    
    async def notify_new_lead(self, lead_data: dict, lead_id: int):
        """Уведомление о новом лиде"""
        text = f"""
🔔 <b>Новая заявка!</b>

👤 Имя: {lead_data.get('name', 'Не указано')}
📞 Телефон: {lead_data.get('phone', 'Не указан')}
🏗 Марка: {lead_data.get('concrete_grade', 'Не указана')}
📦 Объём: {lead_data.get('volume', 'Не указан')} м³
📍 Адрес: {lead_data.get('address', 'Не указан')}
💰 Сумма: {lead_data.get('calculated_amount', 0):,.0f} ₽
⚡ Срочность: {lead_data.get('urgency', 'normal')}

ID: {lead_id}
Источник: {lead_data.get('source', 'landing')}
"""
        await self._send_message(text)
    
    async def notify_hot_lead(self, lead_id: int):
        """Уведомление о горячем лиде"""
        text = f"""
🔥 <b>ГОРЯЧИЙ ЛИД!</b>

Лид #{lead_id} перешёл в статус "Горячий"
Срочно свяжитесь с клиентом!
"""
        await self._send_message(text)
    
    async def notify_error(self, error: str):
        """Уведомление об ошибке"""
        text = f"""
❌ <b>Ошибка в системе!</b>

{error}
"""
        await self._send_message(text)
