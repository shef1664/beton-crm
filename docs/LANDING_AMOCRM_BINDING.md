# Подключение лендинга к amoCRM

Боевой вход:

`landing/index.html`

Активный исходный вариант:

`variants/landing-speed/index.html`

Концепция: диспетчерская доставки бетона. Форма отправляет заявку в backend:

`POST /api/leads/create`

## Что передает форма

- `name`
- `phone`
- `concrete_grade`
- `volume`
- `address`
- `urgency`
- `source = landing-speed`
- `source_platform = landing-speed`
- `source_channel = form`
- `source_account = graniton-dispatch`
- `source_listing = pathname лендинга`
- `source_campaign = campaign или utm_campaign`
- `utm_source`
- `utm_medium`
- `utm_campaign`
- `client_type = private`
- `next_action`
- `comment`

## Как заявка попадает в amoCRM

1. Лендинг отправляет форму в backend.
2. `backend/main.py` принимает `LeadCreate`.
3. Backend считает сумму, если есть марка и объем.
4. `SalesAutomationService` проставляет приоритет, менеджера, playbook и SLA.
5. `AmoCRMService.create_lead()` создает контакт и лид в amoCRM.
6. Если amoCRM недоступна, лид сохраняется локально в SQLite/Baserow fallback.

## Переменные для Render/backend

Минимально нужны:

```env
AMOCRM_DOMAIN=your-subdomain
AMOCRM_ACCESS_TOKEN=your-long-lived-token
AMOCRM_PIPELINE_ID=10818570
BACKEND_URL=https://your-backend.onrender.com
```

Желательно заполнить:

```env
AMOCRM_PIPELINE_STATUSES_JSON={"new":123,"qualification":456,"calculation":789}
AMOCRM_CUSTOM_FIELD_IDS_JSON={"source_platform":111,"source_channel":222,"concrete_grade":333,"volume":444,"address":555}
```

В `render.yaml` уже есть заготовка для этих переменных.

## Проверка

Локально:

```bash
cd backend
uvicorn main:app --reload
```

Затем открыть:

```text
http://localhost:8765/variants/landing-speed/index.html
```

На production лендинг должен видеть `BACKEND_URL` через `GET /api/config`.
