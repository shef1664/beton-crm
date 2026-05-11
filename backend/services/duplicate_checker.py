"""Duplicate detection for leads by phone."""

import logging

import httpx

from services.amocrm import AmoCRMService
from services.lead_utils import normalize_phone, phone_variants

logger = logging.getLogger(__name__)


class DuplicateChecker:
    def __init__(self, amocrm: AmoCRMService, storage=None):
        self.amocrm = amocrm
        self.storage = storage

    async def check(self, phone: str) -> int:
        normalized_phone = normalize_phone(phone)
        if not normalized_phone:
            return 0

        if self.storage:
            local_lead = self.storage.find_lead_by_phone(normalized_phone)
            if local_lead:
                lead_id = int(local_lead.get("lead_id") or local_lead.get("id") or 0)
                logger.info(f"Duplicate found in SQLite: {normalized_phone} -> {lead_id}")
                return lead_id

        if not self.amocrm.is_available():
            return 0

        try:
            base_url = self.amocrm.base_url
            headers = await self.amocrm._get_headers()

            async with httpx.AsyncClient(timeout=15) as client:
                for query in phone_variants(normalized_phone):
                    response = await client.get(
                        f"{base_url}/contacts",
                        headers=headers,
                        params={"query": query},
                    )
                    if response.status_code != 200:
                        continue

                    data = response.json()
                    contacts = (
                        data.get("_embedded", {}).get("contacts")
                        or data.get("_embedded", {}).get("items")
                        or []
                    )
                    for contact in contacts:
                        linked_leads = contact.get("_embedded", {}).get("leads") or []
                        if linked_leads and linked_leads[0].get("id"):
                            lead_id = int(linked_leads[0]["id"])
                            logger.info(f"Duplicate found in amoCRM contacts: {normalized_phone} -> {lead_id}")
                            return lead_id

                for query in phone_variants(normalized_phone):
                    response = await client.get(
                        f"{base_url}/leads",
                        headers=headers,
                        params={"query": query},
                    )
                    if response.status_code != 200:
                        continue

                    data = response.json()
                    leads = (
                        data.get("_embedded", {}).get("leads")
                        or data.get("_embedded", {}).get("items")
                        or []
                    )
                    if leads and leads[0].get("id"):
                        lead_id = int(leads[0]["id"])
                        logger.info(f"Duplicate found in amoCRM leads: {normalized_phone} -> {lead_id}")
                        return lead_id
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")

        return 0
