# ТЗ Кодексу: выгрузить «потерянные» заявки из MAX + задеплоить фикс уведомлений

## Контекст
Заявки из MAX-бота не приходили карточкой в группу Telegram (оповещение не уходило),
но **сами лиды сохранялись** в базе. Нужно: (1) выгрузить эти заявки и прислать
пользователю, (2) задеплоить фикс, чтобы впредь MAX-заявки падали в группу.

## Часть A. Выгрузить сохранённые MAX-заявки

### A1. Через открытый API (проще всего)
```bash
curl -s "https://beton-backend-wr3w.onrender.com/api/leads?limit=300" \
 | jq -r '["created_at","name","phone","grade","volume","address","amount","status"],
          (.leads[] | select(.source=="max" or .source_platform=="max")
           | [.created_at, .name, .phone, .concrete_grade, (.volume|tostring),
              .address, (.calculated_amount|tostring), (.lead_status // "")]) | @tsv' \
 | column -t -s $'\t'
```
Прислать пользователю получившийся список (это все заявки из MAX, что есть в базе).

### A2. Если /api/leads пуст или мало (SQLite могла сброситься при рестарте)
Проверить, что подключено персистентное зеркало:
```bash
curl -s "https://beton-backend-wr3w.onrender.com/health" | jq
```
- Если `baserow: true` — выгрузить заявки из Baserow (таблица `BASEROW_LEADS_TABLE_ID`),
  отфильтровать `source=max`.
- Если подключён AmoCRM/Notion — посмотреть там (воронка «Лиды» / база 📥 Лиды).
- Дополнительно — заглянуть в **логи Render** сервиса `beton-backend` за нужный период:
  строки `Новый лид: …` (создан лид) и апдейты MAX. На Free логи хранятся недолго.

> Незавершённые диалоги (клиент писал, но не оформил заказ) в лиды НЕ попадают —
> они только в логах Render (если ещё не истекли). Из MAX API задним числом их не достать.

## Часть B. Задеплоить фикс уведомлений (чтобы не повторялось)
Фикс уже в master (PR #40): backend-уведомитель для source=max шлёт карточку в группу.
```bash
RENDER=$(jq -r .api_key ~/.secrets/render.json)
SID=$(curl -s -H "Authorization: Bearer $RENDER" \
  "https://api.render.com/v1/services?name=beton-backend&limit=1" | jq -r '.[0].service.id')

# проверить env
curl -s -H "Authorization: Bearer $RENDER" \
  "https://api.render.com/v1/services/$SID/env-vars" | \
  jq '.[].envVar | select(.key|test("RUN_MAX_BOT|MAX_BOT_TOKEN|SALES_CHAT_ID"))'
# если SALES_CHAT_ID пуст — выставить id группы (был -5347837606; супергруппа → взять актуальный)

# деплой latest master
curl -s -X POST -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
  "https://api.render.com/v1/services/$SID/deploys" -d '{"clearCache":"do_not_clear"}'
```
Включить **Auto-Deploy: Yes**. В логах старта дождаться `МАКС-бот запущен (в backend)`.

## Часть C. Проверка после деплоя
```bash
PH="+7913$(date +%H%M%S)"
curl -s -X POST https://beton-backend-wr3w.onrender.com/api/leads/create \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"ТЕСТ из МАКС\",\"phone\":\"$PH\",\"source\":\"max\",\"source_platform\":\"max\",\"source_channel\":\"message\",\"concrete_grade\":\"М300\",\"volume\":6,\"address\":\"Кемерово, Кедровка\",\"delivery_date\":\"Завтра\",\"payment_method\":\"Наличные\",\"calculated_amount\":49200,\"comment\":\"тест уведомления в группу\"}"
```
Ожидаемо: в группе Telegram — карточка **«🧱 Новая заявка из МАКС»**.

## Отчёт
Прислать: (A) список MAX-заявок из базы; (B) задеплоенный коммит + статус `live`,
значения RUN_MAX_BOT/MAX_BOT_TOKEN(есть/нет)/SALES_CHAT_ID, строку `МАКС-бот запущен`;
(C) пришла ли тестовая карточка в группу (если нет — строки лога вокруг
`notify_sales_group` / `Telegram send … failed`).
