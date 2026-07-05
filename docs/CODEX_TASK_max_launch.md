# ТЗ для Кодекса: запустить МАКС-бота (max.ru) и сверить его Bot API

## Контекст
В backend добавлен адаптер клиентского AI-бота для МАКС — `backend/bot_max/main.py`
(long-polling, инлайн-кнопки, request_contact). Он переиспользует ядро (AI, зоны,
цены, лид) через localhost-эндпоинты. Включается флагом `RUN_MAX_BOT=true` +
`MAX_BOT_TOKEN`. Код написан по спецификации TamTam/MAX Bot API «вслепую» (доки из
CI недоступны) — **нужно сверить форматы на живом API и поправить при расхождении**.

## Цель
Зарегистрировать бота в МАКС, включить его на проде (`beton-backend`), сверить/поправить
форматы Bot API, протестировать полный сценарий заказа.

## Доступы (локально)
```bash
RENDER=$(jq -r .api_key ~/.secrets/render.json)
```

## Шаги

### 1. Зарегистрировать бота в МАКС и получить токен
- Найти в МАКС платформу для ботов (аналог @BotFather). Ориентиры: dev.max.ru,
  профильный бот-регистратор внутри МАКС. Создать бота → получить **access token**.
- Сохранить токен локально (например `~/.secrets/max.json` → `{"bot_token":"..."}`),
  в git не класть.

### 2. Сверить Bot API МАКС с реализацией
Открыть офиц. доку Bot API МАКС (dev.max.ru/docs-api или аналог). Сверить и, при
расхождении, поправить в `backend/bot_max/main.py` (правки только в функциях `_max_*`
и рядом — бизнес-логика/FSM не трогать):
- **base URL** → env `MAX_API_BASE` (в коде дефолт `https://botapi.max.ru`);
- **аутентификация** — `access_token` как query-параметр (сейчас так);
- **long-polling** `GET /updates` → поля `updates[]`, `marker`, `update_type`;
- **отправка** `POST /messages?user_id=...` → поле `text`, вложение `inline_keyboard`;
- **типы апдейтов** — `message_created`, `message_callback`, `bot_started`;
- **кнопки** — `inline_keyboard.payload.buttons`, типы `callback` и **`request_contact`**;
- **формат contact-вложения** (телефон) → функция `_extract_phone()`;
- при необходимости — как отвечать на callback (некоторые API требуют
  `POST /answers?callback_id=...`); если так — добавить вызов после обработки кнопки.

### 3. Выставить env в Render и передеплоить
```bash
SID=$(curl -s -H "Authorization: Bearer $RENDER" \
  "https://api.render.com/v1/services?name=beton-backend&limit=1" | jq -r '.[0].service.id')

for KV in "MAX_BOT_TOKEN=<токен_из_max.json>" "RUN_MAX_BOT=true" "MAX_API_BASE=<сверенный_base>"; do
  K=${KV%%=*}; V=${KV#*=}
  curl -s -X PUT -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
    "https://api.render.com/v1/services/$SID/env-vars/$K" -d "{\"value\":\"$V\"}"
done

curl -s -X POST -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
  "https://api.render.com/v1/services/$SID/deploys" -d '{"clearCache":"do_not_clear"}'
```
> Если правили `bot_max/main.py` — сначала закоммитить и влить в master (Render деплоит master).

### 4. Проверить
- Логи Render при старте: `MAX bot: started` (без трейсбеков).
- В МАКС: написать боту → приветствие; «какой бетон на фундамент?» → ответ AI;
  «Рассчитать и заказать» → марка (кнопки) → объём → адрес «Кемерово, Кедровка» →
  доставка 8000–9000 ₽ → дата → оплата → **кнопка отправки контакта** → «Заявка принята».
- Заявка должна попасть в CRM/базу с источником `max` (проверить в дашборде/логах).
- Если телефон из контакта не считался — поправить `_extract_phone()` под реальный формат.

## Модель нейросети (Fable 5)
- Модель задаётся env `AI_MODEL` (общая для Telegram и МАКС ботов). Сейчас
  `claude-opus-4-8` — оптимально для живого чата (быстро, топ-качество).
- **Fable 5** (`claude-fable-5`) — самая мощная, НО с постоянным «размышлением»:
  медленно (иногда минуты) и ~2× дороже. Для чат-бота продаж не рекомендуется.
  Если всё же нужно под сложные консультации — поставить `AI_MODEL=claude-fable-5`
  (адаптеров менять не нужно; при желании добавить refusal-fallbacks на `claude-opus-4-8`).

## Нельзя
Коммитить токены/ключи; менять env bulk-PUT (только per-key).

## Отчёт
Прислать: что за регистратор бота в МАКС, какой оказался base URL и формат contact,
какие правки внесли в `_max_*`, лог `MAX bot: started`, результат теста заказа.
