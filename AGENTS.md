# AGENTS.md — Бетон42 / автоматизированный отдел продаж

> **Этот файл читается автоматически любым AI-агентом (Codex / Claude / другие) при запуске в этой папке.** Здесь полная карта проекта на момент 2026-05-12. Не пропускай — потеряешь контекст.

## Что это

Production-система отдела продаж для ООО «ПУЛЬСАР» (ИНН 4205271841), бренд **«Бетон Экспресс»**, регион Кемерово. Сайт **https://бетон42.рф**.

## Что работает прямо сейчас (production)

| Компонент | Адрес | Статус |
|---|---|---|
| Лендинг | https://бетон42.рф/ | ✅ 200, ~100 КБ |
| Политика ПД (152-ФЗ) | https://бетон42.рф/privacy.html | ✅ 200 |
| Backend API | https://beton-backend-wr3w.onrender.com | ✅ FastAPI 0.128, 33 endpoint'а |
| Хостинг | Render.com (Frankfurt, Free plan) | ⚠️ см. РКН ниже |
| CDN | Cloudflare (front of Render) | ✅ |
| SSL | Let's Encrypt | ✅ авто |
| GitHub | https://github.com/shef1664/beton-crm | ✅ master = production |
| AmoCRM | https://shef1664.amocrm.ru | ✅ демо продлено, AMOCRM_ACCESS_TOKEN в Render env. Лиды реально создаются (price=calc_amount, name «Клиент — М300, 6 м³») |
| Telegram бот | @otdprod_bot (id 8724634676) | ✅ уведомления приходят, admin_id 150420 |
| База лидов | SQLite на Render | ✅ fallback от AmoCRM работает |
| Notion auto-sync лидов | `backend/services/notion.py` → база 📥 Лиды | ⏳ ждёт `NOTION_API_TOKEN` env var |
| Яндекс.Метрика | env-driven injection в backend (`YANDEX_METRIKA_ID`) | ⏳ ждёт 8-значный counter_id |
| Yandex.Direct | план: 4 кампании, 105k ₽/мес, тест 7k/7 дн | 📋 см. docs/YANDEX_DIRECT_LAUNCH_PLAN.md |
| Render API ключ | сохранён в ~/.secrets/render.json | ✅ env vars выставляются через API без user UI |

## Карта файлов

| Где | Что |
|---|---|
| `./` (cwd) | Главная рабочая папка проекта (этот файл) |
| `backend/` | FastAPI приложение (main.py 699 строк + services/) |
| `backend/.venv/` | Python 3.9 venv (рабочий) |
| `backend/.env` | Локальные секреты (в .gitignore) |
| `backend/data/notion_config.json` | IDs трёх Notion-баз |
| `landing/` | Боевой лендинг Бетон Экспресс |
| `variants/` | 6 A/B-вариантов лендинга |
| `docs/` | AMOCRM_LIVE_MAPPING.md, SALES_CRM_SCHEMA.md, аудит 2026-05-01 |
| `render.yaml`, `Procfile` | Конфиги Render |

### Внешние локации
- **Drive снапшот:** `/Users/a0000/Library/CloudStorage/GoogleDrive-shef1664@gmail.com/Мой диск/проект ии/Автоматизированный отдел продаж. Финал/` — read-only архив, не редактируй
- **Drive working copy:** `…/проект ии/автоматизированный отдел продаж/` — синкается с master через коммиты
- **Секреты:** `~/.secrets/` (chmod 600 каждый файл)
- **Скиллы:** `~/.claude/skills/{ru-sales-stack, beton42-notion-ops, avito-beton-monitor}/`
- **Память агента:** `~/.claude/projects/-Users-a0000-Documents-Codex-2026-04-27-notion-SMART-MARKETING-AI/memory/MEMORY.md` — индекс всех заметок предыдущих сессий

## Где взять секреты

