"""
Backend for the concrete sales funnel.
The architecture stays the same: landing -> backend -> amoCRM/storage/notifications.
"""

from datetime import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from bot.main import start_bot as start_telegram_bot, stop_bot as stop_telegram_bot
from config import settings
from services.amocrm import AmoCRMService
from services.baserow import BaserowService
from services.calculator import BetonCalculator
from services.duplicate_checker import DuplicateChecker
from services.lead_utils import coerce_amount
from services.notifier import TelegramNotifier
from services.integration_adapters import IntegrationAdapters
from services.sales_automation import SalesAutomationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Бетон Backend API",
    description="Интеграционное ядро: amoCRM + storage + Telegram + лендинги",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

amocrm = AmoCRMService()
baserow = BaserowService()
calculator = BetonCalculator()
notifier = TelegramNotifier()
duplicate_checker = DuplicateChecker(amocrm, baserow)
sales_automation = SalesAutomationService()


class LeadCreate(BaseModel):
    name: str = Field(..., description="Имя клиента")
    phone: str = Field(..., description="Телефон")
    source: Optional[str] = Field("landing", description="Короткий источник")
    source_platform: Optional[str] = Field("site", description="Платформа: site, yandex_maps, 2gis, avito, vk, max")
    source_channel: Optional[str] = Field("form", description="Канал: form, call, chat, message")
    source_account: Optional[str] = Field(None, description="Аккаунт площадки")
    source_listing: Optional[str] = Field(None, description="Объявление, карточка или объект")
    source_campaign: Optional[str] = Field(None, description="Кампания, оффер или гипотеза")
    utm_source: Optional[str] = Field(None, description="UTM source")
    utm_medium: Optional[str] = Field(None, description="UTM medium")
    utm_campaign: Optional[str] = Field(None, description="UTM campaign")
    concrete_grade: Optional[str] = Field(None, description="Марка бетона")
    volume: Optional[float] = Field(None, description="Объем в м3")
    address: Optional[str] = Field(None, description="Адрес доставки")
    delivery_date: Optional[str] = Field(None, description="Дата доставки")
    urgency: Optional[str] = Field("normal", description="Срочность")
    payment_method: Optional[str] = Field(None, description="Способ оплаты")
    comment: Optional[str] = Field(None, description="Комментарий")
    calculated_amount: Optional[float] = Field(None, description="Расчетная сумма")
    distance: Optional[float] = Field(None, description="Расстояние в км")
    client_type: Optional[str] = Field("private", description="Тип клиента")
    sales_priority: Optional[str] = Field(None, description="Приоритет для отдела продаж")
    assigned_manager: Optional[str] = Field(None, description="Назначенный менеджер")
    lead_status: Optional[str] = Field(None, description="Рекомендуемый статус")
    next_action: Optional[str] = Field(None, description="Следующее действие")
    route_bucket: Optional[str] = Field(None, description="Маршрут распределения")
    sales_playbook: Optional[str] = Field(None, description="Автоматически выбранный playbook")
    qualification_script: Optional[str] = Field(None, description="Подсказка для квалификации")
    sla_minutes: Optional[int] = Field(None, description="SLA на первый контакт")
    contact_deadline_at: Optional[str] = Field(None, description="Крайний срок первого контакта")

    @field_validator("calculated_amount", mode="before")
    @classmethod
    def normalize_amount(cls, value: Any) -> Optional[float]:
        return coerce_amount(value)


class LeadUpdate(BaseModel):
    status_id: Optional[int] = None
    lead_status: Optional[str] = None
    concrete_grade: Optional[str] = None
    volume: Optional[float] = None
    calculated_amount: Optional[float] = None
    comment: Optional[str] = None
    manual_check: Optional[bool] = False

    @field_validator("calculated_amount", mode="before")
    @classmethod
    def normalize_amount(cls, value: Any) -> Optional[float]:
        return coerce_amount(value)


class CalculateRequest(BaseModel):
    concrete_grade: str
    volume: float
    distance: Optional[float] = 0


class ExternalLeadIngest(BaseModel):
    lead_data: LeadCreate
    integration: Optional[str] = Field(None, description="Источник интеграции: telephony, yandex_maps, 2gis")
    event_type: Optional[str] = Field("lead", description="Тип события")
    raw_payload: Optional[dict[str, Any]] = Field(None, description="Оригинальный payload для логирования")


class WorkqueueClaimRequest(BaseModel):
    assigned_manager: str = Field(..., description="Кто берет лид в работу")
    next_action: Optional[str] = Field("Связаться с клиентом", description="Следующий шаг")


