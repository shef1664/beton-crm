# 🏗 СИСТЕМА ПРОДАЖИ БЕТОНА - ДОКУМЕНТАЦИЯ

## 📊 Схема системы

```
         Лендинг       Telegram Bot    Звонки
             ↓             ↓              ↓
         ┌─────────────────────────────────┐
         │      Backend (FastAPI)          │
         │  - API endpoints                │
         │  - Калькулятор                  │
         │  - Антидубли                    │
         │  - Логирование                  │
         └────────────────┬────────────────┘
                          ↓
                    ┌─────────┐
                    │ amoCRM  │  ← ЦЕНТР СИСТЕМЫ
                    │  - Лиды │
                    │  - Воронка │
                    │  - Контакты │
                    └────┬────┘
                         ↓
                   ┌──────────┐
                   │ Baserow  │  ← ЛОГИ + РАСЧЁТЫ
                   │  - Логи  │
                   │  - События │
                   └────┬─────┘
                        ↓
               ┌─────────────────┐
               │ Telegram        │
               │ уведомления     │
               └─────────────────┘
```

---

## 📁 Структура проекта

```
АНОМАЛЬНЫЙ_ЛЕНДИНГ/
├── backend/
│   ├── main.py              # FastAPI приложение
│   ├── config.py            # Конфигурация
│   ├── requirements.txt     # Python зависимости
│   ├── .env.example         # Шаблон переменных
│   ├── bot/
│   │   └── main.py          # Telegram бот @otdprod
│   ├── api/                 # API endpoints
│   └── services/
│       ├── amocrm.py        # amoCRM интеграция
│       ├── baserow.py       # Baserow логирование
│       ├── calculator.py    # Калькулятор бетона
│       ├── notifier.py      # Telegram уведомления
│       └── duplicate_checker.py  # Антидубли
├── landing-main/
│   └── index.html           # Главный лендинг с формой
├── variants/                # 5 тестовых лендингов
│   ├── landing-kdm/
│   ├── landing-vedro/
│   ├── landing-speed/
│   ├── landing-trust/
│   └── landing-calc/
├── baserow/                 # Структура таблиц Baserow
├── package.json             # npm скрипты
├── Procfile                 # Для Render deploy
└── README.md                # Этот файл
```

---

## 🔑 Что нужно настроить

### 1. amoCRM
1. Зайдите в amoCRM → Настройки → Интеграции → API
2. Создайте интеграцию, получите:
   - Client ID
   - Client Secret
   - Access Token
3. В настройках воронки создайте этапы:
   - Новый лид (ID: 5311172)
   - Сбор данных (ID: 5311174)
   - Квалификация (ID: 5311176)
   - Расчёт (ID: 5311178)
   - Дожим (ID: 5311180)
   - Горячий лид (ID: 5311182)
   - Сделка подтверждена (ID: 5311184)
   - Завершено (ID: 5311186)
   - Проиграно (ID: 5311188)
4. Создайте кастомные поля:
   - concrete_grade (марка бетона)
   - volume (объём)
   - address (адрес)
   - delivery_date (дата доставки)
   - urgency (срочность)
   - payment_method (способ оплаты)
   - calculated_amount (расчётная сумма)
   - distance (расстояние)

### 2. Telegram Бот
1. Откройте @BotFather
2. Напишите `/newbot`
3. Назовите бота: `otdprod`
4. Скопируйте токен
5. Вставьте в `.env` файл

### 3. Baserow
1. Зарегистрируйтесь на https://baserow.io
2. Создайте базу данных
3. Создайте 2 таблицы:

**Таблица 1: leads**
- name (Text)
- phone (Text)
- source (Text)
- concrete_grade (Text)
- volume (Number)
- address (Text)
- calculated_amount (Number)
- created_at (Date)
- lead_id (Number)

**Таблица 2: logs**
- action (Text)
- error (Text)
- data (Long text)
- timestamp (Date)

4. Скопируйте Token из настроек
5. Вставьте Table IDs в `.env`

### 4. Deploy на Render
1. Зарегистрируйтесь на https://render.com
2. Нажмите "New Web Service"
3. Подключите GitHub репозиторий
4. Настройки:
   - Build command: `pip install -r backend/requirements.txt`
   - Start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Environment: добавьте все переменные из `.env.example`
5. Нажмите "Create Web Service"

---

## 🚀 Запуск локально

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # заполните .env
uvicorn main:app --reload
```

Откройте: http://localhost:8000

---

## 📡 API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/` | Статус сервиса |
| GET | `/health` | Health check |
| POST | `/api/leads/create` | Создание лида |
| PATCH | `/api/leads/{id}` | Обновление лида |
| POST | `/api/calculate` | Расчёт стоимости |
| GET | `/api/leads` | Список лидов |
| POST | `/webhooks/amocrm` | Webhook от amoCRM |
| POST | `/webhooks/telegram` | Webhook от бота |

---

## 🤖 Telegram Bot @otdprod

Сценарий диалога:
1. /start → Как вас зовут?
2. Имя → Какой объём?
3. Объём → Выберите марку
4. Марка → Адрес доставки
5. Адрес → Когда доставка?
6. Дата → Способ оплаты
7. Оплата → Телефон
8. Телефон → ✅ Заявка принята!

Данные отправляются на backend → создаётся лид в amoCRM

---

## 📊 Воронка amoCRM

```
Новый лид → Сбор данных → Квалификация → Расчёт → Дожим → Горячий лид → Сделка подтверждена → Завершено
                                                                                                ↓
                                                                                           Проиграно
```

---

## 💰 Калькулятор

Формула расчёта:
```
Стоимость = (Цена_марки × Объём) + (Расстояние × 150₽/км)
```

Цены:
- М100: 5800 ₽/м³
- М150: 6100 ₽/м³
- М200: 6400 ₽/м³
- М250: 6800 ₽/м³
- М300: 7200 ₽/м³
- М350: 7600 ₽/м³
- М400: 8000 ₽/м³
- М450: 8400 ₽/м³

---

## 📝 Чек-лист запуска

- [ ] Создан бот @otdprod в BotFather
- [ ] Настроена amoCRM (воронка, поля, API ключ)
- [ ] Создана база в Baserow
- [ ] Заполнен `.env` файл
- [ ] Задеплоено на Render
- [ ] Протестирована форма на лендинге
- [ ] Протестирован Telegram бот
- [ ] Приходят уведомления в Telegram
- [ ] Лиды создаются в amoCRM

---

Создано: 2026-04-12
