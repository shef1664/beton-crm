# ТЗ Кодексу: задеплоить master, перезапустить MAX-бота, проверить заявку в группу

## Проблема
Заявка из **MAX-бота** не приходит карточкой в группу Telegram отдела продаж
(в самом MAX бот отвечает «Заявка принята»). В Telegram-боте заявки в группу
приходят. Фикс уже влит в `master` (PR #40): backend-уведомитель теперь для
не-telegram источников (МАКС) шлёт карточку в группу по прямому каналу
`api.telegram.org` (`services/notifier.py::notify_sales_group`). Осталось —
**задеплоить** и проверить.

## Доступы
```bash
RENDER=$(jq -r .api_key ~/.secrets/render.json)
SID=$(curl -s -H "Authorization: Bearer $RENDER" \
  "https://api.render.com/v1/services?name=beton-backend&limit=1" | jq -r '.[0].service.id')
```

## Шаги

### 1. Проверить env сервиса
```bash
curl -s -H "Authorization: Bearer $RENDER" \
  "https://api.render.com/v1/services/$SID/env-vars" | \
  jq '.[].envVar | select(.key|test("RUN_MAX_BOT|MAX_BOT_TOKEN|SALES_CHAT_ID"))'
```
Должно быть: `RUN_MAX_BOT=true`, `MAX_BOT_TOKEN=<токен>`, `SALES_CHAT_ID=<id группы>`.
Если `SALES_CHAT_ID` пуст — выставить id группы отдела продаж (ранее был `-5347837606`;
если группа стала супергруппой — взять актуальный через @getmyid_bot в группе):
```bash
curl -s -X PUT -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
  "https://api.render.com/v1/services/$SID/env-vars/SALES_CHAT_ID" -d '{"value":"-5347837606"}'
```

### 2. Задеплоить latest master (перезапустит и MAX-бота, и подтянет новый код)
```bash
curl -s -X POST -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
  "https://api.render.com/v1/services/$SID/deploys" -d '{"clearCache":"do_not_clear"}'
```
Дождаться статуса `live`. Задеплоенный коммит должен быть последним из master
(merge PR #40 «заявки из МАКС уведомляют группу…»).

### 3. Включить Auto-Deploy (чтобы мержи катились сами)
Settings → Build & Deploy → **Auto-Deploy: Yes** (или через API — поле `autoDeploy=yes`).

### 4. Проверить логи старта
Искать:
- `МАКС-бот запущен (в backend)` — polling MAX поднялся;
- клиентский AI-бот запущен, без трейсбеков `reportlab`/`invoice`/`telegram`.

### 5. Пробная заявка из MAX (через API, минуя мессенджер)
```bash
PH="+7913$(date +%H%M%S)"   # уникальный телефон, чтобы не сработал антидубль
curl -s -X POST https://beton-backend-wr3w.onrender.com/api/leads/create \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"ТЕСТ из МАКС\",\"phone\":\"$PH\",\"source\":\"max\",\"source_platform\":\"max\",\"source_channel\":\"message\",\"concrete_grade\":\"М300\",\"volume\":6,\"address\":\"Кемерово, Кедровка\",\"delivery_date\":\"Завтра\",\"payment_method\":\"Наличные\",\"calculated_amount\":49200,\"comment\":\"тест уведомления в группу\"}"
```
Ожидаемо: в группе Telegram появляется карточка **«🧱 Новая заявка из МАКС»**.
Если карточка не пришла — прислать из логов строки вокруг `notify_sales_group`
(там явный warning `SALES_CHAT_ID неизвестен …`, если id не задан) и `Telegram send to … failed`.

### 6. Живой прогон в MAX
Заказ через MAX-бота до конца → «Заявка принята» → карточка в группе Telegram.

## Отчёт
Прислать: задеплоенный коммит и статус `live`, значения RUN_MAX_BOT/MAX_BOT_TOKEN(есть/нет)/SALES_CHAT_ID,
строку `МАКС-бот запущен` из логов, результат пробной заявки (пришла карточка в группу или нет,
и если нет — соответствующие строки лога).
