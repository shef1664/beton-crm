# ТЗ для Кодекса: задеплоить прод, включить авто-деплой, проверить

## Проблема
Весь новый код влит в `master` (умный AI-диалог, новые цены, зоны доставки, фикс
ответа менеджера), но прод (`beton-backend` на Render) крутит старую версию —
Render не деплоит автоматически. Нужно задеплоить и включить авто-деплой.

## Доступы
```bash
RENDER=$(jq -r .api_key ~/.secrets/render.json)
SID=$(curl -s -H "Authorization: Bearer $RENDER" \
  "https://api.render.com/v1/services?name=beton-backend&limit=1" | jq -r '.[0].service.id')
```

## Шаги

### 1. Задеплоить последний master
```bash
curl -s -X POST -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
  "https://api.render.com/v1/services/$SID/deploys" -d '{"clearCache":"do_not_clear"}'
```
Дождаться статуса `live`. У деплоя должен быть последний коммит master.

### 2. Включить авто-деплой (чтобы merge деплоился сам)
В настройках сервиса Render: Settings → Build & Deploy → **Auto-Deploy: Yes**
(или через API — сверить поле `autoDeploy` у сервиса и выставить `yes`).

### 3. Проверить, что SALES_CHAT_ID выставлен
```bash
curl -s -H "Authorization: Bearer $RENDER" \
  "https://api.render.com/v1/services/$SID/env-vars" | jq '.[].envVar | select(.key=="SALES_CHAT_ID")'
```
Если пусто — выставить (id группы отдела продаж):
```bash
curl -s -X PUT -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
  "https://api.render.com/v1/services/$SID/env-vars/SALES_CHAT_ID" -d '{"value":"-5347837606"}'
```
и передеплоить (шаг 1).

## Проверка после `live`
1. Логи Render при старте: `Telegram bot: started`, без ошибок.
2. Написать @otdprod_bot по-человечески:
   «Нужен бетон на ленточный фундамент, дом 8 на 10, лента 0.4 на 0.6, привезти в Кедровку».
   Бот должен **сам вести диалог**: подобрать М300, посчитать объём (~8.6 м³),
   назвать цену с доставкой (Кедровка 8000–9000 за подачу), спросить дату/оплату,
   показать **кнопку отправки телефона** → оформить заявку.
3. Цена М300 6 м³ = бетон 42 000 ₽ (новая, не 43 200).
4. Заявка → карточка в группе отдела продаж; «Позвать менеджера» → reply в группе доходит клиенту.

## Отчёт
Прислать: коммит задеплоенного релиза, `autoDeploy` состояние, что SALES_CHAT_ID стоит,
результат теста живого диалога.
