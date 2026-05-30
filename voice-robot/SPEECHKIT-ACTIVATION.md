# Yandex SpeechKit activation — Бетон42

Статус: инструкция. Нужен доступ к Yandex Cloud и биллинг.

1. Открыть https://console.cloud.yandex.ru.
2. Выбрать существующий cloud/folder Бетон42, не создавать дубль.
3. Включить SpeechKit.
4. Создать сервисный аккаунт `beton42-speechkit`.
5. Выдать роли:
   - `ai.speechkit-stt.user`;
   - `ai.speechkit-tts.user`.
6. Создать API key для сервисного аккаунта.
7. Сохранить ключ в:

```text
/Users/a0000/Documents/Бетон-deploy/secrets/speechkit_api_key.txt
```

8. `chmod 600 secrets/speechkit_api_key.txt`.
9. Рекомендуемый голос TTS: `alena`, язык `ru-RU`.
10. Проверить через `voice-robot/test-speechkit.py`.

Без ключа SpeechKit Voximplant-сценарий будет использовать fallback-озвучку.
