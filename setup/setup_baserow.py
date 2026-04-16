"""
setup_baserow.py
Автоматическая настройка Baserow:
  - Создаёт workspace
  - Создаёт database
  - Создаёт таблицы «Заявки» и «Логи» с полями
  - Записывает ID в .env

Запуск: python setup_baserow.py
"""

import sys
import os
import requests
from pathlib import Path

try:
    from dotenv import set_key, load_dotenv
except ImportError:
    print("❌ Библиотека python-dotenv не установлена!")
    print("   Выполните: pip install python-dotenv requests")
    sys.exit(1)

BASE_URL = "https://api.baserow.io/api"
TIMEOUT = 15
ENV_PATH = Path(__file__).resolve().parent.parent / "backend" / ".env"

LEADS_TABLE_NAME = "Заявки"
LEADS_FIELDS = [
    {"name": "name",           "type": "text"},
    {"name": "phone",          "type": "text"},
    {"name": "source",         "type": "text"},
    {"name": "concrete_grade", "type": "text"},
    {"name": "volume",         "type": "number", "number_decimal_places": 2, "number_negative": False},
    {"name": "address",        "type": "long_text"},
    {"name": "calculated_amount", "type": "number", "number_decimal_places": 2, "number_negative": False},
    {
        "name": "status",
        "type": "single_select",
        "select_options": [
            {"value": "Новая",    "color": "blue"},
            {"value": "В работе", "color": "orange"},
            {"value": "Завершена","color": "green"},
            {"value": "Отказ",    "color": "red"},
        ],
    },
    {"name": "lead_id",    "type": "number", "number_decimal_places": 0, "number_negative": False},
    {"name": "created_at", "type": "date", "date_include_time": True, "date_format": "ISO", "date_time_format": "24"},
]

LOGS_TABLE_NAME = "Логи"
LOGS_FIELDS = [
    {"name": "action",    "type": "text"},
    {"name": "error",     "type": "long_text"},
    {"name": "data",      "type": "long_text"},
    {"name": "timestamp", "type": "date", "date_include_time": True, "date_format": "ISO", "date_time_format": "24"},
]


def headers(token):
    return {"Authorization": f"Token {token}", "Content-Type": "application/json"}


def api_post(url, token, payload):
    try:
        r = requests.post(url, json=payload, headers=headers(token), timeout=TIMEOUT)
    except requests.ConnectionError:
        print(f"❌ Нет соединения с {url}")
        sys.exit(1)
    except requests.Timeout:
        print(f"❌ Таймаут запроса к {url}")
        sys.exit(1)
    if r.status_code not in (200, 201):
        print(f"❌ Ошибка API [{r.status_code}]: {url}")
        print(f"   Ответ: {r.text[:500]}")
        sys.exit(1)
    return r.json()


def api_get(url, token):
    try:
        r = requests.get(url, headers=headers(token), timeout=TIMEOUT)
    except requests.ConnectionError:
        print(f"❌ Нет соединения с {url}")
        sys.exit(1)
    except requests.Timeout:
        print(f"❌ Таймаут запроса к {url}")
        sys.exit(1)
    if r.status_code not in (200, 201):
        print(f"❌ Ошибка API [{r.status_code}]: {url}")
        print(f"   Ответ: {r.text[:500]}")
        sys.exit(1)
    return r.json()


def ensure_env_file():
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ENV_PATH.exists():
        ENV_PATH.touch()


def write_env(key, value):
    ensure_env_file()
    set_key(str(ENV_PATH), key, value)


def check_token(token):
    print("\n🔑 Проверяю токен Baserow...")
    url = f"{BASE_URL}/workspaces/"
    try:
        r = requests.get(url, headers=headers(token), timeout=TIMEOUT)
    except requests.ConnectionError:
        print("❌ Нет соединения с Baserow API.")
        sys.exit(1)
    except requests.Timeout:
        print("❌ Таймаут соединения с Baserow API.")
        sys.exit(1)
    if r.status_code == 401:
        print("❌ Неверный токен Baserow!")
        sys.exit(1)
    if r.status_code not in (200, 201):
        print(f"❌ Неожиданный ответ [{r.status_code}]: {r.text[:300]}")
        sys.exit(1)
    print("   ✅ Токен валидный")
    return r.json()


def create_workspace(token, existing_workspaces):
    print("\n📁 Шаг 1: Workspace...")
    for ws in existing_workspaces:
        if ws.get("name") == "Бетон CRM":
            ws_id = ws["id"]
            print(f"   ⏩ Workspace «Бетон CRM» уже существует (ID: {ws_id})")
            return ws_id
    data = api_post(f"{BASE_URL}/workspaces/", token, {"name": "Бетон CRM"})
    ws_id = data["id"]
    print(f"   ✅ Создан workspace «Бетон CRM» (ID: {ws_id})")
    return ws_id


