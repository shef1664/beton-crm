# МАКС-бот (мессенджер max.ru)

Клиентский AI-бот заказа бетона для МАКС. Тот же функционал, что и Telegram-бот
(AI-консультация, зоны доставки, цены, лид в CRM), реализован адаптером
`backend/bot_max/main.py` — работает в backend-процессе, дёргает те же эндпоинты
(`/api/ai/chat`, `/api/quote`, `/api/leads/create`) по localhost. Лиды помечаются
источником `max`.

## Включение
1. Зарегистрировать бота в МАКС (платформа для ботов max.ru), получить **токен**.
2. В Render (сервис `beton-backend`) выставить:
   - `MAX_BOT_TOKEN` = токен бота МАКС
   - `RUN_MAX_BOT` = `true`
   - `MAX_API_BASE` = базовый URL Bot API МАКС (**сверить** в их доке; по умолчанию
     `https://botapi.max.ru`)
3. Передеплоить. В логах при старте: `MAX bot: started`.

## ⚠️ Что сверить на живом токене (докой из CI не достучаться)
МАКС Bot API — наследник TamTam Bot API. В `backend/bot_max/main.py` вынесены в
функции `_max_*` и помечены `⚠️ сверить`:
- **base URL** (`MAX_API_BASE`);
- **long-polling** `GET /updates` (поля `updates`, `marker`, `update_type`);
- **отправка** `POST /messages?user_id=...` (поле `text`, вложение `inline_keyboard`);
- **типы update**: `message_created`, `message_callback`, `bot_started`;
- **кнопки**: `inline_keyboard` с `callback` и **`request_contact`** (запрос телефона);
- **формат contact-вложения** (откуда брать телефон) — `_extract_phone()`.

Если формат отличается — правки только в этих функциях, бизнес-логика (FSM, вызовы
backend) не меняется.

## Что уже работает без правок
- Backend принимает лиды с источником `max` (есть в `SUPPORTED_SOURCE_PLATFORMS`).
- AI, зоны, цены — общие с Telegram-ботом.

## Отличия v1 от Telegram-бота
- Отдел продаж: лид идёт в CRM + уведомление админу (notifier). Карточка в
  Telegram-группу и живой оператор — пока только в Telegram-боте (для МАКС — v2).
- Дата/оплата — инлайн-кнопками; телефон — кнопкой `request_contact`.
