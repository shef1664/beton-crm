"""Проверка дублей по телефону"""
import logging
import httpx
from services.amocrm import AmoCRMService

logger = logging.getLogger(__name__)

class DuplicateChecker:
    def __init__(self, amocrm: AmoCRMService):
        self.amocrm = amocrm

    async def check(self, phone: str) -> int:
        """Проверка дубля по телефону. Возвращает ID существующего лида или 0"""
        if not self.amocrm.is_available():
            return 0

        try:
            # Поиск по контактам
            base_url = self.amocrm.base_url
            headers = await self.amocrm._get_headers()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/contacts",
                    headers=headers,
                    params={"filter[custom_fields_values][phone]": phone}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    contacts = data.get("_embedded", {}).get("items", [])
                    
                    if contacts:
                        contact_id = contacts[0]["id"]
                        
                        # Поиск лидов по этому контакту
                        leads_response = await client.get(
                            f"{base_url}/leads",
                            headers=headers,
                            params={"filter[contact_id]": contact_id}
                        )
                        
                        if leads_response.status_code == 200:
                            leads_data = leads_response.json()
                            leads = leads_data.get("_embedded", {}).get("items", [])
                            
                            if leads:
                                logger.info(f"Дубль найден: {phone}, лид #{leads[0]['id']}")
                                return leads[0]["id"]
            
            return 0
            
        except Exception as e:
            logger.error(f"Ошибка проверки дубля: {e}")
            return 0
