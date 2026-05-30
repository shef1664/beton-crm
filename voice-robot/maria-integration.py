#!/usr/bin/env python3
"""
Интеграция Claude AI + Eleven Labs в Voximplant.
Мария — консультант по бетону, отвечает как живая женщина.
"""

import json
import os
import re
from typing import Optional
import anthropic

# ============================================================================
# КОНФИГ
# ============================================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # Bella
MANAGER_PHONE = "8 903 916 40 40"

# Промпт для Марии (полный)
MARIA_SYSTEM_PROMPT = """Ты — Мария, консультант по продажам бетона в Бетон42.
НИКОГДА не упоминаешь что ты робот. Говоришь как живая женщина 27 лет.

🏭 О КОМПАНИИ (говорить только если спросят):
- Работаем с 2013 года
- Собственные бетоносмесители, бетононасосы, бетонный завод
- 2 завода в городе (Рудничный район и Южный)
- Работаем 24/7

💰 ЦЕНЫ (М³ бетона - Народный бетон):
- М100: 5,775 ₽/м³
- М200: 6,300 ₽/м³
- М300: 7,245 ₽/м³
- М400: 7,770 ₽/м³

⚠️ Цена + доставка рассчитывается автоматически по адресу.
Если клиент спросит точную стоимость → скажи сумму по объёму, потом уточни адрес.

⏰ СРОКИ ДОСТАВКИ:
- Обычно 2-3 часа
- Зависит от занятости (работаем 24/7 по предварительной заявке)
- ЕСЛИ СРОК ОПРЕДЕЛЁННЫЙ → ПЕРЕДАВАТЬ МЕНЕДЖЕРУ

🚚 ВАРИАНТЫ ДОСТАВКИ (миксеры):
2м³, 3м³, 5м³, 6м³, 7м³, 8м³, 9м³, 10м³

🏗️ АВТОБЕТОНОНАСОСЫ:
- 15м, 21м, 36м, 42м, иногда 60м
- Называют "Swing" или "хобот"
- Услуга ТОЛЬКО с нашим бетоном

📍 РАЙОНЫ ДОСТАВКИ:
- Кемерово и +100км от города
- Межгород (дальше 100км) обсуждаем отдельно

🎯 КАК РАБОТАТЬ:
1. Слушаешь что нужно клиенту
2. Отвечаешь кратко (1-2 предложения, как в реальном разговоре)
3. Собираешь информацию: объём (м³), марка (М100-М400), адрес, нужен ли насос, есть ли срок, номер телефона
4. Говоришь как живая женщина: "Ну да", "конечно", "хороший вопрос"
5. Не говоришь "я робот", "я не знаю", "это невозможно"
   - Вместо "не знаю" → "интересный вопрос, дайте узнаю"
   - Вместо "невозможно" → "давайте со менеджером обсудим"

🚨 КОГДА ПЕРЕДАВАТЬ НА МЕНЕДЖЕРА (transfer_needed: true):
1. Клиент просит "менеджера" явно
2. Клиент готов заказать ("хорошо, беру", "как оформить")
3. Клиент просит скидку, рассрочку, спецусловия
4. Клиент говорит срок доставки ("нужно через час", "в пятницу")
5. Объём > 20 кубов (большой заказ)
6. Сумма выходит большая (сложный расчёт)
7. Нужны спецусловия (договор, документы, гарантия)
8. Межгород доставка (дальше 100км)
9. Если что-то непонятно, не ясно (лучше подстраховаться)

🎤 ТОН ГОЛОСА:
- Живая женщина 27 лет
- Дружелюбно, но серьёзно (бизнес-консультант)
- Не спешишь, но и не затягиваешь
- Улыбка в голосе (клиент должен хотеть работать именно с тобой)

ГЛАВНОЕ: Звучи как живая женщина. Собирай информацию мягко. Передавай на менеджера когда не уверена или когда нужно.
"""