```bash
jq -r .amocrm.access_token ~/.secrets/beton-sales.json
jq -r .amocrm.domain      ~/.secrets/beton-sales.json   # shef1664.amocrm.ru
jq -r .telegram.bot_token ~/.secrets/beton-sales.json
jq -r .telegram.admin_id  ~/.secrets/beton-sales.json   # 150420
jq -r .pat                ~/.secrets/github.json
jq -r .token              ~/.secrets/dadata.json
jq -r .api_key            ~/.secrets/yandex-places.json
```

## Архитектура потока лида

```
Лендинг + Telegram-бот + Звонки
         ↓
  POST /api/leads/create
         ↓
  ┌──────────────────────────────────┐
  │  FastAPI backend                  │
  │   1. Антидубли по телефону        │
  │   2. Калькулятор (если объём+марка)│
  │   3. Sales automation (приоритет) │
  └────────────┬─────────────────────┘
               ↓
   ┌───────────┼───────────┐
   ↓           ↓           ↓
 AmoCRM    SQLite     Telegram
(402)    fallback   @otdprod_bot
```

## Калькулятор бетона

```
delivery_per_m3 = (distance_km × 35) + 650
billable_volume = max(6 м³, ceil(order_volume))
total = (grade_price × order_volume) + (delivery_per_m3 × billable_volume)
```

Цены: М100=5800 · М150=6100 · М200=6400 · М250=6800 · М300=7200 · М350=7600 · М400=8000 · М450=8400

## AmoCRM воронка (IDs зафиксированы)

12 статусов: `unprocessed=85162966 · new=85162970 · data_collection=85162974 · calculation=85162978 · hot_lead=85162982 · confirmed=85162986 · won=142 · lost=143`.

27 кастомных полей зафиксированы в `render.yaml` → `AMOCRM_CUSTOM_FIELD_IDS_JSON`.

## Notion — 3 базы под отдел продаж

| База | data_source_id | URL |
|---|---|---|
| 📥 Лиды | `4cec5918-8482-43d8-8028-88f44480d284` | https://www.notion.so/af0ca819002c457198bd353701b1ff26 |
| 🔥 Задачи продаж | `b8508944-204a-42ee-9ca2-77cb26431f87` | https://www.notion.so/6b79b6d08138457cbaf195207f610451 |
| ⚔️ Конкуренты | `d2401094-4515-442b-a971-44e122c056d0` | https://www.notion.so/6f1c74a3ae8f44739afe7b926e94b78c |

Parent: «🤖 Автоматизированный отдел продаж — Бетон42» (id `35ee5c10-f168-81c1-a027-f44c194bfe2d`).

Связанные страницы стратегии:
- 🏗 Бетон Кемерово — Конкурентная разведка (id `353e5c10-f168-814e-9805-ebacb9061f45`)
- 📅 Авито ежедневный отчёт (id `354e5c10-f168-81a0-8022-f7354a3ad34a`)

## Готовые скиллы (auto-trigger)

- **`ru-sales-stack`** — Yandex Direct/Метрика/Карты, 2ГИС, DaData, secrets bootstrap
- **`beton42-notion-ops`** — операционка трёх Notion-баз: создание лидов/задач/конкурентов, дашборды
- **`avito-beton-monitor`** — парсер Авито через Apify, отчёты в Notion (ждёт Apify token)

## TODO (зафиксированное на 2026-05-12)

### 🔴 Юридическое
1. **Уведомление в Роскомнадзор** (ст. 22 152-ФЗ) — без него нельзя обрабатывать ПД с сайта. https://pd.rkn.gov.ru/operators-registry/notification/form/
2. **Российский хостинг** — Render Frankfurt = нарушение ч. 5 ст. 18 152-ФЗ. Варианты: Selectel/Beget/Timeweb/Yandex Cloud.
3. **ОКВЭД** — сейчас 49.4 (грузоперевозки), нужно добавить 23.63 / 46.73.6 / 47.78.9 через ФНС.