class WorkqueueContactRequest(BaseModel):
    next_action: Optional[str] = Field("Контакт выполнен, ждем детали", description="Следующий шаг после контакта")
    lead_status: Optional[str] = Field("data_collection", description="Новый статус после первого контакта")
    comment: Optional[str] = Field(None, description="Комментарий менеджера")


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Бетон Backend API",
        "version": "1.0.0",
        "amoCRM": "connected" if amocrm.is_available() else "not configured",
    }


@app.get("/ping")
async def ping():
    return {"pong": True, "timestamp": datetime.now().isoformat()}


@app.get("/api/config")
async def get_public_config():
    return {
        "status": "ok",
        "api_url": settings.BACKEND_URL,
        "backend_url": settings.BACKEND_URL,
        "phone": "8-903-916-40-40",
        "company": "ТрансМикс",
        "services": {
            "amocrm": amocrm.is_available(),
            "telegram": notifier.is_available(),
        },
        "sales": {
            "supported_source_platforms": settings.SUPPORTED_SOURCE_PLATFORMS,
            "supported_source_channels": settings.SUPPORTED_SOURCE_CHANNELS,
        },
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "amoCRM": amocrm.is_available(),
            "baserow": baserow.is_available(),
            "telegram": notifier.is_available(),
        },
    }


@app.get("/api/crm/schema")
async def get_crm_schema():
    return {
        "status": "success",
        "pipeline_statuses": settings.PIPELINE_STATUSES,
        "configured_custom_fields": settings.AMOCRM_CUSTOM_FIELD_IDS,
        "supported_source_platforms": settings.SUPPORTED_SOURCE_PLATFORMS,
        "supported_source_channels": settings.SUPPORTED_SOURCE_CHANNELS,
        "required_manager_fields": settings.REQUIRED_MANAGER_FIELDS,
        "sales_managers": settings.SALES_MANAGERS,
        "sales_playbooks": settings.SALES_PLAYBOOKS,
        "lead_fields": [
            "name",
            "phone",
            "source",
            "source_platform",
            "source_channel",
            "source_account",
            "source_listing",
            "source_campaign",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "concrete_grade",
            "volume",
            "address",
            "delivery_date",
            "urgency",
            "payment_method",
            "comment",
            "calculated_amount",
            "distance",
            "client_type",
            "sales_priority",
            "assigned_manager",
            "lead_status",
            "next_action",
            "route_bucket",
            "sales_playbook",
            "qualification_script",
            "sla_minutes",
            "contact_deadline_at",
        ],
    }


@app.get("/api/integrations/schema")
async def get_integrations_schema():
    return {
        "status": "success",
        "integrations": settings.INTEGRATION_DEFAULTS,
        "supported_source_platforms": settings.SUPPORTED_SOURCE_PLATFORMS,
        "supported_source_channels": settings.SUPPORTED_SOURCE_CHANNELS,
        "generic_webhook": "/webhooks/external/{integration}",
        "generic_intake": "/api/intake/external",
        "raw_payload_adapters": ("telephony", "yandex_maps", "2gis", "avito", "vk", "whatsapp", "telegram"),
    }


@app.get("/api/sales/dashboard")
async def get_sales_dashboard():
    return {
        "status": "success",
        "dashboard": baserow.get_dashboard_stats(),
    }


@app.get("/api/sales/report")
async def get_sales_report():
    return {
        "status": "success",
        "dashboard": baserow.get_dashboard_stats(),
        "automation": {
            "managers": settings.SALES_MANAGERS,
            "rules": settings.SALES_AUTOMATION_RULES,
            "playbooks": settings.SALES_PLAYBOOKS,
        },
        "recent_external_intake": baserow.get_logs(limit=10, action="external_intake_payload"),
        "recent_duplicates": baserow.get_logs(limit=10, action="duplicate_lead"),
        "recent_errors": baserow.get_logs(limit=10, action="create_lead"),
    }


@app.get("/api/sales/workqueue")
async def get_sales_workqueue(
    limit: int = 30,
    assigned_manager: Optional[str] = None,
    route_bucket: Optional[str] = None,
):
    queue = baserow.get_workqueue(
        limit=limit,
        assigned_manager=assigned_manager,
        route_bucket=route_bucket,
    )
    return {
        "status": "success",
        "count": len(queue),
        "items": queue,
    }


