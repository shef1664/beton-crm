"""
Скрипт для получения access_token amoCRM через OAuth2.

Инструкция:
1. Войдите в amoCRM → Настройки → Интеграции → Создать интеграцию
2. Укажите Redirect URL: https://your-backend.onrender.com/api/amocrm/callback
3. Скопируйте CLIENT_ID и CLIENT_SECRET
4. Нажмите "Авторизовать" → вы попадёте на страницу amoCRM → разрешите доступ
5. Из URL скопируйте параметр ?code=XXXXXXXX
6. Вставьте все данные ниже и запустите: python get_amo_token.py
"""

import requests

# ============================
# ВСТАВЬТЕ СВОИ ДАННЫЕ:
# ============================
AMOCRM_DOMAIN   = ""   # Например: mycompany  (без .amocrm.ru)
CLIENT_ID       = ""   # UUID из настроек интеграции
CLIENT_SECRET   = ""   # Секрет из настроек интеграции
AUTH_CODE       = ""   # Код из URL после авторизации (?code=...)
REDIRECT_URI    = ""   # Тот же URL что указали в интеграции
# ============================

def main():
    if not all([AMOCRM_DOMAIN, CLIENT_ID, CLIENT_SECRET, AUTH_CODE, REDIRECT_URI]):
        print("❌ Заполните все переменные в начале скрипта!")
        return

    url = f"https://{AMOCRM_DOMAIN}.amocrm.ru/oauth2/access_token"

    payload = {
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type":    "authorization_code",
        "code":          AUTH_CODE,
        "redirect_uri":  REDIRECT_URI,
    }

    print(f"Запрос токена для {AMOCRM_DOMAIN}.amocrm.ru ...")

    try:
        r = requests.post(url, json=payload, timeout=15)
        data = r.json()

        if r.status_code == 200 and "access_token" in data:
            print("\n✅ Токены получены! Добавьте в .env:\n")
            print(f"AMOCRM_DOMAIN={AMOCRM_DOMAIN}")
            print(f"AMOCRM_CLIENT_ID={CLIENT_ID}")
            print(f"AMOCRM_CLIENT_SECRET={CLIENT_SECRET}")
            print(f"AMOCRM_ACCESS_TOKEN={data['access_token']}")
            print(f"AMOCRM_REFRESH_TOKEN={data['refresh_token']}")
            print(f"AMOCRM_REDIRECT_URI={REDIRECT_URI}")
            print(f"\n⚠️  ACCESS_TOKEN истекает через {data.get('expires_in', '?')} секунд (~24ч)")
            print("⚠️  Сохраните REFRESH_TOKEN — он нужен для автообновления!")
        else:
            print(f"❌ Ошибка {r.status_code}: {data}")
            hint = data.get("hint", "")
            if "authorization_code" in hint.lower() or r.status_code == 400:
                print("\n💡 Подсказка: код авторизации одноразовый и истекает быстро.")
                print("   Повторите процедуру авторизации и сразу запустите скрипт.")

    except Exception as e:
        print(f"❌ Ошибка соединения: {e}")


if __name__ == "__main__":
    main()