### 🟡 Маркетинг / запуск
4. **AmoCRM подписка** оплатить — лиды автоматически потекут в воронку без правок кода.
5. **Apify токен** — для активации `avito-beton-monitor` skill.
6. **Яндекс.Метрика** счётчик на лендинг + цели.
7. **Яндекс.Директ** запуск кампаний с UTM-разметкой (поля уже принимаются backend).
8. **Маркировка ОРД** для рекламы.

### 🟢 Расширение
9. **Mango Office** + **Yandex SpeechKit** → голосовой робот (код в backend готов).
10. **Notion-плагин** активация через `/plugin install notion-workspace-plugin@notion-plugin-marketplace` — даст 10 slash commands.
11. **Bitrix24 / AmoCRM миграция** если 402 надолго.

## Счета (генератор PDF) — встроен в @otdprod_bot

- Пакет `backend/invoice_generator/` (reportlab+qrcode). Команда **/schet** в боте:
  клиент шлёт ИНН + позиции текстом → PDF-счёт с логотипом Бетон Экспресс и платёжным
  QR по ГОСТ (ST00012), копия в отдел продаж. Покупатель по ИНН через DaData.
- **Мультиорганизация:** продавец по умолчанию `sequoia` (ООО «Секвойя», ИНН 4205355160),
  есть `pulsar` (ООО «Пульсар»). Выбор строкой «Организация: Пульсар» или полем `seller`.
- **Секреты вне git** (репо публичный!): реквизиты `seller.<key>.json` и печати
  `<key>-stamp-signature-pdf.png` — в `INVOICE_SECRETS_DIR` (Render Secret Files, `/etc/secrets`).
  Печать привязана к организации по ИНН. Печати Секвойи пока нет → подпись без печати.
- Деплой/секреты: `docs/CODEX_TASK_invoice_render.md`. TODO: распознавание реквизитов
  из PDF/фото (Claude vision) и версия счетов для МАКС.

## Роутинг моделей AI-консультанта (по сложности запроса)

- `AI_MODEL_COMPLEX=claude-fable-5` (подбор марки/расчёты/нюансы), `AI_MODEL_MEDIUM=claude-opus-4-8`
  (обычный диалог), `AI_MODEL_LIGHT=claude-haiku-4-5-20251001` (короткие реплики).
  Модель выбирается по последней реплике клиента в `backend/services/ai_agent.py::_pick_model`.
- `AI_MODEL` (если задан непустым) форсит одну модель и ОТКЛЮЧАЕТ роутинг.
  Fable 5 медленнее — на потоке заказа можно вернуть Opus через `AI_MODEL_COMPLEX`.

## Дисциплина / правила

Из CLAUDE_RULES.md проекта SMART_MARKETING_AI:
1. Не угадывать — задавать вопросы.
2. Не усложнять архитектуру.
3. Делать минимально достаточные решения.
4. Не создавать overengineering.
5. **Не изменять структуру проекта без согласования.**
6. Главная цель — рост заявок и прибыли.
7. Любая автоматизация должна быть измерима.
8. AI не принимает критические решения самостоятельно.
9. Сначала данные — потом автоматизация.
10. Сначала MVP — потом масштабирование.

## Запуск backend локально

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8765
# открыть http://127.0.0.1:8765/  → отдаст лендинг
# POST /api/leads/create  → end-to-end в AmoCRM/SQLite/Telegram
```

## Git workflow

- `master` = production (Render автодеплоит)
- Не пушить напрямую в master — через PR
- Авторы коммитов: `shef1664 <shef1664@gmail.com>` + `Co-Authored-By: Claude/Codex`
- PAT для push: `jq -r .pat ~/.secrets/github.json`

## Если что-то не понятно

1. Прочитай `MEMORY.md` в `~/.claude/projects/.../memory/` — там накопленный контекст
2. Прочитай `FINAL_PROJECT_SUMMARY.md` в Drive снапшоте
3. Прочитай `docs/PROJECT_AUDIT_2026-05-01.md` в этой папке
4. Спроси пользователя

---

**Версия:** 2026-05-12. Поддерживай актуальной — обновляй когда меняются URL/IDs/статусы.
