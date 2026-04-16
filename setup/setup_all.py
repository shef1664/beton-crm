"""
setup_all.py
Мастер-скрипт: настраивает всё за один запуск.

  0. Telegram — токен бота и chat_id
  1. Baserow — создаёт БД, таблицы, поля
  2. amoCRM — создаёт воронку с этапами
  3. Безопасность — генерирует API_KEY
  4. Проверка — запускает test_connections.py

Запуск: python setup_all.py
"""

import sys
import os
import subprocess
import secrets
from pathlib import Path

try:
    from dotenv import load_dotenv, set_key
except ImportError:
    print("❌ Библиотека python-dotenv не установлена!")
    print("   Выполните: pip install python-dotenv requests")
    sys.exit(1)


# ─── Пути ────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR.parent / "backend" / ".env"
TEST_SCRIPT = SCRIPT_DIR.parent / "backend" / "test_connections.py"


# ═════════════════════════════════════════════════════════════
#  Утилиты
# ═════════════════════════════════════════════════════════════

def banner(text: str):
    width = 60
    print("\n")
    print("═" * width)
    print(f"  {text}")
    print("═" * width)


def separator():
    print("\n" + "─" * 60)


def ensure_env_file():
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ENV_PATH.exists():
        ENV_PATH.touch()
        print(f"📄 Создан: {ENV_PATH}")


def write_env(key: str, value: str):
    ensure_env_file()
    set_key(str(ENV_PATH), key, value)


def read_env(key: str) -> str:
    if ENV_PATH.exists():
        load_dotenv(str(ENV_PATH), override=True)
    return os.getenv(key, "").strip()


def ask(prompt: str, required: bool = True, env_key: str = None) -> str:
    if env_key:
        existing = read_env(env_key)
        if existing:
            masked = existing[:8] + "..." if len(existing) > 12 else existing
            use = input(f"   Найдено в .env: {masked} — использовать? (y/n) [y]: ").strip().lower()
            if use != "n":
                return existing

    value = input(f"   {prompt}: ").strip()

    if required and not value:
        print("   ❌ Значение не может быть пустым!")
        sys.exit(1)

    return value


# ═════════════════════════════════════════════════════════════
#  ШАГ 0: Telegram
# ═════════════════════════════════════════════════════════════

def setup_telegram():
    banner("📱 ШАГ 0: TELEGRAM (опционально)")

    print("\n   Для Telegram-уведомлений нужны:")
    print("   • Bot Token — получите у @BotFather в Telegram")
    print("   • Chat ID — ID чата куда слать уведомления")
    print()

    skip = input("   Настроить Telegram сейчас? (y/n) [y]: ").strip().lower()
    if skip == "n":
        print("   ⏩ Пропущено — настроите позже в .env")
        return False

    token = ask("Bot Token (от @BotFather)", required=False, env_key="TELEGRAM_BOT_TOKEN")
    if token:
        write_env("TELEGRAM_BOT_TOKEN", token)

        import requests as req
        try:
            r = req.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
            if r.status_code == 200:
                bot_name = r.json().get("result", {}).get("username", "?")
                print(f"   ✅ Бот найден: @{bot_name}")
            else:
                print(f"   ⚠️ Токен не прошёл проверку (статус {r.status_code})")
        except Exception as e:
            print(f"   ⚠️ Не удалось проверить: {e}")

    chat_id = ask("Chat ID (например -1001234567890)", required=False, env_key="TELEGRAM_CHAT_ID")
    if chat_id:
        write_env("TELEGRAM_CHAT_ID", chat_id)

    print("   ✅ Telegram — записано в .env")
    return True


# ═════════════════════════════════════════════════════════════
#  ШАГ 1: Baserow
# ═════════════════════════════════════════════════════════════

