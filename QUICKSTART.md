# 🚀 БЫСТРЫЙ ЗАПУСК

## Что уже готово:

✅ Backend (FastAPI) с API для лендингов
✅ Telegram бот @otdprod (код готов)
✅ Лендинг загружает данные из backend
✅ Цены, тексты, контакты — всё в JSON
✅ Форма заявки создаёт лид
✅ Калькулятор бетона
✅ Антидубли по телефону
✅ Логирование в Baserow
✅ Уведомления в Telegram

---

## Как запустить локально (для теста):

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Откройте: http://localhost:8000

Лендинг: откройте `landing-main/index.html` в браузере

---

## Деплой на Render.com (бесплатно):

1. Зарегистрируйтесь на https://render.com
2. Нажмите "New Web Service"
3. Подключите GitHub аккаунт
4. Выберите репозиторий `АНОМАЛЬНЫЙ_ЛЕНДИНГ`
5. Настройки:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Environment Variables (добавьте из `.env.example`):
   - `AMOCRM_DOMAIN` (пока оставьте пустым)
   - `TELEGRAM_BOT_TOKEN` (получите от BotFather)
   - `TELEGRAM_ADMIN_ID` (ваш Telegram ID)
   - `BASEROW_TOKEN` (получите от Baserow)
7. Нажмите "Create Web Service"
8. Подождите 2-3 минуты
9. Получите URL типа: `https://beton-xxx.onrender.com`

---

## Как обновить лендинг:

Скажите мне: "обнови цены на бетоне" или "измени телефон на 8-999-123-45-67"

Я обновлю `backend/data/landing_config.json` и всё автоматически изменится на сайте!

---

## Как подключить amoCRM позже:

1. Получите API ключи из amoCRM
2. Скажите мне ключи
3. Я обновлю `.env` и всё заработает

---

## Текущие API endpoints:

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/landing-data` | Данные для лендинга |
| POST | `/api/landing-data/update` | Обновить данные |
| GET | `/api/prices` | Только цены |
| POST | `/api/leads/create` | Создать лид |
| POST | `/api/calculate` | Калькулятор |
| GET | `/api/leads` | Список лидов |
| POST | `/webhooks/amocrm` | Webhook amoCRM |
| POST | `/webhooks/telegram` | Webhook Telegram |

---

Создано: 2026-04-12
