# Next Session Brief

## Goal
Построить полуавтономный отдел продаж для бетона:
`landing/lead intake -> расчет -> CRM -> уведомления -> workqueue -> voice sales bot -> аналитика`

## Current State
- Backend работает.
- Landing intake есть.
- amoCRM интеграция есть.
- SQLite/Baserow fallback есть.
- Telegram notifier есть.
- Sales automation/workqueue есть.
- Telephony webhook есть.
- Voice bot есть.

## Voice Bot Status
- Проходит сценарий `qualification -> quote -> confirm/handoff`.
- Happy path создает лид.
- Возражение по цене переводит на менеджера.
- Реального telephony provider пока нет.
- Production TTS/STT пока нет.

## Done
- Настроен `/webhooks/telephony`.
- Добавлены `/status` и `/api/telephony/status`.
- Добавлены telephony env-переменные.
- Переписан `backend/services/sales_dialogue.py`.
- Обновлен `backend/services/voice_agent.py`.
- Улучшены `backend/services/stt.py` и `backend/services/tts.py`.
- Обновлен `backend/test_full_flow.py`.
- Сделан директорский dashboard HTML.
- Отчет и dashboard отправлены на `shef1664@gmail.com`.
- Создан короткий ритуал:
  - утром: `прочитай бриф`
  - вечером: `обнови бриф`

## Verified
- `python -m compileall backend` проходит.
- Через `TestClient`:
  - quote path = OK
  - objection handoff = OK
  - happy path lead creation = OK

## Not Verified
- Реальный входящий звонок.
- Реальный голос через провайдера.
- Production end-to-end через live telephony.

## Important Files
- `backend/main.py`
- `backend/config.py`
- `backend/services/sales_dialogue.py`
- `backend/services/voice_agent.py`
- `backend/services/stt.py`
- `backend/services/tts.py`
- `backend/test_full_flow.py`
- `docs/SALES_CRM_SCHEMA.md`
- `diagnostics/sales_system_report_2026-04-20.md`
- `diagnostics/director_dashboard_superset_style.html`

## Reports / Files
- Отчет отправлен на Gmail.
- Dashboard отправлен на Gmail.
- Есть PDF/HTML материалы в `diagnostics/`.

## Created Test Leads
- Во время проверок создавались тестовые лиды в amoCRM.
- Последний замеченный ID: `45344343`

## Claude / VS Code Setup
- `Claude Code` настроен на работу через `Ollama`.
- Рабочая модель по умолчанию: `minimax-m2.7:cloud`
- `Ollama` доступен локально на `http://127.0.0.1:11434`
- В `C:\Users\ASUS\.claude\settings.json` дефолтная модель переключена на `minimax-m2.7:cloud`
- В PowerShell profile добавлены:
  - `ANTHROPIC_BASE_URL=http://127.0.0.1:11434`
  - `ANTHROPIC_AUTH_TOKEN=ollama`
- Проверка прошла:
  - `claude -p "reply with ok"` => `ok`

## Working Commands
- `прочитай бриф` -> быстро восстановить контекст
- `обнови бриф` -> сохранить контекст
- `экспекто патронум` -> запустить `claude` через VS Code

## Next Best Steps
1. Подключить реального telephony provider.
2. Подключить качественный TTS/STT.
3. Расширить sales-сценарии: счет, насос, юрлицо, торг, конкуренты, callback.
4. Доделать voice analytics.
5. Подключить внешние каналы: Yandex Maps, 2GIS, Avito, VK, WhatsApp.

## Fast Resume
Система уже работает как sales core + voice beta. Главный следующий шаг: не переписывать ядро, а довести production integration телефонии и голоса.
