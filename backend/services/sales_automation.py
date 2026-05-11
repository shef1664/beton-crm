"""Automatic sales routing, SLA and playbook recommendations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from config import settings
from services.lead_utils import coerce_amount


class SalesAutomationService:
    def __init__(self):
        self.rules = settings.SALES_AUTOMATION_RULES
        self.managers = settings.SALES_MANAGERS
        self.playbooks = settings.SALES_PLAYBOOKS

    def _resolve_playbook(self, route_bucket: str) -> dict[str, Any]:
        return self.playbooks.get(route_bucket) or self.playbooks.get("default", {})

    def evaluate(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        source_platform = str(lead_data.get("source_platform") or lead_data.get("source") or "site")
        source_channel = str(lead_data.get("source_channel") or "form")
        urgency = str(lead_data.get("urgency") or "normal").lower()
        amount = coerce_amount(lead_data.get("calculated_amount")) or 0

        sales_priority = "normal"
        lead_status = "new"
        next_action = "Первичный контакт менеджера"
        route_bucket = "default"

        if source_platform in self.rules["high_priority_sources"] or urgency in self.rules["hot_urgency_values"]:
            sales_priority = "high"
            lead_status = "qualification"
            next_action = "Быстрый контакт и квалификация"

        if amount >= self.rules["high_priority_amount"]:
            sales_priority = "high"
            lead_status = "calculation"
            next_action = "Срочно отправить расчет и подтвердить детали"

        if source_platform in self.rules["marketplace_sources"]:
            route_bucket = "marketplaces"
            if sales_priority == "normal":
                lead_status = "data_collection"
                next_action = "Уточнить потребность по объявлению и объекту"

        elif source_platform in self.rules["messenger_sources"]:
            route_bucket = "messengers"
            if sales_priority == "normal":
                lead_status = "qualification"
                next_action = "Дожать до телефона и параметров заказа"

        elif source_platform == "phone" or source_channel == "call":
            route_bucket = "phone"
            sales_priority = "high"
            lead_status = "qualification"
            next_action = "Обработать как горячий звонок"

        elif source_platform in ("yandex_maps", "2gis"):
            route_bucket = "geo"
            if sales_priority == "normal":
                sales_priority = "high"
                lead_status = "qualification"
                next_action = "Перехватить лид с геосервиса и закрепить контакт"

        assigned_manager = self.managers.get(route_bucket) or self.managers.get("default", "sales-team")
        playbook = self._resolve_playbook(route_bucket)
        sla_minutes = int(playbook.get("sla_minutes", 30))
        deadline_at = (datetime.now(timezone.utc) + timedelta(minutes=sla_minutes)).isoformat()

        return {
            "sales_priority": sales_priority,
            "lead_status": lead_status,
            "assigned_manager": assigned_manager,
            "next_action": next_action,
            "route_bucket": route_bucket,
            "sales_playbook": playbook.get("sales_playbook", "standard_followup"),
            "qualification_script": playbook.get(
                "qualification_script",
                "Уточнить объем, марку, адрес, дату и способ оплаты.",
            ),
            "sla_minutes": sla_minutes,
            "contact_deadline_at": deadline_at,
        }
