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


def _build_lead_data(chat: Dict[str, Any]) -> Dict[str, Any]:
    """Build a lead dict from chat metadata.

    Note: free Avito API does not give message body without paid Messenger
    API subscription. So we only use chat metadata: client name, ad title,
    chat link. Manager opens the chat in Avito app to read the actual message.
    """
    users = chat.get("users") or []
    me_id = str(os.getenv("AVITO_USER_ID", ""))
    client_user = next((u for u in users if str(u.get("id")) != me_id), {}) or {}

    client_name = client_user.get("name") or "Авито клиент"
    item = (chat.get("context") or {}).get("value") or {}
    item_title = item.get("title") or ""
    item_price = item.get("price_string") or ""
    item_url = item.get("url") or ""
    chat_url = f"https://www.avito.ru/profile/messenger/channel/{chat.get('id','')}"

    return {
        "name": client_name,
        "phone": "",
        "source": "avito",
        "tag": "Авито",
        "comment": (
            f"Новое сообщение на Авито\n"
            f"Объявление: {item_title}\n"
            f"Цена: {item_price}\n"
            f"Откройте чат для ответа: {chat_url}"
        ).strip(),
        "marka": "",
        "amount": "",
        "details": [
            "Источник: Авито",
            f"Объявление: {item_title}",
            f"Цена: {item_price}",
            f"Ссылка на объявление: {item_url}",
            f"Чат: {chat_url}",
            "Тело сообщения недоступно (требуется платная подписка API мессенджера)",
        ],
    }


async def avito_poll_loop(amocrm) -> None:
    """Main loop. Imported and started from main.py startup.

    Without paid Messenger API subscription Avito does not return message
    bodies, so we operate on chat-level signals: every time a chat updates
    with a new incoming message (direction='in'), we create one CRM deal
    and notify operator. State (last seen chat.updated) is persisted to
    avoid duplicates.
    """
    from services.avito import AvitoService

    avito = AvitoService()
    if not avito.is_configured():
        logger.info("avito_poller: AVITO_* env vars missing, poller disabled")
        return

    logger.info("avito_poller: started, interval=%ss", POLL_INTERVAL_SEC)

    while True:
        try:
            await _poll_iteration(avito, amocrm)
        except Exception as e:
            logger.exception("avito_poller iteration error: %s", e)
        await asyncio.sleep(POLL_INTERVAL_SEC)


async def _poll_iteration(avito, amocrm) -> None:
    """One pass: enumerate chats, create deals for new client activity."""
    state = avito._load_state()
    seen_updated: Dict[str, int] = state.setdefault("chat_updated", {})

    chats = await avito.list_chats(only_unread=False, limit=50)
    new_count = 0
    me_id = str(os.getenv("AVITO_USER_ID", ""))

    for chat in chats:
        chat_id = chat.get("id")
        if not chat_id:
            continue
        updated = int(chat.get("updated") or 0)
        first_time = chat_id not in seen_updated
        # First time we see this chat → just record state, do not flood AmoCRM
        # with historical chats. Lead создаётся только при новой активности.
        if first_time:
            seen_updated[chat_id] = updated
            continue
        if updated <= seen_updated[chat_id]:
            continue
        # Only react if the last message is FROM the client (incoming).
        last_msg = chat.get("last_message") or {}
        direction = last_msg.get("direction", "")
        author_id = str(last_msg.get("author_id") or "")
        if direction != "in" or author_id == me_id:
            seen_updated[chat_id] = updated
            continue

        # Create lead
        lead_data = _build_lead_data(chat)
        try:
            lead_id = await amocrm.create_lead(lead_data)
        except Exception as e:
            logger.error("avito_poller: amocrm.create_lead failed: %s", e)
            lead_id = 0
        name = lead_data["name"]
        item_title = ((chat.get("context") or {}).get("value") or {}).get("title", "")
        chat_url = f"https://www.avito.ru/profile/messenger/channel/{chat_id}"
        await _notify_telegram(
            f"🟦 <b>Новое обращение Авито</b>\n"
            f"Клиент: <b>{name}</b>\n"
            f"Объявление: {item_title}\n"
            f"AmoCRM сделка: {lead_id or '—'}\n\n"
            f"<a href=\"{chat_url}\">Открыть чат в Авито</a>"
        )
        seen_updated[chat_id] = updated
        new_count += 1

    state["chat_updated"] = seen_updated
    avito._save_state(state)
    if new_count:
        logger.info("avito_poller: %d new client activities", new_count)
