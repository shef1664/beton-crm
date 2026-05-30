# 🎙 Voice-robot — Бетон42

Голосовой бот для входящих звонков на 8 (3842) 63-55-88.

**Стек:** Voximplant (SIP, ASR) + Yandex SpeechKit (TTS) + наш backend (Claude-логика).
**Решение:** см. `RECOMMENDATION-2026-05-25.md`.

---

## Файлы

| Файл | Что |
|---|---|
| `voxengine-scenario.js` | JS-сценарий VoxEngine: приём звонка, цикл «слушаю → backend → говорю». Загружается в Voximplant Application. |
| `backend-handler.py` | FastAPI endpoint `/api/voice/turn` — принимает текст от ASR, отдаёт следующую фразу бота. Сценарий-5-вопросов аналогичный `qualify-leads.py`. |
| `STACK-COMPARISON.md` | 4 варианта стеков, плюсы/минусы. |
| `RECOMMENDATION-2026-05-25.md` | Финальная рекомендация и план на 5 рабочих дней. |

---

## Как поднять (по шагам)

### 1. Backend (локально для тестов)

```bash
pip install fastapi uvicorn
python3 /Users/a0000/Documents/Бетон-deploy/voice-robot/backend-handler.py
# слушает 0.0.0.0:8080
```

Проверить:
```bash
curl -X POST http://localhost:8080/api/voice/turn \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"test-1","text":"нужно 6 кубов М300","history":[]}'
# должен вернуть {"text": "Скажите адрес объекта..."}
```

### 2. Backend в проде (Render)

Создать в Render новый Web Service:
- Repo / папка `voice-robot/`
- Start command: `uvicorn backend-handler:app --host 0.0.0.0 --port $PORT`
- Plan: Free (для теста) или Starter $7
- URL получится: `https://beton-voice-XXXX.onrender.com`

### 3. Voximplant Application

1. Зарегистрироваться: https://manage.voximplant.com/registration
2. Создать Application: `beton42-voice`
3. Создать Scenario: `voice-main` — вставить содержимое `voxengine-scenario.js`
4. Создать Routing Rule: pattern `.*` → scenario `voice-main`
5. В Application properties (Custom Data) добавить:
   ```json
   {
     "backendUrl": "https://beton-voice-XXXX.onrender.com/api/voice/turn",
     "yandexApiKey": "<API Key из Yandex Cloud SpeechKit>",
     "yandexFolderId": "<folder_id Yandex Cloud>",
     "fallbackPhone": "79050000000"
   }
   ```

### 4. SIP-номер

**Вариант А (рекомендую):** перевод входящих с 8 (3842) 63-55-88 на номер Voximplant через текущего оператора.
**Вариант Б:** виртуальный номер Voximplant (250 ₽/мес).

В Voximplant: Numbers → Buy или Connect SIP, привязать к Application `beton42-voice`.

### 5. Yandex SpeechKit

1. Yandex Cloud → SpeechKit → Включить.
2. Создать сервисный аккаунт с ролью `ai.speechkit-tts.user`.
3. Создать API Key для этого аккаунта.
4. Положить в Voximplant Custom Data (см. шаг 3).

### 6. Тестовый прогон

С личного телефона позвонить на номер. Бот должен:
- сказать приветствие с предупреждением о записи
- задать вопрос про объём и марку
- слушать → парсить → задавать следующий вопрос
- передать менеджеру при триггере «срочно/НДС/насос/менеджер»

Если что-то не работает — смотреть Voximplant Application → Calls → Logs (там события и текст ASR).

---

## Что НЕ закрыто (нужны решения)

- [ ] Approve стека (см. `RECOMMENDATION-2026-05-25.md`)
- [ ] Voximplant аккаунт (нужна симка для SMS-верификации)
- [ ] Yandex Cloud SpeechKit (привязка карты для биллинга)
- [ ] Перевод SIP с 8 (3842) 63-55-88 на Voximplant (звонок оператору)
- [ ] Согласие на запись звонков — финальная формулировка приветствия от шефа
- [ ] Запуск backend на Render (после approve)
- [ ] 10 тестовых звонков шеф ↔ бот