def setup_baserow_step():
    banner("🗄️  ШАГ 1: BASEROW")

    print("\n   Для Baserow нужен API-токен.")
    print("   Как получить:")
    print("   1. Зайдите на https://baserow.io")
    print("   2. Зарегистрируйтесь / войдите")
    print("   3. Иконка профиля → Settings → API Tokens")
    print("   4. Create Token → скопируйте токен")
    print()

    token = ask("Baserow API-токен", required=True, env_key="BASEROW_TOKEN")

    separator()

    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        import setup_baserow
        result = setup_baserow.run(token=token)
        return result
    except SystemExit:
        print("\n❌ Настройка Baserow завершилась с ошибкой.")
        cont = input("   Продолжить без Baserow? (y/n) [n]: ").strip().lower()
        if cont != "y":
            sys.exit(1)
        return {"success": False}
    except ImportError:
        print("❌ Не найден файл setup_baserow.py!")
        print(f"   Ожидается в: {SCRIPT_DIR / 'setup_baserow.py'}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Непредвиденная ошибка Baserow: {e}")
        cont = input("   Продолжить? (y/n) [n]: ").strip().lower()
        if cont != "y":
            sys.exit(1)
        return {"success": False}


# ═════════════════════════════════════════════════════════════
#  ШАГ 2: amoCRM
# ═════════════════════════════════════════════════════════════

def setup_amocrm_step():
    banner("🔗 ШАГ 2: amoCRM")

    print("\n   Для amoCRM нужны:")
    print("   • Домен — из URL (mycompany из mycompany.amocrm.ru)")
    print("   • Access Token — из настроек интеграции")
    print()
    print("   Как получить токен:")
    print("   1. amoCRM → Настройки → Интеграции")
    print("   2. Создайте или откройте интеграцию")
    print("   3. Скопируйте access_token")
    print()

    skip = input("   Настроить amoCRM сейчас? (y/n) [y]: ").strip().lower()
    if skip == "n":
        print("   ⏩ Пропущено — настроите позже")
        return {"success": False}

    domain = ask("Домен amoCRM (без .amocrm.ru)", required=True, env_key="AMOCRM_DOMAIN")
    domain = (
        domain
        .replace("https://", "")
        .replace("http://", "")
        .replace(".amocrm.ru", "")
        .strip("/")
        .strip()
    )

    access_token = ask("Access Token amoCRM", required=True, env_key="AMOCRM_ACCESS_TOKEN")

    separator()

    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        import setup_amocrm
        result = setup_amocrm.run(domain=domain, access_token=access_token)
        return result
    except SystemExit:
        print("\n❌ Настройка amoCRM завершилась с ошибкой.")
        cont = input("   Продолжить без amoCRM? (y/n) [n]: ").strip().lower()
        if cont != "y":
            sys.exit(1)
        return {"success": False}
    except ImportError:
        print("❌ Не найден файл setup_amocrm.py!")
        print(f"   Ожидается в: {SCRIPT_DIR / 'setup_amocrm.py'}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Непредвиденная ошибка amoCRM: {e}")
        cont = input("   Продолжить? (y/n) [n]: ").strip().lower()
        if cont != "y":
            sys.exit(1)
        return {"success": False}


# ═════════════════════════════════════════════════════════════
#  ШАГ 3: Безопасность
# ═════════════════════════════════════════════════════════════

def setup_security():
    banner("🔐 ШАГ 3: БЕЗОПАСНОСТЬ")

    current_api = read_env("API_KEY")
    if current_api and current_api != "change-me-in-production":
        print(f"\n   API_KEY уже задан ({len(current_api)} символов)")
        change = input("   Перегенерировать? (y/n) [n]: ").strip().lower()
        if change != "y":
            print("   ⏩ Оставляю текущий")
        else:
            new_key = secrets.token_urlsafe(32)
            write_env("API_KEY", new_key)
            print(f"   ✅ Новый API_KEY ({len(new_key)} символов)")
    else:
        if current_api == "change-me-in-production":
            print("\n   ⚠️ API_KEY = 'change-me-in-production' — заглушка!")
        else:
            print("\n   API_KEY не задан")
        new_key = secrets.token_urlsafe(32)
        write_env("API_KEY", new_key)
        print(f"   ✅ Сгенерирован API_KEY ({len(new_key)} символов)")

    current_secret = read_env("SECRET_KEY")
    if not current_secret or current_secret in ("change-me-too", ""):
        new_secret = secrets.token_urlsafe(32)
        write_env("SECRET_KEY", new_secret)
        print(f"   ✅ Сгенерирован SECRET_KEY ({len(new_secret)} символов)")
    else:
        print(f"   ✅ SECRET_KEY уже задан ({len(current_secret)} символов)")

    current_debug = read_env("DEBUG")
    if not current_debug:
        write_env("DEBUG", "false")
        print("   ✅ DEBUG=false (продакшн-режим)")

    current_origins = read_env("ALLOWED_ORIGINS")
    if not current_origins:
        write_env("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:5500")
        print("   ✅ ALLOWED_ORIGINS задан (localhost)")

    print("\n   🔒 Безопасность настроена")


