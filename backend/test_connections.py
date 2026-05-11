"""
Connectivity check for external services used by the concrete sales backend.
"""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

OK = "   [OK]"
FAIL = "   [FAIL]"

print("=" * 52)
print("CONNECTIVITY CHECK")
print("=" * 52)

all_ok = True

print("\nTelegram...")
token = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not token:
    print(f"{FAIL} TELEGRAM_BOT_TOKEN is empty")
    all_ok = False
else:
    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        data = response.json()
        if data.get("ok"):
            print(f"{OK} Bot connected: @{data['result']['username']}")
        else:
            print(f"{FAIL} Error: {data.get('description')}")
            all_ok = False
    except Exception as e:
        print(f"{FAIL} Telegram connection error: {e}")
        all_ok = False

chat_id = os.getenv("TELEGRAM_ADMIN_ID", "")
if not chat_id or chat_id == "150420":
    print("   [WARN] TELEGRAM_ADMIN_ID is not configured")
else:
    print(f"{OK} Chat ID: {chat_id}")

print("\nStorage...")
baserow_token = os.getenv("BASEROW_TOKEN", "")
baserow_table = os.getenv("BASEROW_LEADS_TABLE_ID", "0")
if not baserow_token or baserow_table == "0":
    print("   [WARN] Baserow is not configured, SQLite fallback will be used")
else:
    try:
        response = requests.get(
            f"https://api.baserow.io/api/database/rows/table/{baserow_table}/?size=1",
            headers={"Authorization": f"Token {baserow_token}"},
            timeout=10,
        )
        if response.status_code == 200:
            print(f"{OK} Baserow available, table {baserow_table}")
        elif response.status_code == 401:
            print(f"{FAIL} Invalid Baserow token")
            all_ok = False
        elif response.status_code == 404:
            print(f"{FAIL} Baserow table {baserow_table} not found")
            all_ok = False
        else:
            print(f"{FAIL} Baserow status: {response.status_code}")
            all_ok = False
    except Exception as e:
        print(f"{FAIL} Baserow connection error: {e}")
        all_ok = False

print("\namoCRM...")
amo_domain = os.getenv("AMOCRM_DOMAIN", "")
amo_token = os.getenv("AMOCRM_ACCESS_TOKEN", "")
if not amo_domain or not amo_token:
    print("   [WARN] amoCRM is not configured, leads will be stored locally")
else:
    try:
        response = requests.get(
            f"https://{amo_domain}.amocrm.ru/api/v4/account",
            headers={"Authorization": f"Bearer {amo_token}"},
            timeout=10,
        )
        if response.status_code == 200:
            print(f"{OK} amoCRM connected: {response.json().get('name', '')}")
        elif response.status_code == 401:
            print(f"{FAIL} amoCRM token is invalid or expired")
            all_ok = False
        else:
            print(f"{FAIL} amoCRM status: {response.status_code}")
            all_ok = False
    except Exception as e:
        print(f"{FAIL} amoCRM connection error: {e}")
        all_ok = False

print("\nSecurity...")
api_key = os.getenv("API_SECRET_KEY", "")
if not api_key or api_key in ("change-me-in-production", "your-secret-key-change-this"):
    print("   [WARN] API_SECRET_KEY is not changed")
else:
    print(f"{OK} API_SECRET_KEY is set ({len(api_key)} chars)")

print("\n" + "=" * 52)
if all_ok:
    print("[OK] External integrations look healthy")
else:
    print("[WARN] Some integrations need setup, but SQLite fallback keeps local flow usable")
print("=" * 52)

sys.exit(0 if all_ok else 1)
