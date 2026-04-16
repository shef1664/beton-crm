"""
Проверка подключения ко всем внешним сервисам.
Запуск: python test_connections.py
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

OK = "   \u2705"
FAIL = "   \u274c"

print("=" * 52)
print("\U0001f50d  \u041f\u0420\u041e\u0412\u0415\u0420\u041a\u0410 \u041f\u041e\u0414\u041a\u041b\u042e\u0427\u0415\u041d\u0418\u0419")
print("=" * 52)

all_ok = True

# ---- Telegram ----
print("\n\U0001f4f1 Telegram...")
token = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not token:
    print(f"{FAIL} TELEGRAM_BOT_TOKEN \u043f\u0443\u0441\u0442\u043e\u0439!")
    all_ok = False
else:
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        data = r.json()
        if data.get("ok"):
            print(f"{OK} \u0411\u043e\u0442 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d: @{data['result']['username']}")
        else:
            print(f"{FAIL} \u041e\u0448\u0438\u0431\u043a\u0430: {data.get('description')}")
            all_ok = False
    except Exception as e:
        print(f"{FAIL} \u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u043e\u0435\u0434\u0438\u043d\u0435\u043d\u0438\u044f: {e}")
        all_ok = False

# ---- Telegram chat_id ----
chat_id = os.getenv("TELEGRAM_ADMIN_ID", "")
if not chat_id or chat_id == "150420":
    print(f"   \u26a0\ufe0f  TELEGRAM_ADMIN_ID \u043d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d (\u0443\u043a\u0430\u0436\u0438\u0442\u0435 ваш ID)")
else:
    print(f"{OK} Chat ID: {chat_id}")

# ---- Baserow ----
print("\n\U0001f4ca Baserow...")
baserow_token = os.getenv("BASEROW_TOKEN", "")
baserow_table = os.getenv("BASEROW_LEADS_TABLE_ID", "0")
if not baserow_token:
    print(f"{FAIL} BASEROW_TOKEN \u043f\u0443\u0441\u0442\u043e\u0439!")
    all_ok = False
elif baserow_table == "0":
    print(f"{FAIL} BASEROW_LEADS_TABLE_ID \u043d\u0435 \u0437\u0430\u0434\u0430\u043d!")
    all_ok = False
else:
    try:
        r = requests.get(
            f"https://api.baserow.io/api/database/rows/table/{baserow_table}/?size=1",
            headers={"Authorization": f"Token {baserow_token}"},
            timeout=10
        )
        if r.status_code == 200:
            print(f"{OK} Baserow \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d, \u0442\u0430\u0431\u043b\u0438\u0446\u0430 {baserow_table} \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430")
        elif r.status_code == 401:
            print(f"{FAIL} \u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0439 \u0442\u043e\u043a\u0435\u043d Baserow!")
            all_ok = False
        elif r.status_code == 404:
            print(f"{FAIL} \u0422\u0430\u0431\u043b\u0438\u0446\u0430 {baserow_table} \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430!")
            all_ok = False
        else:
            print(f"{FAIL} \u0421\u0442\u0430\u0442\u0443\u0441: {r.status_code}")
            all_ok = False
    except Exception as e:
        print(f"{FAIL} \u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u043e\u0435\u0434\u0438\u043d\u0435\u043d\u0438\u044f: {e}")
        all_ok = False

# ---- amoCRM ----
print("\n\U0001f517 amoCRM...")
amo_domain = os.getenv("AMOCRM_DOMAIN", "")
amo_token = os.getenv("AMOCRM_ACCESS_TOKEN", "")
if not amo_domain:
    print(f"{FAIL} AMOCRM_DOMAIN \u043f\u0443\u0441\u0442\u043e\u0439!")
    all_ok = False
elif not amo_token:
    print(f"{FAIL} AMOCRM_ACCESS_TOKEN \u043f\u0443\u0441\u0442\u043e\u0439!")
    all_ok = False
else:
    try:
        r = requests.get(
            f"https://{amo_domain}.amocrm.ru/api/v4/account",
            headers={"Authorization": f"Bearer {amo_token}"},
            timeout=10
        )
        if r.status_code == 200:
            name = r.json().get("name", "")
            print(f"{OK} amoCRM \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d: {name}")
        elif r.status_code == 401:
            print(f"{FAIL} \u0422\u043e\u043a\u0435\u043d \u0438\u0441\u0442\u0451\u043a \u0438\u043b\u0438 \u043d\u0435\u0432\u0435\u0440\u043d\u044b\u0439! \u041d\u0443\u0436\u043d\u043e \u043e\u0431\u043d\u043e\u0432\u0438\u0442\u044c.")
            all_ok = False
        else:
            print(f"{FAIL} \u0421\u0442\u0430\u0442\u0443\u0441: {r.status_code}")
            all_ok = False
    except Exception as e:
        print(f"{FAIL} \u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u043e\u0435\u0434\u0438\u043d\u0435\u043d\u0438\u044f: {e}")
        all_ok = False

# ---- API Key ----
print("\n\U0001f510 \u0411\u0435\u0437\u043e\u043f\u0430\u0441\u043d\u043e\u0441\u0442\u044c...")
api_key = os.getenv("API_SECRET_KEY", "")
if not api_key or api_key in ("change-me-in-production", "your-secret-key-change-this"):
    print(f"   \u26a0\ufe0f  API_SECRET_KEY \u043d\u0435 \u0438\u0437\u043c\u0435\u043d\u0451\u043d!")
    print(f"       \u0421\u0433\u0435\u043d\u0435\u0440\u0438\u0440\u0443\u0439\u0442\u0435: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
else:
    print(f"{OK} API_SECRET_KEY \u0437\u0430\u0434\u0430\u043d ({len(api_key)} \u0441\u0438\u043c\u0432\u043e\u043b\u043e\u0432)")

# ---- \u0418\u0442\u043e\u0433 ----
print("\n" + "=" * 52)
if all_ok:
    print("\u2705  \u0412\u0441\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u0440\u0430\u0431\u043e\u0442\u0430\u044e\u0442! \u041c\u043e\u0436\u043d\u043e \u0437\u0430\u043f\u0443\u0441\u043a\u0430\u0442\u044c \u0431\u0435\u043a\u0435\u043d\u0434.")
else:
    print("\u26a0\ufe0f   \u0415\u0441\u0442\u044c \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u044b. \u0417\u0430\u043f\u043e\u043b\u043d\u0438\u0442\u0435 .env \u0438 \u0437\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u0435 \u0441\u043d\u043e\u0432\u0430.")
print("=" * 52)

sys.exit(0 if all_ok else 1)
