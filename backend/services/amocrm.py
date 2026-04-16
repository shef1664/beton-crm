"""amoCRM интеграция - центр системы"""
import httpx
import logging
from typing import Optional, Dict, List
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
            "Content-Type": "application/json"
        }
    
    async def create_lead(self, lead_data: Dict) -> int:
        """Создание лида в amoCRM"""
        if not self.is_configured:
            logger.warning("amoCRM не настроен - лид сохранён в Baserow")
            return 0
        
        # Формирование данных для amoCRM API
        contacts_data = [{
            "name": lead_data.get("name", ""),
            "custom_fields_values": [
                {
                    "field_code": "PHONE",
                    "values": [{"value": lead_data.get("phone", "")}]
                }
            ]
        }]
        
        # Создание контакта
        async with httpx.AsyncClient() as client:
            contact_response = await client.post(
                f"{self.base_url}/contacts",
                headers=await self._get_headers(),
                json=contacts_data
            )
            contact_response.raise_for_status()
            contact_id = contact_response.json()["_embedded"]["items"][0]["id"]
            
            # Создание сделки (лида)
            lead_data_amo = [{
                "name": f"Заявка: {lead_data.get('name', 'Без имени')} - {lead_data.get('concrete_grade', 'Не указана')}",
                "pipeline_id": settings.AMOCRM_PIPELINE_ID,
                "status_id": settings.PIPELINE_STATUSES["new"],
                "_embedded": {
                    "contacts": [{"id": contact_id}]
                },
                "custom_fields_values": [
                    {"field_code": "PHONE", "values": [{"value": lead_data.get("phone", "")}]},
                    {"field_code": "SOURCE", "values": [{"value": lead_data.get("source", "landing")}]},
                    {"field_code": "concrete_grade", "values": [{"value": lead_data.get("concrete_grade", "")}]},
                    {"field_code": "volume", "values": [{"value": str(lead_data.get("volume", 0))}]},
                    {"field_code": "address", "values": [{"value": lead_data.get("address", "")}]},
                    {"field_code": "delivery_date", "values": [{"value": lead_data.get("delivery_date", "")}]},
                    {"field_code": "urgency", "values": [{"value": lead_data.get("urgency", "normal")}]},
                    {"field_code": "payment_method", "values": [{"value": lead_data.get("payment_method", "")}]},
                    {"field_code": "calculated_amount", "values": [{"value": str(lead_data.get("calculated_amount", 0))}]},
                    {"field_code": "distance", "values": [{"value": str(lead_data.get("distance", 0))}]},
                    {"field_code": "comment", "values": [{"value": lead_data.get("comment", "")}]}
                ]
            }]
            
            lead_response = await client.post(
                f"{self.base_url}/leads",
                headers=await self._get_headers(),
                json=lead_data_amo
            )
            lead_response.raise_for_status()
            lead_id = lead_response.json()["_embedded"]["items"][0]["id"]
            
            logger.info(f"✅ Лид создан в amoCRM: {lead_id}")
            return lead_id
    
    async def update_lead(self, lead_id: int, update_data: Dict) -> Dict:
        """Обновление лида в amoCRM"""
        if not self.is_configured:
            return {"status": "amoCRM not configured"}
        
        update_payload = [{
            "id": lead_id,
            **{k: v for k, v in update_data.items() if k != "manual_check"}
        }]
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.base_url}/leads",
                headers=await self._get_headers(),
                json=update_payload
            )
            response.raise_for_status()
            return response.json()
    
    async def get_leads(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Получение списка лидов"""
        if not self.is_configured:
            return []
        
        params = {"limit": limit}
        if status:
            params["filter[status_id]"] = settings.PIPELINE_STATUSES.get(status)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/leads",
                headers=await self._get_headers(),
                params=params
            )
            response.raise_for_status()
            return response.json()["_embedded"]["items"]
    
    async def add_comment(self, lead_id: int, comment: str):
        """Добавление комментария к лиду"""
        if not self.is_configured:
            return
        
        comment_data = [{
            "lead_id": lead_id,
            "comment": comment
        }]
        
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.base_url}/leads/{lead_id}/notes",
                headers=await self._get_headers(),
                json=comment_data
            )
