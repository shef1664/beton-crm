# ДЗ для Кодекса: выставить env в Render и задеплоить AI-бота

> Клиентский AI-бот (@otdprod_bot) влит в `master` (PR #34) и живёт в backend-процессе.
> Чтобы заработала нейросеть и отдел продаж, нужно задать переменные окружения на
> Render-сервисе `beton-backend`. Секреты — только через Render API, **ничего не коммитить**.

## Что выставить
| Переменная | Значение | Обязательна |
|---|---|---|
| `ANTHROPIC_API_KEY` | ключ Anthropic (новый!) | да — без неё AI молчит, бот падает на кнопки |
| `SALES_CHAT_ID` | chat_id Telegram-группы отдела продаж | да — иначе нет карточек и передачи менеджеру |
| `AI_MODEL` | напр. `claude-haiku-4-5` (дешевле) или оставить `claude-opus-4-8` | нет |
| `DADATA_TOKEN` | из `~/.secrets/dadata.json` — точный район по улице | нет |

`TELEGRAM_BOT_TOKEN` (@otdprod_bot) уже настроен — не трогать.

## Шаги

1. **Новый ключ Anthropic.** console.anthropic.com → API Keys → создать новый,
   старый (тот, что светился в переписке) — **Revoke**. Сохранить локально, напр.
   `~/.secrets/anthropic.json` → `{"api_key":"sk-ant-..."}`. В git не класть.

2. **Render API-ключ** (заголовок `Authorization: Bearer <ключ>`):
   ```bash
   RENDER=$(jq -r .api_key ~/.secrets/render.json)   # сверить имя поля в файле
   ```

3. **Найти serviceId** сервиса `beton-backend`:
   ```bash
   curl -s -H "Authorization: Bearer $RENDER" \
     "https://api.render.com/v1/services?name=beton-backend&limit=1" | jq
   SID=<serviceId из ответа>
   ```

4. **Выставить переменные** (по одной — per-key PUT, не bulk, чтобы не затереть остальные):
   ```bash
   curl -s -X PUT -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
     "https://api.render.com/v1/services/$SID/env-vars/ANTHROPIC_API_KEY" \
     -d "{\"value\":\"$(jq -r .api_key ~/.secrets/anthropic.json)\"}"

   curl -s -X PUT -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
     "https://api.render.com/v1/services/$SID/env-vars/SALES_CHAT_ID" \
     -d "{\"value\":\"<ID_группы_отдела_продаж>\"}"
   ```
   `SALES_CHAT_ID` = id Telegram-группы (создать группу, добавить @otdprod_bot,
   узнать id через @getmyid_bot; обычно отрицательное число вида `-100...`).

5. **Запустить деплой:**
   ```bash
   curl -s -X POST -H "Authorization: Bearer $RENDER" -H "Content-Type: application/json" \
     "https://api.render.com/v1/services/$SID/deploys" -d '{"clearCache":"do_not_clear"}'
   ```

6. **Проверить логи деплоя** — должно быть:
   - `Telegram bot: started`
   - `Telegram: configured`
   - нет предупреждения `ANTHROPIC_API_KEY is not set`.

7. **Тест в Telegram:** `/start` @otdprod_bot → «какой бетон на ленточный фундамент?»
   → осмысленный ответ AI → пройти заказ (марка → объём → адрес «Кемерово, Кедровка»
   → цена доставки 8 000–9 000 ₽ → дата → оплата → телефон) → в группе появилась карточка.

## Нельзя
- Коммитить ключи/токены в репозиторий.
- Использовать bulk-PUT env (затрёт остальные переменные) — только per-key.

## Точные детали API
Имя поля ключа в `render.json` и формат ответа `/v1/services` Кодекс сверяет на месте
(есть доступ к секретам и Render). Референс: https://api-docs.render.com/reference/update-env-var
