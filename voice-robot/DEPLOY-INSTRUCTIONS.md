# 🚀 ДЕПЛОЙ МАРИИ НА 635588

**Цель:** Запустить голосовой бот Марии на номер 635588

**Время:** ~15 минут

---

## ШАГ 1: Развернуть backend на Render

### 1.1 Создать новый Render Service

1. Открыть https://dashboard.render.com/
2. **Create** → **Web Service**
3. Выбрать GitHub repo (или загрузить исходники)
4. Назвать: `beton42-maria-voice` (или другое)

### 1.2 Конфигурация

**Build command:**
```bash
pip install -r requirements.txt
```

**Start command:**
```bash
uvicorn backend-maria:app --host 0.0.0.0 --port 10000
```

### 1.3 Environment variables

Добавить в Render (Settings → Environment):

```
ANTHROPIC_API_KEY=sk-ant-...  (из secrets/anthropic_api_key.txt)
ELEVENLABS_API_KEY=...        (из secrets/elevenlabs_api_key.txt)
```

### 1.4 Deploy

Нажать **Create Web Service** → дождаться деплоя (~2 мин)

**URL будет примерно:** `https://beton42-maria-voice.onrender.com`

---

## ШАГ 2: Загрузить сценарий в Voximplant

### 2.1 В Voximplant Console

1. Зайти в https://voximplant.com/cabinet/ → **Applications**
2. Выбрать приложение Бетон42 (или создать новое)
3. **Scenarios** → **Create new**

### 2.2 Загрузить код

Скопировать содержимое `voxengine-scenario.js` в редактор сценария.

Сохранить как: `beton42-maria`

### 2.3 Настроить Application Properties

**Settings** → **Scenario parameters** (или Custom data):

```
BACKEND_URL = https://beton42-maria-voice.onrender.com/api/voice/maria
ELEVENLABS_API_KEY = (скопировать из secrets/elevenlabs_api_key.txt)
ELEVENLABS_VOICE_ID = EXAVITQu4vr4xnSDxMaL
MANAGER_PHONE = 89039164040
```

---

## ШАГ 3: Привязать номер 635588

### 3.1 В Voximplant Console

**Routing rules** → **Incoming rules**

### 3.2 Создать правило

| Параметр | Значение |
|----------|----------|
| Name | `635588-maria` |
| Incoming: Pattern | `635588` |
| Incoming: Destination | Приложение Бетон42 |
| Scenario | `beton42-maria` |

### 3.3 Сохранить

**Save** → правило активно

---

## ШАГ 4: Тестирование

### 4.1 Позвонить на 635588

Позвонить с мобильного:
```
+7-913-120-0300 → 635588
```

### 4.2 Слышите ли Марию?

- ✅ Приветствие "Добрый день! Компания Бетон42..."
- ✅ Женский голос (Bella)
- ✅ Естественное произношение

### 4.3 Провести тестовый диалог

```
Вы: "Привет, сколько стоит бетон М300?"
Мария: "Здравствуйте! М300 стоит 7 245 рублей за куб..."

Вы: "5 кубов"
Мария: "Хороший объём! Где доставить?"

Вы: "Кемерово, ул. Ленина"
Мария: "Принял заявку..."

Вы: "А если мне нужно СРОЧНО, через час?"
Мария: "Давайте я подключу менеджера - он подберёт вариант."
[ПЕРЕДАЧА НА 8 903 916 40 40]
```

---

## ШАГ 5: Мониторинг

### 5.1 Логи Render

https://dashboard.render.com/ → Service → Logs

Искать:
```
chat_id=635588-..., text=...
action=continue | action=transfer
```

### 5.2 Логи Voximplant

Voximplant Console → **CDR** (Call Detail Records)

Ищи:
- Входящие звонки на 635588
- Статус: connected, transfer, completed

---

## 🔧 TROUBLESHOOTING

### Проблема: Нет звука от Марии

**Проверить:**
1. ✅ ELEVENLABS_API_KEY установлен в Voximplant
2. ✅ Render service работает (green status)
3. ✅ Logs не показывают ошибок

**Fallback:** Сценарий автоматически перейдёт на встроенный Yandex TTS

### Проблема: Backend не отвечает

**Проверить:**
1. ✅ URL в сценарии правильный
2. ✅ `curl https://beton42-maria-voice.onrender.com/health`
3. ✅ Logs Render для ошибок

### Проблема: Клиент не слышит передачу

**Проверить:**
1. ✅ MANAGER_PHONE в конфиге правильный (89039164040)
2. ✅ Номер менеджера активен
3. ✅ Voximplant может звонить на этот номер

---

## 📝 CHECKLIST

- [ ] Backend развёрнут на Render (URL: https://beton42-maria-voice.onrender.com)
- [ ] Сценарий загружен в Voximplant (beton42-maria)
- [ ] Application Properties установлены (BACKEND_URL, API ключи)
- [ ] Routing rule создана для 635588
- [ ] Тестовый звонок проведён
- [ ] Слышна Мария (женский голос Bella)
- [ ] Передача на менеджера работает
- [ ] Логи проверены на ошибки

---

## 🎯 ГОТОВО!

После выполнения всех шагов:

✅ Номер 635588 слушает входящие звонки  
✅ Клиент слышит Марию (женский голос)  
✅ Диалог естественный и человеческий  
✅ При передаче клиент попадает на менеджера  

**Время до полного запуска:** ~30 минут (включая тестирование)

---

**Версия:** 1.0  
**Дата:** 2026-05-31