async def _sync_workqueue_update_to_amocrm(updated_item: dict, note: Optional[str] = None):
    lead_id = updated_item.get("lead_id")
    if not lead_id:
        return

    update_payload = {}
    lead_status = updated_item.get("lead_status")
    if lead_status:
        mapped_status = settings.PIPELINE_STATUSES.get(lead_status)
        if mapped_status:
            update_payload["status_id"] = mapped_status

    result_note_parts = []
    if updated_item.get("assigned_manager"):
        result_note_parts.append(f"Assigned manager: {updated_item['assigned_manager']}")
    if updated_item.get("next_action"):
        result_note_parts.append(f"Next action: {updated_item['next_action']}")
    if updated_item.get("sales_priority"):
        result_note_parts.append(f"Priority: {updated_item['sales_priority']}")

    if update_payload:
        await amocrm.update_lead(int(lead_id), update_payload)

    combined_note = "\n".join(part for part in [note, *result_note_parts] if part)
    if combined_note:
        await amocrm.add_comment(int(lead_id), combined_note)


@app.post("/api/sales/workqueue/{local_id}/claim")
async def claim_workqueue_lead(local_id: int, payload: WorkqueueClaimRequest):
    updated = baserow.update_local_lead(
        local_id,
        {
            "assigned_manager": payload.assigned_manager,
            "lead_status": "qualification",
            "next_action": payload.next_action or "Связаться с клиентом",
        },
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Lead not found or nothing to update")
    await _sync_workqueue_update_to_amocrm(updated, note="Lead claimed from workqueue")
    return {"status": "success", "item": updated}


@app.post("/api/sales/workqueue/{local_id}/contacted")
async def mark_workqueue_contacted(local_id: int, payload: WorkqueueContactRequest):
    updated = baserow.update_local_lead(
        local_id,
        {
            "lead_status": payload.lead_status or "data_collection",
            "next_action": payload.next_action or "Контакт выполнен, ждем детали",
            "comment": payload.comment,
        },
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Lead not found or nothing to update")
    await _sync_workqueue_update_to_amocrm(updated, note=payload.comment or "First contact completed")
    return {"status": "success", "item": updated}


@app.post("/api/sales/automation-preview")
async def sales_automation_preview(lead_data: LeadCreate):
    payload = lead_data.model_dump()
    payload["calculated_amount"] = coerce_amount(payload.get("calculated_amount"))
    return {"status": "success", "automation": sales_automation.evaluate(payload)}


@app.post("/api/integrations/normalize-preview/{integration}")
async def normalize_integration_preview(integration: str, data: dict):
    lead_payload = data.get("lead_data") if isinstance(data, dict) else None
    if isinstance(lead_payload, dict):
        return {"status": "success", "normalized_lead": lead_payload, "adapter_used": False}

    normalized, reason = IntegrationAdapters.normalize(integration, data)
    if not normalized:
        return {"status": "ignored", "reason": reason or "unable to normalize", "adapter_used": True}
    return {"status": "success", "normalized_lead": normalized, "adapter_used": True}


def _apply_integration_defaults(lead: LeadCreate, integration: Optional[str], event_type: Optional[str]) -> LeadCreate:
    if integration and integration in settings.INTEGRATION_DEFAULTS:
        defaults = settings.INTEGRATION_DEFAULTS[integration]
        if not lead.source or lead.source == "landing":
            lead.source = defaults.get("source", integration)
        if not lead.source_platform or lead.source_platform == "site":
            lead.source_platform = defaults.get("source_platform", integration)
        if not lead.source_channel or lead.source_channel == "form":
            lead.source_channel = defaults.get("source_channel", "form")

    if integration and not lead.source:
        lead.source = integration
    if integration and not lead.source_platform:
        lead.source_platform = integration
    if event_type == "call" and (not lead.source_channel or lead.source_channel == "form"):
        lead.source_channel = "call"
    return lead


def _integration_key_valid(integration: str, provided_key: Optional[str]) -> bool:
    expected = settings.INTEGRATION_KEYS.get(integration)
    if not expected:
        return True
    return bool(provided_key and provided_key == expected)


@app.post("/api/leads/create", status_code=201)
async def create_lead(lead_data: LeadCreate):
    try:
        logger.info("Новый лид: %s, %s", lead_data.name, lead_data.phone)

        duplicate_id = await duplicate_checker.check(lead_data.phone)
        if duplicate_id:
            logger.warning("Дубль найден: %s", lead_data.phone)
            await baserow.log_error(
                "duplicate_lead",
                "",
                {
                    "phone": lead_data.phone,
                    "source": lead_data.source,
                    "source_platform": lead_data.source_platform,
                    "source_channel": lead_data.source_channel,
                    "existing_lead_id": duplicate_id,
                },
            )
            return {
                "status": "duplicate",
                "message": "Вы уже оставляли заявку. Мы свяжемся с вами!",
                "existing_lead_id": duplicate_id,
            }

        lead_data.calculated_amount = coerce_amount(lead_data.calculated_amount)
        if lead_data.calculated_amount is None and lead_data.concrete_grade and lead_data.volume:
            calc_result = calculator.calculate(
                lead_data.concrete_grade,
                lead_data.volume,
                lead_data.distance or 0,
            )
            lead_data.calculated_amount = calc_result["total"]

        if not lead_data.source:
            lead_data.source = lead_data.source_platform or "landing"

        automation = sales_automation.evaluate(lead_data.model_dump())
        if not lead_data.sales_priority:
            lead_data.sales_priority = automation["sales_priority"]
        if not lead_data.assigned_manager:
            lead_data.assigned_manager = automation["assigned_manager"]
        if not lead_data.lead_status:
            lead_data.lead_status = automation["lead_status"]
        if not lead_data.next_action:
            lead_data.next_action = automation["next_action"]
        if not lead_data.route_bucket:
            lead_data.route_bucket = automation["route_bucket"]
        if not lead_data.sales_playbook:
            lead_data.sales_playbook = automation["sales_playbook"]
        if not lead_data.qualification_script:
            lead_data.qualification_script = automation["qualification_script"]
        if not lead_data.sla_minutes:
            lead_data.sla_minutes = automation["sla_minutes"]
        if not lead_data.contact_deadline_at:
            lead_data.contact_deadline_at = automation["contact_deadline_at"]

        lead_payload = lead_data.model_dump()
        lead_id = await amocrm.create_lead(lead_payload)

        await baserow.log_lead(
            {
                **lead_payload,
                "lead_id": lead_id,
                "created_at": datetime.now().isoformat(),
            }
        )
        await notifier.notify_new_lead(lead_payload, lead_id)

        return {
            "status": "success",
            "lead_id": lead_id,
            "amo_lead_created": bool(lead_id),
            "message": "Заявка принята! Перезвоним за 5 минут.",
        }
    except Exception as exc:
        logger.error("Ошибка создания лида: %s", exc)
        await baserow.log_error("create_lead", str(exc), lead_data.model_dump())
        raise HTTPException(status_code=500, detail=str(exc))


@app.patch("/api/leads/{lead_id}")
async def update_lead(lead_id: int, update_data: LeadUpdate):
    try:
        payload = update_data.model_dump(exclude_unset=True)
        if payload.get("lead_status") and not payload.get("status_id"):
            mapped_status = settings.PIPELINE_STATUSES.get(payload["lead_status"])
            if mapped_status:
                payload["status_id"] = mapped_status
        payload.pop("lead_status", None)

        result = await amocrm.update_lead(lead_id, payload)
        if payload.get("status_id") and payload["status_id"] >= settings.PIPELINE_STATUSES.get("hot_lead", 0):
            await notifier.notify_hot_lead(lead_id)
        return {"status": "success", "lead_id": lead_id, "result": result}
    except Exception as exc:
        logger.error("Ошибка обновления лида %s: %s", lead_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/calculate")
async def calculate(calc_data: CalculateRequest):
    try:
        result = calculator.calculate(
            calc_data.concrete_grade,
            calc_data.volume,
            calc_data.distance,
        )
        await baserow.log_calculation(calc_data.model_dump(), result)
        return {"status": "success", "calculation": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Ошибка расчета: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/leads")
async def get_leads(status: Optional[str] = None, limit: int = 50):
    try:
        leads = baserow.get_leads(limit=limit)
        return {"status": "success", "leads": leads, "count": len(leads), "filter": status}
    except Exception as exc:
        logger.error("Ошибка получения лидов: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/intake/external", status_code=201)
async def intake_external_lead(payload: ExternalLeadIngest):
    try:
        lead = _apply_integration_defaults(
            payload.lead_data.model_copy(deep=True),
            payload.integration,
            payload.event_type,
        )

        result = await create_lead(lead)

        if payload.raw_payload:
            await baserow.log_error(
                "external_intake_payload",
                "",
                {
                    "integration": payload.integration,
                    "event_type": payload.event_type,
                    "result_status": result.get("status"),
                    "raw_payload": payload.raw_payload,
                },
            )

        return result
    except Exception as exc:
        logger.error("Ошибка внешнего intake: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/webhooks/external/{integration}", status_code=201)
async def external_integration_webhook(
    integration: str,
    data: dict,
    x_integration_key: Optional[str] = Header(None, alias="X-Integration-Key"),
):
    if not _integration_key_valid(integration, x_integration_key):
        raise HTTPException(status_code=403, detail="Invalid integration key")

    try:
        if "lead_data" in data and isinstance(data.get("lead_data"), dict):
            lead_payload = data["lead_data"]
        else:
            lead_payload, reason = IntegrationAdapters.normalize(integration, data)
            if not lead_payload:
                return {"status": "ignored", "reason": reason or "unable to normalize"}
        lead = LeadCreate(**lead_payload)
        payload = ExternalLeadIngest(
            lead_data=lead,
            integration=integration,
            event_type=data.get("event_type", "lead"),
            raw_payload=data,
        )
        return await intake_external_lead(payload)
    except Exception as exc:
        logger.error("Ошибка webhook внешней интеграции %s: %s", integration, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/webhooks/amocrm")
async def amocrm_webhook(data: dict):
    try:
        logger.info("Webhook от amoCRM: %s", data)
        leads_updated = data.get("leads", {}).get("updated", [])
        for lead in leads_updated:
            lead_id = lead.get("id")
            status_id = lead.get("status_id")
            if lead_id and status_id == settings.PIPELINE_STATUSES.get("hot_lead"):
                await notifier.notify_hot_lead(lead_id)
        return {"status": "ok"}
    except Exception as exc:
        logger.error("Ошибка webhook amoCRM: %s", exc)
        return {"status": "error", "message": str(exc)}


@app.post("/webhooks/telegram")
async def telegram_webhook(data: dict):
    try:
        logger.info("Webhook от Telegram: %s", data)
        if "lead_data" in data:
            lead_data = LeadCreate(**data["lead_data"])
            lead_data.source = "telegram"
            lead_data.source_platform = "telegram"
            lead_data.source_channel = "message"
            return await create_lead(lead_data)
        return {"status": "ok"}
    except Exception as exc:
        logger.error("Ошибка webhook Telegram: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/webhooks/telephony")
async def telephony_webhook(data: dict):
    try:
        logger.info("Webhook от телефонии: %s", data)
        phone = data.get("phone") or data.get("client_phone") or data.get("caller")
        if not phone:
            return {"status": "ignored", "reason": "phone is missing"}

        lead = LeadCreate(
            name=data.get("name") or data.get("client_name") or "Телефонный лид",
            phone=phone,
            source="phone",
            source_platform="phone",
            source_channel="call",
            source_account=data.get("account") or data.get("line") or data.get("manager"),
            source_listing=data.get("line_name") or data.get("call_source"),
            source_campaign=data.get("campaign") or data.get("call_campaign"),
            comment=data.get("comment") or data.get("record_url") or data.get("notes"),
            client_type=data.get("client_type") or "private",
        )
        return await create_lead(lead)
    except Exception as exc:
        logger.error("Ошибка webhook телефонии: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


LANDING_CONFIG_PATH = Path(__file__).parent / "data" / "landing_config.json"


@app.get("/api/landing-data")
async def get_landing_data():
    try:
        with open(LANDING_CONFIG_PATH, "r", encoding="utf-8") as file:
            config_data = json.load(file)
        return {"status": "success", "data": config_data}
    except Exception as exc:
        logger.error("Ошибка чтения landing config: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/landing-data/update")
async def update_landing_data(
    new_data: dict,
    authorization: str = Header(None, alias="Authorization"),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Необходим API ключ")

    token = authorization.replace("Bearer ", "")
    if token != settings.API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Неверный API ключ")

    try:
        with open(LANDING_CONFIG_PATH, "w", encoding="utf-8") as file:
            json.dump(new_data, file, ensure_ascii=False, indent=2)
        logger.info("Landing config updated")
        return {"status": "success", "message": "Данные обновлены"}
    except Exception as exc:
        logger.error("Ошибка обновления landing config: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/prices")
async def get_prices():
    try:
        with open(LANDING_CONFIG_PATH, "r", encoding="utf-8") as file:
            config_data = json.load(file)
        return {"status": "success", "prices": config_data["pricing"]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Backend API...")
    logger.info("   amoCRM: %s", "configured" if amocrm.is_available() else "not configured")
    logger.info("   storage: %s", "ready" if baserow.is_available() else "not ready")
    logger.info("   Telegram: %s", "configured" if notifier.is_available() else "not configured")
    bot_started = await start_telegram_bot()
    logger.info("   Telegram bot: %s", "started" if bot_started else "disabled or unavailable")
    logger.info("Backend API ready")


@app.on_event("shutdown")
async def shutdown_event():
    await stop_telegram_bot()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
