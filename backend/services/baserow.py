"""Baserow интеграция - слой логирования и хранения"""
import httpx
import logging
from typing import Dict
from config import settings

logger = logging.getLogger(__name__)

class BaserowService:
    def __init__(self):
        self.base_url = settings.BASEROW_URL
        self.token = settings.BASEROW_TOKEN
        self.leads_table = settings.BASEROW_LEADS_TABLE_ID
        self.logs_table = settings.BASEROW_LOGS_TABLE_ID
        self.is_configured = bool(self.token)
    
    def is_available(self) -> bool:
        return self.is_configured
    
    async def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json"
        }
    
    async def log_lead(self, lead_data: Dict):
        """Логирование лида в Baserow"""
        if not self.is_configured:
            logger.warning("Baserow не настроен - лид не сохранён")
            return
        
        try:
            data = {
                "name": lead_data.get("name"),
                "phone": lead_data.get("phone"),
                "source": lead_data.get("source"),
                "concrete_grade": lead_data.get("concrete_grade"),
                "volume": lead_data.get("volume"),
                "address": lead_data.get("address"),
                "calculated_amount": lead_data.get("calculated_amount"),
                "created_at": lead_data.get("created_at"),
                "lead_id": lead_data.get("lead_id")
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/database/rows/table/{self.leads_table}/",
                    headers=await self._get_headers(),
                    json=data
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Лид сохранён в Baserow")
                else:
                    logger.error(f"Ошибка сохранения в Baserow: {response.text}")
                    
        except Exception as e:
            logger.error(f"Ошибка логирования лида: {e}")
    
    async def log_calculation(self, calc_data: Dict, result: Dict):
        """Логирование расчёта"""
        if not self.is_configured:
            return
        
        try:
            data = {
                "concrete_grade": calc_data.get("concrete_grade"),
                "volume": calc_data.get("volume"),
                "distance": calc_data.get("distance"),
                "total_amount": result.get("total"),
                "timestamp": result.get("timestamp")
            }
            
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.base_url}/api/database/rows/table/{self.logs_table}/",
                    headers=await self._get_headers(),
                    json=data
                )
                
        except Exception as e:
            logger.error(f"Ошибка логирования расчёта: {e}")
    
    async def log_error(self, action: str, error: str, data: Dict):
        """Логирование ошибки"""
        if not self.is_configured:
            return
        
        try:
            error_data = {
                "action": action,
                "error": error,
                "data": str(data)[:1000],  # Ограничение длины
                "timestamp": data.get("created_at", "")
            }
            
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.base_url}/api/database/rows/table/{self.logs_table}/",
                    headers=await self._get_headers(),
                    json=error_data
                )
                
        except Exception as e:
            logger.error(f"Ошибка логирования ошибки: {e}")
