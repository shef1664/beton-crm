# Voximplant activation — Бетон42

Статус: инструкция для запуска после решения шефа. Codex не регистрирует аккаунт без симки.

1. Открыть https://manage.voximplant.com/registration.
2. Зарегистрировать аккаунт на email юрлица/шефа и подтвердить SMS.
3. Создать Application: `beton42-voice`.
4. Создать Scenario: `voice-main`.
5. Вставить содержимое `voice-robot/voxengine-scenario.js`.
6. Создать Routing Rule: pattern `.*` → scenario `voice-main`.
7. В Custom Data приложения задать:

```json
{
  "backendUrl": "https://beton42-voice-backend.onrender.com/api/voice/turn",
  "yandexApiKey": "<SPEECHKIT_API_KEY>",
  "yandexFolderId": "<YANDEX_FOLDER_ID>",
  "fallbackPhone": "<номер менеджера>"
}
```

8. Подключить SIP/номер:
   - безопасный вариант: тестовый номер Voximplant;
   - боевой вариант: переадресация с `8 (3842) 63-55-88` после 10 тестовых звонков.
9. Сделать 10 тестовых звонков:
   - обычная заявка;
   - срочная заявка;
   - НДС/юрлицо;
   - насос;
   - клиент молчит;
   - клиент просит менеджера.

Боевой номер подключать только после успешных тестов.
