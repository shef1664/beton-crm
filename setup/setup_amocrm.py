"""
setup_amocrm.py
Автоматическая настройка amoCRM:
  - Проверяет токен
  - Создаёт воронку «Продажи бетона» с 5 этапами
  - Записывает pipeline_id в .env
  - Сохраняет ID этапов в pipeline_statuses.json

Запуск: python setup_amocrm.py
"""

import sys
import os
import json
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv, set_key
except ImportError:
    print("❌ Библиотека python-dotenv не установлена!")
    print("   Выполните: pip install python-dotenv requests")
    sys.exit(1)

TIMEOUT = 15
ENV_PATH = Path(__file__).resolve().parent.parent / "backend" / ".env"
STATUSES_JSON_PATH = Path(__file__).resolve().parent / "pipeline_statuses.json"

STATUS_KEY_MAP = {
    "Новый лид":           "new",
    "Сбор данных":         "data_collection",
    "Расчёт отправлен":    "calculation",
    "Горячий":             "hot_lead",
    "Сделка подтверждена": "confirmed",
}

PIPELINE_PAYLOAD = [
    {
        "name": "Продажи бетона",
        "is_main": True,
        "_embedded": {
            "statuses": [
                {"name": "Новый лид",           "sort": 10, "color": "#99ccff"},
                {"name": "Сбор данных",         "sort": 20, "color": "#ffcc99"},
                {"name": "Расчёт отправлен",    "sort": 30, "color": "#ffff99"},
                {"name": "Горячий",             "sort": 40, "color": "#ff9900"},
                {"name": "Сделка подтверждена", "sort": 50, "color": "#99ff99"},
            ]
        },
    }
]


def amo_headers(access_token):
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


def ensure_env_file():
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ENV_PATH.exists():
        ENV_PATH.touch()


def write_env(key, value):
    ensure_env_file()
    set_key(str(ENV_PATH), key, value)


def check_token(domain, token):
    print("\n🔑 Шаг 1: Проверяю подключение к amoCRM...")
    url = f"https://{domain}.amocrm.ru/api/v4/account"
    try:
        r = requests.get(url, headers=amo_headers(token), timeout=TIMEOUT)
    except requests.ConnectionError:
        print(f"❌ Нет соединения с {domain}.amocrm.ru")
        print("   Проверьте домен и интернет-соединение.")
        sys.exit(1)
    except requests.Timeout:
        print("❌ Таймаут соединения с amoCRM.")
        sys.exit(1)
    if r.status_code == 401:
        print("❌ Неверный или истёкший access_token!")
        sys.exit(1)
    if r.status_code not in (200, 201):
        print(f"❌ Неожиданный ответ [{r.status_code}]: {r.text[:300]}")
        sys.exit(1)
    data = r.json()
    print(f"   ✅ Подключено: «{data.get('name', '—')}» (ID: {data.get('id', '—')})")
    return data


def check_existing_pipeline(domain, token):
    url = f"https://{domain}.amocrm.ru/api/v4/leads/pipelines"
    try:
        r = requests.get(url, headers=amo_headers(token), timeout=TIMEOUT)
        if r.status_code == 200:
            for p in r.json().get("_embedded", {}).get("pipelines", []):
                if p.get("name") == "Продажи бетона":
                    return p
    except Exception:
        pass
    return None


def create_pipeline(domain, token):
    print("\n🔧 Шаг 2: Создание воронки «Продажи бетона»...")
    existing = check_existing_pipeline(domain, token)
    if existing:
        print(f"   ⏩ Воронка уже существует (ID: {existing['id']})")
        return existing
    url = f"https://{domain}.amocrm.ru/api/v4/leads/pipelines"
    try:
        r = requests.post(url, json=PIPELINE_PAYLOAD, headers=amo_headers(token), timeout=TIMEOUT)
    except requests.ConnectionError:
        print("❌ Нет соединения с amoCRM при создании воронки.")
        sys.exit(1)
    except requests.Timeout:
        print("❌ Таймаут при создании воронки.")
        sys.exit(1)
    if r.status_code not in (200, 201):
        print(f"❌ Ошибка создания воронки [{r.status_code}]: {r.text[:500]}")
        sys.exit(1)
    data = r.json()
    if "_embedded" in data:
        pipeline = data["_embedded"]["pipelines"][0]
    elif isinstance(data, list):
        pipeline = data[0]
    else:
        pipeline = data
    print(f"   ✅ Воронка создана (ID: {pipeline.get('id')})")
    return pipeline


