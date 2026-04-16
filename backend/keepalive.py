"""
keepalive.py — пингует backend каждые 10 минут чтобы Render free tier не засыпал.
Запуск: python keepalive.py
Остановка: Ctrl+C
"""

import time
import logging
import os
import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "https://beton-backend-kwa9.onrender.com")
INTERVAL_SECONDS = 600  # 10 минут


def ping(url: str) -> bool:
    try:
        req = urllib.request.Request(f"{url}/ping", headers={"User-Agent": "keepalive/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                logger.info(f"OK  {url}/ping -> 200")
                return True
            logger.warning(f"WARN {url}/ping -> {resp.status}")
            return False
    except urllib.error.URLError as e:
        logger.error(f"FAIL {url}/ping -> {e.reason}")
        return False
    except Exception as e:
        logger.error(f"FAIL {url}/ping -> {e}")
        return False


if __name__ == "__main__":
    logger.info(f"Keepalive запущен. Цель: {BACKEND_URL}, интервал: {INTERVAL_SECONDS}с")
    while True:
        ping(BACKEND_URL)
        time.sleep(INTERVAL_SECONDS)
