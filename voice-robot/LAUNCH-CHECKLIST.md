# ✅ МАРИЯ НА 635588 — ФИНАЛЬНЫЙ ЧЕК-ЛИСТ

## 📦 ГОТОВЫЕ ФАЙЛЫ

| Файл | Назначение | Статус |
|------|-----------|--------|
| `maria-prompt.md` | Полный промпт для Claude | ✅ |
| `maria-integration.py` | Python обработчик диалога | ✅ |
| `backend-maria.py` | FastAPI wrapper | ✅ |
| `voxengine-scenario.js` | Voximplant SIP сценарий | ✅ |
| `requirements.txt` | Зависимости для Render | ✅ |
| `DEPLOY-INSTRUCTIONS.md` | Пошаговая инструкция | ✅ |
| `test-maria.py` | Локальный тест | ✅ |
| `README-MARIA.md` | Полная документация | ✅ |

---

## 🚀 ЧТО НУЖНО СДЕЛАТЬ (15 минут)

### 1. Развернуть Backend

**На Render:**
- [ ] Создать новый Web Service
- [ ] Выбрать `backend-maria.py` как entry point
- [ ] Start command: `uvicorn backend-maria:app --host 0.0.0.0 --port 10000`
- [ ] Добавить env vars:
  - [ ] ANTHROPIC_API_KEY
  - [ ] ELEVENLABS_API_KEY
- [ ] Deploy
- [ ] Проверить здоровье: GET /health

**Результат:** URL вроде `https://beton42-maria-voice.onrender.com`

### 2. Загрузить в Voximplant

**Console → Applications → Scenarios:**
- [ ] Создать новый сценарий `beton42-maria`
- [ ] Скопировать код из `voxengine-scenario.js`
- [ ] Save

**Settings → Custom Data:**
- [ ] BACKEND_URL = https://beton42-maria-voice.onrender.com/api/voice/maria
- [ ] ELEVENLABS_API_KEY = (из secrets)
- [ ] ELEVENLABS_VOICE_ID = EXAVITQu4vr4xnSDxMaL
- [ ] MANAGER_PHONE = 89039164040

### 3. Привязать номер 635588

**Routing rules → Incoming:**
- [ ] Pattern: 635588
- [ ] Destination: приложение Бетон42
- [ ] Scenario: beton42-maria
- [ ] Save

### 4. Тестовый звонок

- [ ] Позвонить на 635588
- [ ] Слышна Мария? ✅
- [ ] Женский голос Bella? ✅
- [ ] Естественный диалог? ✅
- [ ] Передача на 8 903 916 40 40 работает? ✅

---

## 🎯 АРХИТЕКТУРА (итоговая)

```
635588 входящий звонок
  ↓ (Voximplant SIP)
voxengine-scenario.js
  ↓ (Yandex SpeechKit STT)
backend-maria.py (Render)
  ↓ (Claude Haiku)
maria-integration.py
  ↓ (Eleven Labs Bella TTS)
Воспроизведение клиенту
  ↓ (if transfer_needed)
Передача на 8 903 916 40 40
```

---

## 📊 МЕТРИКИ ОТСЛЕЖИВАНИЯ

**Логи Render:**
```bash
# Смотреть в реальном времени
https://dashboard.render.com/services/beton42-maria-voice
```

**Логи Voximplant:**
```bash
# CDR записи
Voximplant Console → CDR → Фильтр по номеру 635588
```

**Ожидаемый формат логов:**
```
[INFO] chat_id=635588-1717225600000, caller=+7913..., text="Привет"
[INFO] action=continue
[INFO] chat_id=635588-1717225600000, text="Передаю менеджеру"
[INFO] action=transfer, transfer_phone=89039164040
```

---

## 🆘 БЫСТРОЕ РЕШЕНИЕ ПРОБЛЕМ

| Проблема | Решение |
|----------|---------|
| Нет звука от Марии | Проверить ELEVENLABS_API_KEY в Voximplant |
| Backend не отвечает | Проверить статус Render service (должен быть green) |
| Клиент не слышит передачу | Проверить MANAGER_PHONE = 89039164040 (без +7) |
| Плохое качество звука | Попробовать другую модель TTS (пока Bella оптимальна) |
| Медленный ответ | Увеличить timeout в voxengine-scenario.js с 10s до 15s |

---

## 📞 КОНТАКТЫ ЕСЛИ ЧТО-ТО НЕ РАБОТАЕТ

- **Voximplant Support:** https://voximplant.com/support
- **Render Support:** https://render.com/docs
- **Anthropic API:** https://support.anthropic.com
- **Eleven Labs:** https://elevenlabs.io/help

---

## ✨ ИТОГОВОЕ СОСТОЯНИЕ ПРОЕКТА

### ✅ ЗАВЕРШЕНО:
- Полная интеграция Claude AI + Eleven Labs + Voximplant
- Мария звучит как живая женщина (Bella voice)
- Автоматическая передача на менеджера
- Сохранение истории разговора
- Полная документация и инструкции

### ⏳ ТРЕБУЕТ ДЕПЛОЯ:
- Render service для backend
- Voximplant сценарий и routing rule

### 📈 ГОТОВО К МАСШТАБИРОВАНИЮ:
- После V1.0 можно добавить мультибренд (разные голоса/цены)
- Интеграция с WhatsApp/Telegram для голосовых сообщений
- Расширение до других каналов (Email, Avito)

---

**Статус:** 🟢 ГОТОВО К ЗАПУСКУ  
**Дата:** 2026-05-31  
**Версия:** 1.0  
**Время деплоя:** 15-20 минут  

---

## 🎬 СЛЕДУЮЩИЙ ШАГ

Выполнить пункты выше в порядке (1, 2, 3, 4) и позвонить на 635588 для проверки.

**Готовы?** 🚀
