"""
keepalive.py — пингует Render каждые 10 минут чтобы сервис не засыпал.

Запуск:
    python keepalive.py https://beton-backend-kwa9.onrender.com
"""

import sys
import time
from datetime import datetime

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

INTERVAL = 600
TIMEOUT = 15
ENDPOINT = "/ping"


def get_url():
    if len(sys.argv) < 2:
        print("Usage: python keepalive.py <URL>")
        sys.exit(1)
    return sys.argv[1].strip().rstrip("/")


def ping(url):
    full_url = url + ENDPOINT
    now = datetime.now().strftime("%H:%M:%S")
    try:
        r = requests.get(full_url, timeout=TIMEOUT)
        status = "OK" if r.status_code == 200 else f"ERR {r.status_code}"
        print(f"  [{now}] {status}")
        return r.status_code == 200
    except requests.Timeout:
        print(f"  [{now}] TIMEOUT")
        return False
    except Exception as e:
        print(f"  [{now}] ERROR: {e}")
        return False


def main():
    url = get_url()
    print(f"Keep-alive: {url}{ENDPOINT} каждые {INTERVAL//60} мин. Ctrl+C для стоп.")
    total = success = 0
    try:
        while True:
            total += 1
            if ping(url):
                success += 1
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        pct = round(success / total * 100) if total else 0
        print(f"\nСтоп. {success}/{total} успешных ({pct}%)")


if __name__ == "__main__":
    main()