def create_database(token, workspace_id):
    print("\n💾 Шаг 2: Database...")
    apps = api_get(f"{BASE_URL}/applications/workspace/{workspace_id}/", token)
    for app in apps:
        if app.get("name") == "Бетон БД" and app.get("type") == "database":
            db_id = app["id"]
            print(f"   ⏩ Database «Бетон БД» уже существует (ID: {db_id})")
            return db_id
    data = api_post(
        f"{BASE_URL}/applications/workspace/{workspace_id}/",
        token,
        {"name": "Бетон БД", "type": "database"},
    )
    db_id = data["id"]
    print(f"   ✅ Создана database «Бетон БД» (ID: {db_id})")
    return db_id


def create_table(token, db_id, table_name):
    tables = api_get(f"{BASE_URL}/database/tables/database/{db_id}/", token)
    for t in tables:
        if t.get("name") == table_name:
            t_id = t["id"]
            print(f"   ⏩ Таблица «{table_name}» уже существует (ID: {t_id})")
            return t_id
    data = api_post(f"{BASE_URL}/database/tables/database/{db_id}/", token, {"name": table_name})
    t_id = data["id"]
    print(f"   ✅ Создана таблица «{table_name}» (ID: {t_id})")
    return t_id


def get_existing_fields(token, table_id):
    return api_get(f"{BASE_URL}/database/fields/table/{table_id}/", token)


def create_fields(token, table_id, fields_def):
    existing = get_existing_fields(token, table_id)
    existing_names = {f["name"] for f in existing}

    for field in fields_def:
        fname = field["name"]
        if fname in existing_names:
            print(f"      ⏩ Поле «{fname}» уже есть — пропуск")
            continue

        payload = {"name": fname, "type": field["type"]}

        if field["type"] == "number":
            payload["number_decimal_places"] = field.get("number_decimal_places", 0)
            payload["number_negative"] = field.get("number_negative", False)
        elif field["type"] == "date":
            payload["date_include_time"] = field.get("date_include_time", False)
            payload["date_format"] = field.get("date_format", "ISO")
            if field.get("date_include_time"):
                payload["date_time_format"] = field.get("date_time_format", "24")

        data = api_post(f"{BASE_URL}/database/fields/table/{table_id}/", token, payload)
        field_id = data["id"]
        print(f"      ✅ Поле «{fname}» ({field['type']}) — ID: {field_id}")

        if field["type"] == "single_select" and "select_options" in field:
            patch_url = f"{BASE_URL}/database/fields/{field_id}/"
            try:
                r = requests.patch(
                    patch_url,
                    json={"select_options": field["select_options"]},
                    headers=headers(token),
                    timeout=TIMEOUT,
                )
                if r.status_code == 200:
                    opts = [o["value"] for o in field["select_options"]]
                    print(f"         ✅ Опции: {opts}")
                else:
                    print(f"         ⚠️ Опции: статус {r.status_code}")
            except Exception as e:
                print(f"         ⚠️ Не удалось добавить опции: {e}")


def run(token=None):
    print("=" * 55)
    print("  🗄️  НАСТРОЙКА BASEROW")
    print("=" * 55)

    if not token:
        token = input("\n🔑 Вставьте Baserow API-токен: ").strip()
    if not token:
        print("❌ Токен не может быть пустым!")
        sys.exit(1)

    existing_ws = check_token(token)
    ws_id = create_workspace(token, existing_ws)
    db_id = create_database(token, ws_id)

    print(f"\n📋 Шаг 3: Таблица «{LEADS_TABLE_NAME}»...")
    leads_table_id = create_table(token, db_id, LEADS_TABLE_NAME)
    print(f"   Создаю поля:")
    create_fields(token, leads_table_id, LEADS_FIELDS)

    print(f"\n📋 Шаг 4: Таблица «{LOGS_TABLE_NAME}»...")
    logs_table_id = create_table(token, db_id, LOGS_TABLE_NAME)
    print(f"   Создаю поля:")
    create_fields(token, logs_table_id, LOGS_FIELDS)

    print(f"\n💾 Шаг 5: Запись в .env ({ENV_PATH})...")
    write_env("BASEROW_TOKEN", token)
    write_env("BASEROW_LEADS_TABLE_ID", str(leads_table_id))
    write_env("BASEROW_LOGS_TABLE_ID", str(logs_table_id))
    print("   ✅ .env обновлён")

    print("\n" + "=" * 55)
    print("  ✅ Baserow настроен!")
    print(f"     БД: Бетон БД (ID: {db_id})")
    print(f"     Таблица Заявки: ID {leads_table_id}")
    print(f"     Таблица Логи:   ID {logs_table_id}")
    print("=" * 55)

    return {
        "success": True,
        "db_id": db_id,
        "leads_table_id": leads_table_id,
        "logs_table_id": logs_table_id,
    }


if __name__ == "__main__":
    run()
