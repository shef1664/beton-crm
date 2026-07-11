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
    assert actions["ai_chat"] == "📋 Помочь с расчётом"
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
    assert "Чтобы быстрее получить расчёт" in message.reply_text.await_args.args[0]
    assert message.reply_text.await_args.kwargs == {}


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


def test_voice_message_is_transcribed_and_sent_to_normal_chat(monkeypatch):
    tg_file = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(b"ogg")))
    message = SimpleNamespace(
        voice=SimpleNamespace(get_file=AsyncMock(return_value=tg_file)),
        reply_text=AsyncMock(),
    )
    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=42))
    context = SimpleNamespace(user_data={}, bot_data={})
    transcribe = AsyncMock(return_value="нужно пять кубов м300")
    consult_text = AsyncMock()
    monkeypatch.setattr(bot_main, "transcribe_ogg", transcribe)
    monkeypatch.setattr(bot_main, "consult_text", consult_text)

    asyncio.run(bot_main.voice_message(update, context))

    transcribe.assert_awaited_once_with(b"ogg")
    assert message.reply_text.await_args_list[1].args[0] == "🎤 Я услышал: «нужно пять кубов м300»"
    consult_text.assert_awaited_once_with(update, context, "нужно пять кубов м300")


def test_voice_cannot_replace_manual_phone_input():
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(user_data={"manual_phone_required": True})

    asyncio.run(bot_main.voice_message(update, context))

    assert "ввести цифрами вручную" in message.reply_text.await_args.args[0]
