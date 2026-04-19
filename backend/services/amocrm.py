"""amoCRM integration for the concrete sales funnel."""

import logging
from typing import Any, Dict, List, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class AmoCRMService:
    def __init__(self):
        domain = settings.AMOCRM_DOMAIN
        if domain and not domain.endswith(".amocrm.ru"):
            domain = f"{domain}.amocrm.ru"
        self.base_url = f"https://{domain}/api/v4"
        self.access_token = settings.AMOCRM_ACCESS_TOKEN
        self.is_configured = bool(self.access_token and settings.AMOCRM_DOMAIN)

    def is_available(self) -> bool:
        return self.is_configured

    async def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _format_field_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip()
        return text or None

    def _build_custom_fields(self, lead_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        field_map = settings.AMOCRM_CUSTOM_FIELD_IDS
        if not field_map:
            return []

        payload: List[Dict[str, Any]] = []
        for field_name, field_id in field_map.items():
            if field_name not in lead_data:
                continue

            value = self._format_field_value(lead_data.get(field_name))
            if value is None:
                continue

            try:
                numeric_id = int(field_id)
            except (TypeError, ValueError):
                logger.warning("Invalid amoCRM field id for %s: %s", field_name, field_id)
                continue

            payload.append(
                {
                    "field_id": numeric_id,
                    "values": [{"value": value}],
                }
            )

        return payload

    @staticmethod
    def _build_details(lead_data: Dict[str, Any]) -> List[str]:
        field_labels = (
            ("source_platform", "Platform"),
            ("source_channel", "Channel"),
            ("source_account", "Account"),
            ("source_listing", "Listing"),
            ("source_campaign", "Campaign"),
            ("sales_priority", "Sales priority"),
            ("assigned_manager", "Assigned manager"),
            ("lead_status", "Recommended status"),
            ("next_action", "Next action"),
            ("route_bucket", "Route bucket"),
            ("sales_playbook", "Sales playbook"),
            ("qualification_script", "Qualification script"),
            ("sla_minutes", "SLA minutes"),
            ("contact_deadline_at", "Contact deadline"),
            ("utm_source", "UTM source"),
            ("utm_medium", "UTM medium"),
            ("utm_campaign", "UTM campaign"),
            ("client_type", "Client type"),
            ("concrete_grade", "Concrete grade"),
            ("volume", "Volume"),
            ("address", "Address"),
            ("delivery_date", "Delivery date"),
            ("calculated_amount", "Calculated amount"),
            ("comment", "Comment"),
        )

        details: List[str] = []
        for field_name, label in field_labels:
            value = lead_data.get(field_name)
            if value in (None, ""):
                continue
            suffix = " m3" if field_name == "volume" else ""
            suffix = " RUB" if field_name == "calculated_amount" else suffix
            details.append(f"{label}: {value}{suffix}")
        return details

    async def create_lead(self, lead_data: Dict[str, Any]) -> int:
        if not self.is_configured:
            logger.warning("amoCRM is not configured, lead will stay local")
            return 0

        contacts_data = [
            {
                "name": lead_data.get("name", ""),
                "custom_fields_values": [
                    {
                        "field_code": "PHONE",
                        "values": [{"value": lead_data.get("phone", "")}],
                    }
                ],
            }
        ]

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                contact_response = await client.post(
                    f"{self.base_url}/contacts",
                    headers=await self._get_headers(),
                    json=contacts_data,
                )
                contact_response.raise_for_status()
                embedded_contacts = contact_response.json()["_embedded"]
                contact_id = (embedded_contacts.get("contacts") or embedded_contacts.get("items"))[0]["id"]

                source_label = lead_data.get("source_platform") or lead_data.get("source") or "lead"
                custom_fields_values = self._build_custom_fields(lead_data)
                lead_payload = [
                    {
                        "name": (
                            f"{source_label}: "
                            f"{lead_data.get('name', 'No name')} - "
                            f"{lead_data.get('concrete_grade', 'No grade')}"
                        ),
                        "pipeline_id": settings.AMOCRM_PIPELINE_ID,
                        "status_id": settings.PIPELINE_STATUSES["new"],
                        "_embedded": {"contacts": [{"id": contact_id}]},
                        **({"custom_fields_values": custom_fields_values} if custom_fields_values else {}),
                    }
                ]

                lead_response = await client.post(
                    f"{self.base_url}/leads",
                    headers=await self._get_headers(),
                    json=lead_payload,
                )
                if lead_response.status_code not in (200, 201):
                    logger.error("amoCRM leads error: %s", lead_response.text[:500])
                lead_response.raise_for_status()
                embedded_leads = lead_response.json()["_embedded"]
                lead_id = (embedded_leads.get("leads") or embedded_leads.get("items"))[0]["id"]

                details = self._build_details(lead_data)
                if details:
                    await client.post(
                        f"{self.base_url}/leads/{lead_id}/notes",
                        headers=await self._get_headers(),
                        json=[{"note_type": "common", "params": {"text": "\n".join(details)}}],
                    )

                logger.info("Lead created in amoCRM: %s", lead_id)
                return lead_id
        except Exception as exc:
            logger.error("amoCRM temporarily unavailable, lead kept locally: %s", exc)
            return 0

    async def update_lead(self, lead_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_configured:
            return {"status": "amoCRM not configured"}

        update_payload = [{"id": lead_id, **{k: v for k, v in update_data.items() if k != "manual_check"}}]

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.patch(
                f"{self.base_url}/leads",
                headers=await self._get_headers(),
                json=update_payload,
            )
            response.raise_for_status()
            return response.json()

    async def get_leads(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []

        params = {"limit": limit}
        if status:
            params["filter[status_id]"] = settings.PIPELINE_STATUSES.get(status)

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}/leads",
                headers=await self._get_headers(),
                params=params,
            )
            response.raise_for_status()
            embedded = response.json().get("_embedded", {})
            return embedded.get("leads") or embedded.get("items") or []

    async def add_comment(self, lead_id: int, comment: str):
        if not self.is_configured:
            return

        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(
                f"{self.base_url}/leads/{lead_id}/notes",
                headers=await self._get_headers(),
                json=[{"note_type": "common", "params": {"text": comment}}],
            )
