# ТЗ для Кодекса: включить группу отдела продаж + выкатить новые цены

## Данные из Telegram (от @getmyid_bot)
```
Your ID (админ):        150420          # личный id владельца (уже прописан как TELEGRAM_ADMIN_ID)
Current chat ID (группа): -5347837606   # id группы отдела продаж → это SALES_CHAT_ID
```

## Цель
1. Выкатить в прод новые цены бетона (PR #35).
2. Включить отправку заявок/«Позвать менеджера» в группу отдела продаж: прописать
   `SALES_CHAT_ID = -5347837606` в Render-сервисе `beton-backend` и передеплоить.

## Доступы (локально)
```bash
RENDER=$(jq -r .api_key ~/.secrets/render.json)     # Render API key
TOKEN=$(jq -r .telegram.bot_token ~/.secrets/beton-sales.json)  # токен @otdprod_bot (для проверок)
```

## Шаги

### 1. Влить цены (PR #35 → master)
Render автодеплоит master. Смёржить:
```bash
gh pr merge 35 --repo shef1664/beton-crm --merge     # либо кнопкой Merge в вебе
```
В PR #35: цены бетона −200 ₽ (М100 5600 … М450 8200), Заводский р-н доставка 6000.

### 2. Прописать SALES_CHAT_ID и передеплоить
```bash
SID=$(curl -s -H "Authorization: Bearer $RENDER" \
  "https://api.render.com/v1/services?name=beton-backend&limit=1" | jq -r '.[0].service.id')

curl -s -X PUT -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
  "https://api.render.com/v1/services/$SID/env-vars/SALES_CHAT_ID" \
  -d '{"value":"-5347837606"}'

curl -s -X POST -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
  "https://api.render.com/v1/services/$SID/deploys" -d '{"clearCache":"do_not_clear"}'
```

### 3. Проверить, что @otdprod_bot в группе
Бот должен быть **участником группы -5347837606** с правом писать, иначе карточки не уйдут.
Если нет — добавить бота в группу вручную в Telegram.

## Проверка результата (после статуса live)
1. Логи Render: `Telegram bot: started`, без ошибок `ANTHROPIC_API_KEY is not set` / `409 Conflict`.
2. @otdprod_bot → расчёт М300: цена бетона **7000 ₽/м³** (новая); адрес «Кемерово, Кедровка» → доставка **8000–9000 ₽**.
3. Довести тестовую заявку до телефона → **карточка `🧱 Новая заявка из бота` падает в группу -5347837606**.
4. Кнопка «Позвать менеджера» → в группе `🔔 Клиент просит менеджера…`; ответить **reply** на это сообщение → ответ приходит клиенту в личку; `/end` завершает.

## Нельзя
- Коммитить токены/ключи в репозиторий.
- Менять env bulk-PUT (затрёт остальные) — только per-key PUT, как выше.

## Нюанс
`-5347837606` — id обычной группы. Если Telegram превратит её в супергруппу, id сменится
на вид `-100…` и карточки перестанут идти — тогда взять новый id через @getmyid_bot и
обновить `SALES_CHAT_ID`.
