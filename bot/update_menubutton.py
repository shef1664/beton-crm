"""
Обновить Menu Button для @pulsar_daily_report_bot
Нужно ввести правильный токен от BotFather
"""

import requests

# ВВЕДИТЕ ТОКЕН СЮДА (возьмите из BotFather → @pulsar_daily_report_bot → Bot Settings → Token)
BOT_TOKEN = input("Введите токен бота из BotFather: ").strip()

WEBAPP_URL = "https://shef1664.github.io/smart-fleet-app"

print("\n🔄 Проверяю токен...")

# Проверяем токен
url_get_me = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
response = requests.get(url_get_me)
data = response.json()

if not data.get("ok"):
    print(f"❌ Токен не работает: {data}")
    print("Получите токен: BotFather → @pulsar_daily_report_bot → Bot Settings → Token")
    input("\nНажмите Enter для выхода...")
    exit()

bot_info = data["result"]
print(f"✅ Бот найден: @{bot_info['username']} (ID: {bot_info['id']})")

print("\n🔄 Обновляю Menu Button...")

# Обновляем Menu Button для ВСЕХ пользователей
url_set_menu = f"https://api.telegram.org/bot{BOT_TOKEN}/setChatMenuButton"

payload = {
    "menu_button": {
        "type": "web_app",
        "text": "📱 Открыть приложение",
        "web_app": {
            "url": WEBAPP_URL
        }
    }
}

response = requests.post(url_set_menu, json=payload)
result = response.json()

if result.get("ok"):
    print(f"\n✅ MENU BUTTON ОБНОВЛЁН!")
    print(f"   URL: {WEBAPP_URL}")
    print(f"   Текст: 📱 Открыть приложение")
    print("\n" + "=" * 60)
    print("ТЕПЕРЬ В TELEGRAM:")
    print("1. Закройте Telegram полностью")
    print("2. Откройте заново")  
    print("3. Найдите @pulsar_daily_report_bot")
    print("4. Нажмите кнопку 'Меню' слева от поля ввода")
    print("=" * 60)
else:
    print(f"❌ Ошибка: {result}")

input("\nНажмите Enter для выхода...")
