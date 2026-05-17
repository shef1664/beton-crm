"""
Internal scheduled tasks running inside the FastAPI process.

Two jobs:
1. keepalive_loop — pings own /ping every 10 minutes so Render Free
   does not sleep (it sleeps after 15 min of zero external traffic).
2. daily_summary_loop — once per day at 21:00 local (Asia/Krasnoyarsk)
   sends a Telegram summary of new leads to TELEGRAM_ADMIN_ID.

Failures are logged but never crash the parent task.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

import httpx

logger = logging.getLogger(__name__)

KEEPALIVE_INTERVAL_SEC = 600  # 10 min
DAILY_SUMMARY_HOUR = 21       # 21:00
KEMEROVO_TZ = timezone(timedelta(hours=7))


async def keepalive_loop(self_url: str) -> None:
    """Self-ping every 10 min to prevent Render Free sleep."""
    if not self_url:
        logger.warning("keepalive_loop: BACKEND_URL not set, skip")
        return
    url = self_url.rstrip("/") + "/ping"
    await asyncio.sleep(60)  # let app warm up first
    while True:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(url)
                logger.debug("keepalive ping %s → %s", url, r.status_code)
        except Exception as exc:
            logger.warning("keepalive ping failed: %s", exc)
        await asyncio.sleep(KEEPALIVE_INTERVAL_SEC)


async def _send_telegram(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_ADMIN_ID", "")
    if not token or not chat_id:
        logger.info("daily_summary: TG creds missing, skip send")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
    except Exception as exc:
        logger.warning("daily_summary TG send failed: %s", exc)


async def daily_summary_loop(self_url: str) -> None:
    """Once per day at 21:00 Kemerovo time → Telegram summary."""
    if not self_url:
        return
    sent_for_date: str | None = None
    while True:
        now_kem = datetime.now(KEMEROVO_TZ)
        today_str = now_kem.strftime("%Y-%m-%d")
        # fire when hour matches and we haven't already fired today
        if now_kem.hour == DAILY_SUMMARY_HOUR and sent_for_date != today_str:
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    r = await client.get(self_url.rstrip("/") + "/api/sales/dashboard")
                    data = (r.json() or {}).get("dashboard", {}) if r.status_code == 200 else {}
                total = data.get("total", 0)
                today = data.get("today", 0)
                week = data.get("week", 0)
                overdue = data.get("overdue_contacts", 0)
                sources = data.get("sources", []) or []
                src_lines = "\n".join(f"  • {s.get('source','?')}: {s.get('cnt',0)}" for s in sources[:8])
                latest = data.get("latest") or {}
                latest_name = latest.get("name", "—")
                latest_phone = latest.get("phone", "—")
                msg = (
                    f"<b>📊 Сводка за {today_str}</b>\n\n"
                    f"Лидов всего: <b>{total}</b>\n"
                    f"За сегодня: <b>{today}</b>\n"
                    f"За неделю: <b>{week}</b>\n"
                    f"Просроченных контактов: <b>{overdue}</b>\n\n"
                    f"<b>Источники:</b>\n{src_lines or '  • —'}\n\n"
                    f"<b>Последний:</b> {latest_name} ({latest_phone})"
                )
                await _send_telegram(msg)
                sent_for_date = today_str
                logger.info("daily_summary sent for %s", today_str)
            except Exception as exc:
                logger.warning("daily_summary failed: %s", exc)
        await asyncio.sleep(300)  # check every 5 min


def start_scheduled_tasks(self_url: str) -> None:
    """Spawn background loops. Call from FastAPI startup."""
    loop = asyncio.get_event_loop()
    loop.create_task(keepalive_loop(self_url))
    loop.create_task(daily_summary_loop(self_url))
    logger.info("Scheduled tasks started: keepalive (10min) + daily_summary (21:00 Kmr)")
