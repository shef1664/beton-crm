# ТЗ для Кодекса: бот @otdprod_bot не отвечает на /start — диагностировать и починить

## Проблема
Пользователь пишет `/start` боту **@otdprod_bot** — бот молчит, ничего не происходит.
В master (PR #34) влит клиентский AI-бот, работающий **внутри backend-процесса**
(`backend/bot/main.py`, опрос через `getUpdates` в `start_bot()`), на токене
`TELEGRAM_BOT_TOKEN`. Deploy сервиса `beton-backend-wr3w` — live, `ANTHROPIC_API_KEY`
и `DADATA_TOKEN` выставлены. `SALES_CHAT_ID` пока не задан (это не влияет на /start).

Цель: бот должен отвечать на `/start` и вести диалог.

## Доступы (локально у Кодекса)
```bash
TOKEN=$(jq -r .telegram.bot_token ~/.secrets/beton-sales.json)   # токен @otdprod_bot
RENDER=$(jq -r .api_key ~/.secrets/render.json)                  # Render API key
```

## Диагностика по порядку

### 1. Webhook на боте (причина №1 — блокирует getUpdates)
```bash
curl -s "https://api.telegram.org/bot$TOKEN/getWebhookInfo" | jq
```
Если `result.url` НЕ пустой — включён webhook, и опрос (getUpdates) не получает
апдейты. Удалить:
```bash
curl -s "https://api.telegram.org/bot$TOKEN/deleteWebhook?drop_pending_updates=true"
```
Затем снова отправить боту `/start`.

### 2. Это точно тот бот
```bash
curl -s "https://api.telegram.org/bot$TOKEN/getMe" | jq '.result.username'
```
Должно быть `otdprod_bot`. Если другой — пользователь открывает не тот бот
(проверить ссылку `https://t.me/<username>`).

### 3. Бот вообще запустился (логи Render)
Через API получить последние логи сервиса и найти строки старта:
```bash
SID=$(curl -s -H "Authorization: Bearer $RENDER" \
  "https://api.render.com/v1/services?name=beton-backend&limit=1" | jq -r '.[0].service.id')
echo "serviceId=$SID"
# логи: Render Dashboard → сервис → Logs, либо API /v1/services/$SID/logs (если доступно тарифом)
```
Искать при старте:
- ✅ `Telegram bot: started` — бот поднялся.
- ❌ `Conflict: terminated by other getUpdates request` (409) — есть второй опросчик
  на том же токене (старый процесс/дубль сервиса). Найти и остановить его.
- ❌ `TELEGRAM_BOT_TOKEN не задан` / `Telegram bot: disabled` — токен не виден боту
  или `RUN_BOT=false`. Проверить env (см. п.4).
- ❌ трейсбеки при `start_bot` — прислать текст.

### 4. Проверить env и что задеплоен свежий код
```bash
# env сервиса:
curl -s -H "Authorization: Bearer $RENDER" \
  "https://api.render.com/v1/services/$SID/env-vars" | jq '.[].envVar | {key,value: (.value|type)}'
```
Убедиться, что:
- `TELEGRAM_BOT_TOKEN` присутствует и непустой;
- `RUN_BOT` НЕ равен `false` (по умолчанию бот включён; если переменной нет — ок);
- `BACKEND_URL` задан (нужен для keepalive, чтобы Free-сервис не засыпал и опрос жил).

Свежесть кода — сравнить задеплоенный коммит с вершиной master (должен содержать
новый `backend/bot/main.py` клиентского бота):
```bash
git -C <репозиторий> fetch origin master
git -C <репозиторий> rev-parse origin/master
# в Render: Dashboard → сервис → Events/Deploys → у live-деплоя тот же commit SHA?
```
Если live-деплой на старом коммите (до PR #34) — запустить новый деплой:
```bash
curl -s -X POST -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
  "https://api.render.com/v1/services/$SID/deploys" -d '{"clearCache":"do_not_clear"}'
```

### 5. Render Free «уснул»
Free-web засыпает без внешнего трафика; опрос Telegram его не будит. Разбудить и
проверить, что backend жив:
```bash
curl -s https://beton-backend-wr3w.onrender.com/health
```
Должен ответить быстро (после пробуждения). keepalive_loop (пинг раз в 10 мин)
держит его бодрым только если `BACKEND_URL` задан — проверить (п.4).

## Наиболее вероятная причина
80% таких «тишин» — **webhook (п.1)**. Начать с `getWebhookInfo` → `deleteWebhook`.
Вторая по частоте — **409 Conflict** (второй опросчик на токене).

## Проверка результата
1. `/start` в @otdprod_bot → приходит приветствие «Максим из Бетон Экспресс…».
2. «какой бетон на ленточный фундамент?» → осмысленный ответ AI.
3. «Рассчитать и заказать» → марка → объём → адрес «Кемерово, Кедровка» →
   доставка **8 000–9 000 ₽** → дата → оплата → телефон → «Заявка принята».
4. (после `SALES_CHAT_ID = -5347837606` и редеплоя) — карточка падает в группу.

## Отчёт
Прислать: вывод `getWebhookInfo`, `getMe.username`, 5–10 строк логов старта Render
(строка `Telegram bot: ...`), и что было исправлено.

## Нельзя
Не коммитить токены/ключи; env менять только per-key PUT (не bulk).