class MariaBotHandler:
    """Обработчик диалога с Марией через Claude + Eleven Labs."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.conversation_history = []

    def process_client_message(self, client_text: str) -> dict:
        """
        Обрабатывает сообщение клиента через Claude.
        Возвращает JSON с ответом Марии и информацией о передаче.
        """
        # Добавляем сообщение клиента в историю
        self.conversation_history.append({
            "role": "user",
            "content": client_text
        })

        # Получаем ответ от Claude
        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=MARIA_SYSTEM_PROMPT,
            messages=self.conversation_history
        )

        maria_response = response.content[0].text

        # Добавляем ответ Марии в историю
        self.conversation_history.append({
            "role": "assistant",
            "content": maria_response
        })

        # Анализируем нужна ли передача на менеджера
        transfer_needed = self._detect_transfer_trigger(client_text, maria_response)

        return {
            "text": maria_response,
            "transfer_needed": transfer_needed,
            "transfer_phone": MANAGER_PHONE if transfer_needed else None,
            "conversation_history": self.conversation_history
        }

    def _detect_transfer_trigger(self, client_text: str, maria_response: str) -> bool:
        """
        Детектирует нужна ли передача на менеджера.
        """
        # Комбинируем для анализа
        combined = (client_text + " " + maria_response).lower()

        # Явные триггеры
        transfer_triggers = [
            r"менеджер",
            r"срок",
            r"через\s+час",
            r"сегодня",
            r"срочно",
            r"готов\s+(заказать|купить)",
            r"как\s+оформить",
            r"скидка",
            r"рассрочк",
            r"договор",
            r"спецусловия",
            r"\b[2-9]0\s*куб",  # 20+ кубов
            r"дальше\s+100\s*км",
            r"межгород",
            r"насос",
            r"непонятно",
            r"не ясно",
            r"давайте\s+со\s+менеджером",
        ]

        for pattern in transfer_triggers:
            if re.search(pattern, combined):
                return True

        return False


# ============================================================================
# HTTP HANDLERS (для Voximplant)
# ============================================================================

def handle_incoming_call(client_phone: str, client_text: str) -> dict:
    """
    Обрабатывает входящий звонок от клиента.

    Params:
        client_phone: номер клиента (может быть пустой)
        client_text: текст который распознала STT (от Yandex SpeechKit)

    Returns:
        {
            "response_text": "Ответ Марии",
            "response_audio_url": "URL MP3 с Eleven Labs",
            "transfer_needed": true/false,
            "transfer_phone": "номер менеджера",
            "call_history": [...]
        }
    """
    handler = MariaBotHandler()

    # Получаем ответ от Марии
    result = handler.process_client_message(client_text)

    # Синтезируем аудио через Eleven Labs
    audio_url = synthesize_with_eleven_labs(result["text"])

    return {
        "response_text": result["text"],
        "response_audio_url": audio_url,
        "transfer_needed": result["transfer_needed"],
        "transfer_phone": result["transfer_phone"],
        "call_history": result["conversation_history"]
    }


def synthesize_with_eleven_labs(text: str) -> str:
    """
    Синтезирует текст в MP3 через Eleven Labs (голос Bella).
    Возвращает URL готового аудио.
    """
    import requests

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.55,
            "similarity_boost": 0.75,
            "style": 0.10,
            "use_speaker_boost": True
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        # Сохраняем MP3 и возвращаем URL
        # (в продакшене: загружать в Cloudflare R2 и возвращать публичный URL)
        audio_bytes = response.content
        # TODO: upload to R2 and return public URL

        # Временно: возвращаем base64
        import base64
        return f"data:audio/mpeg;base64,{base64.b64encode(audio_bytes).decode()}"

    except Exception as e:
        print(f"Error synthesizing with Eleven Labs: {e}")
        return None


# ============================================================================
# VOXIMPLANT INTEGRATION
# ============================================================================

async def voximplant_handler(call_data: dict) -> dict:
    """
    Точка входа для Voximplant SIP сценария.
    Вызывается когда приходит входящий звонок.
    """
    client_phone = call_data.get("from", "")
    client_text = call_data.get("recognized_text", "")

    result = handle_incoming_call(client_phone, client_text)

    if result["transfer_needed"]:
        # Передаём звонок менеджеру
        return {
            "action": "transfer",
            "transfer_to": result["transfer_phone"],
            "reason": "manager_required",
            "call_history": result["call_history"],
            "client_phone": client_phone
        }
    else:
        # Отправляем аудио-ответ клиенту
        return {
            "action": "play_audio",
            "audio_url": result["response_audio_url"],
            "text": result["response_text"],
            "call_history": result["call_history"]
        }


if __name__ == "__main__":
    # Тест
    handler = MariaBotHandler()

    test_messages = [
        "Привет, сколько стоит бетон М300?",
        "5 кубов",
        "В Кемерово, Октябрьский район"
    ]

    for msg in test_messages:
        result = handler.process_client_message(msg)
        print(f"Клиент: {msg}")
        print(f"Мария: {result['text']}")
        print(f"Передача? {result['transfer_needed']}\n")
