"""Client bot always exposes restart, ordering, and AI chat actions."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram.ext import ConversationHandler

from bot import main as bot_main


def test_client_menu_contains_repeat_order_and_ai_chat():
    keyboard = bot_main.client_keyboard().inline_keyboard
    actions = {button.callback_data: button.text for row in keyboard for button in row}

    assert actions["order"] == "🧱 Оформить новый заказ"
    assert actions["ai_chat"] == "🤖 Спросить нейросеть"
    assert actions["restart"] == "🔄 Начать заново"
    assert actions["human"] == "💬 Написать менеджеру"
    assert actions["contacts"] == "📞 Позвонить / контакты"


def test_ai_chat_entry_resets_previous_order_and_prompts_for_message():
    message = SimpleNamespace(reply_text=AsyncMock())
    callback = SimpleNamespace(answer=AsyncMock())
    update = SimpleNamespace(
        callback_query=callback,
        effective_user=SimpleNamespace(id=42),
        effective_message=message,
    )
    context = SimpleNamespace(
        user_data={"grade": "М300", "volume": 5, "ai_history": [{"role": "user", "content": "old"}]},
        bot_data={"operators": {42}},
    )

    result = asyncio.run(bot_main.ai_chat_entry(update, context))

    assert result == ConversationHandler.END
    assert context.user_data == {}
    assert 42 not in context.bot_data["operators"]
    callback.answer.assert_awaited_once()
    message.reply_text.assert_awaited_once()
    assert "Напишите вопрос" in message.reply_text.await_args.args[0]


def test_order_entry_clears_previous_order_data():
    message = SimpleNamespace(reply_text=AsyncMock())
    callback = SimpleNamespace(answer=AsyncMock(), message=message)
    update = SimpleNamespace(
        callback_query=callback,
        effective_user=SimpleNamespace(id=42),
    )
    context = SimpleNamespace(
        user_data={"grade": "М200", "volume": 3, "address": "Старый адрес"},
        bot_data={"operators": {42}},
    )

    result = asyncio.run(bot_main.order_entry(update, context))

    assert result == bot_main.VOLUME
    assert context.user_data == {}
    assert 42 not in context.bot_data["operators"]
    callback.answer.assert_awaited_once()
    message.reply_text.assert_awaited_once()


def test_phone_is_accepted_only_from_manual_text():
    assert bot_main._manual_phone("8 923 123-45-67") == "89231234567"
    assert bot_main._manual_phone("номер неизвестен") is None


def test_sales_reply_detects_max_client_target():
    reply_to = SimpleNamespace(
        message_id=10,
        text="Клиент из MAX (max_id 4205271841)",
        caption=None,
    )
    context = SimpleNamespace(bot_data={"relay": {}})

    assert bot_main._client_target_from_reply(context, reply_to) == ("max", 4205271841)