# ═════════════════════════════════════════════════════════════
#  ШАГ 4: Тест подключений
# ═════════════════════════════════════════════════════════════

def run_connection_test() -> bool:
    banner("🧪 ШАГ 4: ПРОВЕРКА ПОДКЛЮЧЕНИЙ")

    if not TEST_SCRIPT.exists():
        print(f"\n   ⚠️ Файл test_connections.py не найден, запускаю встроенный тест...\n")
        return run_inline_test()

    print(f"\n   Запускаю: {TEST_SCRIPT.name}\n")
    try:
        result = subprocess.run(
            [sys.executable, str(TEST_SCRIPT)],
            cwd=str(TEST_SCRIPT.parent),
            timeout=60,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("   ⚠️ Тест превысил время ожидания (60 сек)")
        return False
    except Exception as e:
        print(f"   ❌ Ошибка запуска теста: {e}")
        return False


def run_inline_test() -> bool:
    import requests as req
    load_dotenv(str(ENV_PATH), override=True)
    all_ok = True

    print("   📱 Telegram...")
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if tg_token:
        try:
            r = req.get(f"https://api.telegram.org/bot{tg_token}/getMe", timeout=10)
            if r.status_code == 200:
                name = r.json().get("result", {}).get("username", "?")
                print(f"      ✅ Бот: @{name}")
            else:
                print(f"      ❌ Статус {r.status_code}")
                all_ok = False
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
            all_ok = False
    else:
        print("      ⏩ Не настроен")

    print("   🔗 amoCRM...")
    amo_domain = os.getenv("AMOCRM_DOMAIN", "")
    amo_token = os.getenv("AMOCRM_ACCESS_TOKEN", "")
    if amo_domain and amo_token:
        try:
            r = req.get(
                f"https://{amo_domain}.amocrm.ru/api/v4/account",
                headers={"Authorization": f"Bearer {amo_token}"},
                timeout=10,
            )
            if r.status_code == 200:
                name = r.json().get("name", "?")
                print(f"      ✅ Аккаунт: «{name}»")
            else:
                print(f"      ❌ Статус {r.status_code}")
                all_ok = False
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
            all_ok = False
    else:
        print("      ⏩ Не настроен")

    print("   🔐 Безопасность...")
    api_key = os.getenv("API_KEY", "")
    if api_key and api_key != "change-me-in-production":
        print(f"      ✅ API_KEY задан ({len(api_key)} символов)")
    else:
        print("      ❌ API_KEY не задан!")
        all_ok = False

    return all_ok


# ═════════════════════════════════════════════════════════════
#  Итоговый отчёт
# ═════════════════════════════════════════════════════════════

def print_summary(results: dict):
    width = 60
    print("\n\n")
    print("╔" + "═" * width + "╗")
    print("║" + "  📋 ИТОГОВЫЙ ОТЧЁТ".center(width) + "║")
    print("╠" + "═" * width + "╣")

    load_dotenv(str(ENV_PATH), override=True)

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_status = "✅ Настроен" if tg_token else "⏩ Пропущен"
    line = f"  📱 Telegram:    {tg_status}"
    print(f"║{line.ljust(width)}║")

    br = results.get("baserow", {})
    if br.get("success"):
        print(f"║{'  🗄️  Baserow:     ✅ Настроен'.ljust(width)}║")
        print(f"║{'      Заявки:     ID ' + str(br.get('leads_table_id', '?')).ljust(width - 20)!s:}{' ' * 1}║")
        print(f"║{'      Логи:       ID ' + str(br.get('logs_table_id', '?')):<{width}}║")
    else:
        print(f"║{'  🗄️  Baserow:     ❌ Не настроен'.ljust(width)}║")

    amo = results.get("amocrm", {})
    if amo.get("success"):
        print(f"║{'  🔗 amoCRM:      ✅ Настроен'.ljust(width)}║")
        print(f"║{'      Воронка:    ID ' + str(amo.get('pipeline_id', '?')):<{width}}║")
        print(f"║{'      Этапов:     ' + str(len(amo.get('statuses', {}))) + ' шт.':<{width}}║")
    else:
        print(f"║{'  🔗 amoCRM:      ❌ Не настроен'.ljust(width)}║")

    api_key = os.getenv("API_KEY", "")
    sec_ok = api_key and api_key != "change-me-in-production"
    sec_status = "✅ API_KEY задан" if sec_ok else "❌ API_KEY не задан!"
    print(f"║{'  🔐 Безопасность: ' + sec_status:<{width}}║")

    test_ok = results.get("test_ok", False)
    test_status = "✅ Все проверки пройдены" if test_ok else "⚠️ Есть проблемы"
    print(f"║{'  🧪 Тест:        ' + test_status:<{width}}║")

    print("╠" + "═" * width + "╣")
    env_str = str(ENV_PATH)
    if len(env_str) > width - 8:
        env_str = "..." + env_str[-(width - 11):]
    print(f"║{'  📁 .env: ' + env_str:<{width}}║")
    print("╠" + "═" * width + "╣")

    all_success = br.get("success") and amo.get("success") and sec_ok

    if all_success and test_ok:
        print(f"║{'  🚀 СИСТЕМА ГОТОВА К РАБОТЕ!'.center(width)}║")
        print("╚" + "═" * width + "╝")
        print("\n   Следующие шаги:")
        print("   1. cd backend && uvicorn main:app --reload")
        print("   2. Откройте лендинг и отправьте тестовую заявку")
        print("   3. Проверьте уведомление в Telegram")
    else:
        print(f"║{'  ⚠️  Настройка не завершена'.center(width)}║")
        print("╚" + "═" * width + "╝")
        print("\n   Что не настроено:")
        if not br.get("success"):
            print("   ❌ Baserow — запустите: python setup_baserow.py")
        if not amo.get("success"):
            print("   ❌ amoCRM — запустите: python setup_amocrm.py")
        if not sec_ok:
            print("   ❌ API_KEY — добавьте в .env")
        if not tg_token:
            print("   ⏩ Telegram — опционально, добавьте токен в .env")


# ═════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════

def main():
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                                                            ║")
    print("║   🏗️  АВТОНАСТРОЙКА СИСТЕМЫ «БЕТОН CRM»                   ║")
    print("║                                                            ║")
    print("║   Этот скрипт настроит:                                    ║")
    print("║   • Telegram — уведомления о заявках                       ║")
    print("║   • Baserow — база данных                                  ║")
    print("║   • amoCRM — воронка продаж                                ║")
    print("║   • Ключи безопасности                                     ║")
    print("║                                                            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"\n   📁 .env будет сохранён в: {ENV_PATH}")
    input("\n   Нажмите Enter чтобы начать...")

    results = {}

    try:
        setup_telegram()
    except (KeyboardInterrupt, SystemExit):
        print("\n\n   ⛔ Прервано")
        sys.exit(0)
    except Exception as e:
        print(f"\n   ⚠️ Ошибка Telegram: {e}")

    try:
        results["baserow"] = setup_baserow_step()
    except (KeyboardInterrupt, SystemExit):
        print("\n\n   ⛔ Прервано")
        sys.exit(0)

    try:
        results["amocrm"] = setup_amocrm_step()
    except (KeyboardInterrupt, SystemExit):
        print("\n\n   ⛔ Прервано")
        sys.exit(0)

    try:
        setup_security()
    except Exception as e:
        print(f"\n   ⚠️ Ошибка безопасности: {e}")

    try:
        results["test_ok"] = run_connection_test()
    except Exception as e:
        print(f"\n   ⚠️ Ошибка теста: {e}")
        results["test_ok"] = False

    print_summary(results)


if __name__ == "__main__":
    main()
