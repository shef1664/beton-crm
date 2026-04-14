"""
Backend - Интеграционное ядро системы продажи бетона
amoCRM = центр системы, всё остальное = модули
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging
import os
import json
from pathlib import Path

from config import settings
from services.amocrm import AmoCRMService
from services.baserow import BaserowService
from services.calculator import BetonCalculator
from services.notifier import TelegramNotifier
from services.duplicate_checker import DuplicateChecker

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание приложения
app = FastAPI(
    title="Бетон Backend API",
    description="Интеграционное ядро: amoCRM + Baserow + Telegram + Лендинги",
    version="1.0.0"
)

# CORS для лендингов
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # На продакшене ограничить
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация сервисов
amocrm = AmoCRMService()
baserow = BaserowService()
calculator = BetonCalculator()
notifier = TelegramNotifier()
duplicate_checker = DuplicateChecker(amocrm)


# ==================== МОДЕЛИ ДАННЫХ ====================

class LeadCreate(BaseModel):
    name: str = Field(..., description="Имя клиента")
    phone: str = Field(..., description="Телефон")
    source: Optional[str] = Field("landing", description="Источник: landing, telegram, phone")
    concrete_grade: Optional[str] = Field(None, description="Марка бетона (М100-М450)")
    volume: Optional[float] = Field(None, description="Объём в м³")
    address: Optional[str] = Field(None, description="Адрес доставки")
    delivery_date: Optional[str] = Field(None, description="Дата доставки")
    urgency: Optional[str] = Field("normal", description="Срочность: normal, urgent, today")
    payment_method: Optional[str] = Field(None, description="Способ оплаты")
    comment: Optional[str] = Field(None, description="Комментарий")
    calculated_amount: Optional[float] = Field(None, description="Расчётная сумма")
    distance: Optional[float] = Field(None, description="Расстояние в км")
    client_type: Optional[str] = Field("private", description="Тип: private, company")


class LeadUpdate(BaseModel):
    status_id: Optional[int] = None
    concrete_grade: Optional[str] = None
    volume: Optional[float] = None
    calculated_amount: Optional[float] = None
    comment: Optional[str] = None
    manual_check: Optional[bool] = False


class CalculateRequest(BaseModel):
    concrete_grade: str
    volume: float
    distance: Optional[float] = 0


class BotLeadData(BaseModel):
    step: str
    data: dict


# ==================== ENDPOINTS ====================

@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Бетон Backend API",
        "version": "1.0.0",
        "amoCRM": "connected" if amocrm.is_available() else "not configured"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "amoCRM": amocrm.is_available(),
            "baserow": baserow.is_available(),
            "telegram": notifier.is_available()
        }
    }


# Создание лида с лендинга
@app.post("/api/leads/create", status_code=201)
async def create_lead(lead_data: LeadCreate):
    """Создание нового лида (лендинг → backend → amoCRM)"""
    try:
        logger.info(f"Новый лид: {lead_data.name}, {lead_data.phone}")
        
        # Проверка дублей
        is_duplicate = await duplicate_checker.check(lead_data.phone)
        if is_duplicate:
            logger.warning(f"Дубль найден: {lead_data.phone}")
            return {
                "status": "duplicate",
                "message": "Вы уже оставляли заявку. Мы свяжемся с вами!",
                "existing_lead_id": is_duplicate
            }
        
        # Расчёт стоимости если не указан
        if not lead_data.calculated_amount and lead_data.concrete_grade and lead_data.volume:
            lead_data.calculated_amount = calculator.calculate(
                lead_data.concrete_grade,
                lead_data.volume,
                lead_data.distance or 0
            )
        
        # Создание лида в amoCRM
        lead_id = await amocrm.create_lead(lead_data.dict())
        
        # Сохранение в Baserow (лог)
        await baserow.log_lead({
            **lead_data.dict(),
            "lead_id": lead_id,
            "created_at": datetime.now().isoformat()
        })
        
        # Уведомление в Telegram
        await notifier.notify_new_lead(lead_data.dict(), lead_id)
        
        return {
            "status": "success",
            "lead_id": lead_id,
            "message": "Заявка принята! Перезвоним за 5 минут."
        }
        
    except Exception as e:
        logger.error(f"Ошибка создания лида: {e}")
        # Сохраняем в Baserow даже при ошибке
        await baserow.log_error("create_lead", str(e), lead_data.dict())
        raise HTTPException(status_code=500, detail=str(e))


# Обновление лида
@app.patch("/api/leads/{lead_id}")
async def update_lead(lead_id: int, update_data: LeadUpdate):
    """Обновление данных лида"""
    try:
        result = await amocrm.update_lead(lead_id, update_data.dict(exclude_unset=True))
        
        # Если статус изменился на "горячий" - уведомление
        if update_data.status_id and update_data.status_id >= 6:  # Горячий лид
            await notifier.notify_hot_lead(lead_id)
        
        return {"status": "success", "lead_id": lead_id, "result": result}
        
    except Exception as e:
        logger.error(f"Ошибка обновления лида {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Калькулятор
@app.post("/api/calculate")
async def calculate(calc_data: CalculateRequest):
    """Расчёт стоимости бетона"""
    try:
        result = calculator.calculate(
            calc_data.concrete_grade,
            calc_data.volume,
            calc_data.distance
        )
        
        # Логирование расчёта в Baserow
        await baserow.log_calculation(calc_data.dict(), result)
        
        return {
            "status": "success",
            "calculation": result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка расчёта: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Получение списка лидов (для админки)
@app.get("/api/leads")
async def get_leads(status: Optional[str] = None, limit: int = 50):
    """Получение списка лидов из amoCRM"""
    try:
        leads = await amocrm.get_leads(status=status, limit=limit)
        return {"status": "success", "leads": leads, "count": len(leads)}
    except Exception as e:
        logger.error(f"Ошибка получения лидов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Webhook для amoCRM
@app.post("/webhooks/amocrm")
async def amocrm_webhook(data: dict):
    """Webhook от amoCRM (изменение статусов и т.д.)"""
    try:
        logger.info(f"Webhook от amoCRM: {data}")
        
        # Обработка изменений
        if "leads" in data:
            for lead in data["leads"]["updated"]:
                lead_id = lead.get("id")
                new_status_id = lead.get("status_id")
                
                # Если лид стал горячим
                if new_status_id and new_status_id >= 6:
                    await notifier.notify_hot_lead(lead_id)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Ошибка webhook amoCRM: {e}")
        return {"status": "error", "message": str(e)}


# Webhook для Telegram бота
@app.post("/webhooks/telegram")
async def telegram_webhook(data: dict):
    """Получение данных от Telegram бота"""
    try:
        logger.info(f"Webhook от Telegram: {data}")
        
        # Создание лида из бота
        if "lead_data" in data:
            lead_data = LeadCreate(**data["lead_data"])
            lead_data.source = "telegram"
            
            result = await create_lead(lead_data)
            return result
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Ошибка webhook Telegram: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ЛЕНДИНГ ДАННЫЕ ====================

LANDING_CONFIG_PATH = Path(__file__).parent / "data" / "landing_config.json"

@app.get("/api/landing-data")
async def get_landing_data():
    """Получить данные для лендинга (цены, тексты, контакты)"""
    try:
        with open(LANDING_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return {"status": "success", "data": config}
    except Exception as e:
        logger.error(f"Ошибка чтения конфига лендинга: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/landing-data/update")
async def update_landing_data(new_data: dict):
    """Обновить данные лендинга (только для админа)"""
    try:
        with open(LANDING_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        logger.info("✅ Данные лендинга обновлены")
        return {"status": "success", "message": "Данные обновлены"}
    except Exception as e:
        logger.error(f"Ошибка обновления конфига: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prices")
async def get_prices():
    """Только цены для быстрого доступа"""
    try:
        with open(LANDING_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return {"status": "success", "prices": config["pricing"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Запуск бота при старте
@app.on_event("startup")
async def startup_event():
    """Запуск Telegram бота при старте приложения"""
    logger.info("🚀 Запуск Backend API...")
    
    if settings.TELEGRAM_BOT_TOKEN:
        try:
            from bot.main import start_bot
            import asyncio
            asyncio.create_task(start_bot())
            logger.info("✅ Telegram бот запущен")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось запустить бота: {e}")
    
    logger.info("✅ Backend API готов")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )
