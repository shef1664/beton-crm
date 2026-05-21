"""
Avito → AmoCRM lead poller.

Runs as an asyncio loop inside the FastAPI process. Every POLL_INTERVAL_SEC
seconds:
  1. Fetches new client messages via AvitoService.fetch_new_messages
  2. For each new message, creates a deal in AmoCRM with tag "Авито"
  3. Optionally posts a Telegram notification (if TELEGRAM_BOT_TOKEN set)

Idempotency: AvitoService persists last seen message id per chat, so
restarts will not duplicate leads.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = int(os.getenv("AVITO_POLL_INTERVAL_SEC", "300"))  # 5 min


async def _notify_telegram(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    admin_id = os.getenv("TELEGRAM_ADMIN_ID", "").strip()
    if not token or not admin_id:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": admin_id, "text": text, "parse_mode": "HTML"},
            )
    except Exception as e:
        logger.warning("telegram notify error: %s", e)


def _build_lead_data(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Build a lead dict in the shape AmoCRMService.create_lead expects."""
    chat = msg.get("_chat", {}) or {}
    users = chat.get("users") or []
    me_id = str(os.getenv("AVITO_USER_ID", ""))
    client_user = next((u for u in users if str(u.get("id")) != me_id), {}) or {}

    client_name = client_user.get("name") or "Авито клиент"
    item = (chat.get("context") or {}).get("value") or {}
    item_title = item.get("title") or ""
    item_price = item.get("price_string") or ""

    body = msg.get("content", {}).get("text") or msg.get("content", {}).get("call", {}).get("status") or ""

    return {
        "name": client_name,
        "phone": "",  # phone usually not present in Avito chat
        "source": "avito",
        "tag": "Авито",
        "comment": f"Авито чат: «{item_title}»\nЦена объявления: {item_price}\nСообщение: {body}".strip(),
        "marka": "",
        "amount": "",
        "details": [
            f"Источник: Авито",
            f"Объявление: {item_title}".strip(": "),
            f"Сообщение клиента: {body}",
            f"Чат: https://www.avito.ru/profile/messenger/channel/{chat.get('id','')}",
        ],
    }


async def avito_poll_loop(amocrm) -> None:
    """Main loop. Imported and started from main.py startup."""
    # Lazy import to avoid circular dependencies during cold start
    from services.avito import AvitoService

    avito = AvitoService()
    if not avito.is_configured():
        logger.info("avito_poller: AVITO_* env vars missing, poller disabled")
        return

    logger.info("avito_poller: started, interval=%ss", POLL_INTERVAL_SEC)

    while True:
        try:
            new_msgs = await avito.fetch_new_messages() or []
            if new_msgs:
                logger.info("avito_poller: %d new messages", len(new_msgs))
            for msg in new_msgs:
                lead_data = _build_lead_data(msg)
                try:
                    lead_id = await amocrm.create_lead(lead_data)
                except Exception as e:
                    logger.error("avito_poller: amocrm.create_lead failed: %s", e)
                    lead_id = 0
                name = lead_data["name"]
                comment = lead_data["comment"][:300]
                await _notify_telegram(
                    f"🟦 <b>Новый лид с Авито</b>\n"
                    f"Клиент: <b>{name}</b>\n"
                    f"AmoCRM сделка: {lead_id or '—'}\n\n"
                    f"<i>{comment}</i>"
                )
        except Exception as e:
            logger.exception("avito_poller iteration error: %s", e)
        await asyncio.sleep(POLL_INTERVAL_SEC)