def extract_statuses(pipeline):
    print("\n📊 Шаг 3: Извлечение ID этапов...")
    statuses_list = (
        pipeline.get("_embedded", {}).get("statuses", [])
        or pipeline.get("statuses", [])
    )
    result = {}
    for status in statuses_list:
        s_name = status.get("name", "")
        s_id = status.get("id")
        if s_name in ("Успешно реализовано", "Закрыто и не реализовано"):
            print(f"   ⏩ «{s_name}» — системный, пропуск")
            continue
        key = STATUS_KEY_MAP.get(s_name)
        if key:
            result[key] = s_id
            print(f"   ✅ «{s_name}» → {key} = {s_id}")
        else:
            print(f"   ℹ️  «{s_name}» (ID: {s_id}) — не в маппинге")
    return result


def reload_statuses(domain, token, pipeline_id):
    print("\n🔄 Загружаю этапы отдельным запросом...")
    url = f"https://{domain}.amocrm.ru/api/v4/leads/pipelines/{pipeline_id}/statuses"
    try:
        r = requests.get(url, headers=amo_headers(token), timeout=TIMEOUT)
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return {}
    if r.status_code != 200:
        print(f"   ❌ Статус {r.status_code}: {r.text[:300]}")
        return {}
    result = {}
    for status in r.json().get("_embedded", {}).get("statuses", []):
        s_name = status.get("name", "")
        s_id = status.get("id")
        if s_name in ("Успешно реализовано", "Закрыто и не реализовано"):
            continue
        key = STATUS_KEY_MAP.get(s_name)
        if key:
            result[key] = s_id
            print(f"   ✅ «{s_name}» → {key} = {s_id}")
    return result


def save_results(domain, token, pipeline_id, statuses):
    print(f"\n💾 Шаг 4: Запись в .env ({ENV_PATH})...")
    write_env("AMOCRM_DOMAIN", domain)
    write_env("AMOCRM_ACCESS_TOKEN", token)
    write_env("AMOCRM_PIPELINE_ID", str(pipeline_id))
    print("   ✅ .env обновлён")

    print(f"\n📄 Шаг 5: Сохраняю этапы → {STATUSES_JSON_PATH.name}...")
    with open(STATUSES_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(statuses, f, indent=2, ensure_ascii=False)
    print(f"   ✅ Файл сохранён: {STATUSES_JSON_PATH}")


def run(domain=None, access_token=None):
    print("=" * 55)
    print("  🔗 НАСТРОЙКА amoCRM")
    print("=" * 55)

    if ENV_PATH.exists():
        load_dotenv(str(ENV_PATH))

    if not domain:
        domain = os.getenv("AMOCRM_DOMAIN", "").strip()
    if not domain:
        print("\n🌐 Введите домен amoCRM.")
        print("   Пример: если URL https://mycompany.amocrm.ru → введите: mycompany")
        domain = input("\n   Домен: ").strip()
    if not domain:
        print("❌ Домен не может быть пустым!")
        sys.exit(1)
    domain = domain.replace("https://", "").replace("http://", "").replace(".amocrm.ru", "").strip("/").strip()

    if not access_token:
        access_token = os.getenv("AMOCRM_ACCESS_TOKEN", "").strip()
    if not access_token:
        access_token = input("🔑 Вставьте access_token amoCRM: ").strip()
    if not access_token:
        print("❌ Токен не может быть пустым!")
        sys.exit(1)

    check_token(domain, access_token)
    pipeline = create_pipeline(domain, access_token)
    pipeline_id = pipeline.get("id")

    if not pipeline_id:
        print("❌ Не удалось получить ID воронки!")
        sys.exit(1)

    statuses = extract_statuses(pipeline)
    if len(statuses) < 3:
        print(f"\n   ⚠️ Найдено только {len(statuses)} этапов из 5. Пробую ещё раз...")
        retry = reload_statuses(domain, access_token, pipeline_id)
        if len(retry) > len(statuses):
            statuses = retry

    save_results(domain, access_token, pipeline_id, statuses)

    print("\n" + "=" * 55)
    print("  ✅ amoCRM настроен!")
    print(f"     Аккаунт: {domain}.amocrm.ru")
    print(f"     Воронка: Продажи бетона (ID: {pipeline_id})")
    print(f"     Этапов:  {len(statuses)} создано")
    for key, sid in statuses.items():
        print(f"       • {key}: {sid}")
    print("=" * 55)

    return {"success": True, "pipeline_id": pipeline_id, "statuses": statuses}


if __name__ == "__main__":
    run()
