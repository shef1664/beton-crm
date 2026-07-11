"""MAX bot restart, contact, and manual-phone behavior."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from bot_max import main as max_bot


def test_max_main_menu_exposes_all_client_actions():
    actions = {button["payload"]: button["text"] for row in max_bot._kb_main() for button in row}

    assert actions == {
        "restart": "🔄 Начать заново",
        "order": "🧱 Оформить новый заказ",
        "ai_chat": "📋 Помочь с расчётом",
        "human": "💬 Написать менеджеру",
        "contacts": "📞 Позвонить / контакты",
    }


def test_max_phone_is_accepted_only_from_manual_text():
    assert max_bot._manual_phone("8 923 123-45-67") == "89231234567"
    assert max_bot._manual_phone("нет телефона") is None


def test_max_ai_entry_shows_one_hint_without_repeating_menu(monkeypatch):
    send = AsyncMock()
    monkeypatch.setattr(max_bot, "_max_send", send)
    client = object()

    asyncio.run(max_bot._ai_entry(client, 77))

    send.assert_awaited_once()
    assert "Чтобы быстрее получить расчёт" in send.await_args.args[2]
    assert len(send.await_args.args) == 3


def test_max_start_command_wins_while_bot_waits_for_phone(monkeypatch):
    uid = 101
    max_bot._sessions[uid] = {"state": max_bot.PHONE, "ai_history": []}
    greet = AsyncMock()
    create_lead = AsyncMock()
    monkeypatch.setattr(max_bot, "_greet", greet)
    monkeypatch.setattr(max_bot, "_create_lead", create_lead)
    client = object()

    update = {
        "message": {
            "sender": {"user_id": uid, "name": "Клиент"},
            "body": {"text": "/start"},
        }
    }
    asyncio.run(max_bot._handle_message(client, update))

    greet.assert_awaited_once_with(client, uid)
    create_lead.assert_not_awaited()


def test_max_contact_attachment_is_rejected_in_phone_step(monkeypatch):
    uid = 102
    max_bot._sessions[uid] = {"state": max_bot.PHONE, "ai_history": []}
    send = AsyncMock()
    create_lead = AsyncMock()
    monkeypatch.setattr(max_bot, "_max_send", send)
    monkeypatch.setattr(max_bot, "_create_lead", create_lead)

    update = {
        "message": {
            "sender": {"user_id": uid, "name": "Клиент"},
            "body": {
                "text": "",
                "attachments": [
                    {"type": "contact", "payload": {"phone": "+79030000000"}}
                ],
            },
        }
    }
    asyncio.run(max_bot._handle_message(object(), update))

    create_lead.assert_not_awaited()
    assert "Контакт не принимаю" in send.await_args.args[2]


def test_ai_script_hands_unknown_questions_to_manager():
    from services import ai_agent

    assert "СРАЗУ вызови call_human" in ai_agent.SYSTEM_PROMPT
    assert "Не пытайся угадывать" in ai_agent.SYSTEM_PROMPT
    assert ai_agent._reply_requires_handoff("Извините, я по этой теме не могу помочь")
    assert not ai_agent._reply_requires_handoff("Для фундамента обычно подходит М300")


def test_max_uses_platform_voice_transcription(monkeypatch):
    uid = 103
    max_bot._sessions[uid] = {"state": max_bot.IDLE, "ai_history": []}
    send = AsyncMock()
    consult = AsyncMock()
    stt = AsyncMock()
    monkeypatch.setattr(max_bot, "_max_send", send)
    monkeypatch.setattr(max_bot, "_consult", consult)
    monkeypatch.setattr(max_bot, "transcribe_ogg", stt)
    client = object()
    update = {
        "message": {
            "sender": {"user_id": uid, "name": "Клиент"},
            "body": {"attachments": [{
                "type": "audio",
                "transcription": "нужно шесть кубов м300",
                "payload": {},
            }]},
        }
    }

    asyncio.run(max_bot._handle_message(client, update))

    stt.assert_not_awaited()
    assert send.await_args_list[1].args[2] == "🎤 Я услышал: «нужно шесть кубов м300»"
    consult.assert_awaited_once_with(client, uid, "нужно шесть кубов м300")


def test_max_voice_cannot_replace_manual_phone_input(monkeypatch):
    uid = 104
    max_bot._sessions[uid] = {"state": max_bot.PHONE, "ai_history": []}
    send = AsyncMock()
    monkeypatch.setattr(max_bot, "_max_send", send)
    update = {
        "message": {
            "sender": {"user_id": uid, "name": "Клиент"},
            "body": {"attachments": [{"type": "audio", "transcription": "89030000000"}]},
        }
    }

    asyncio.run(max_bot._handle_message(object(), update))

    assert "ввести цифрами вручную" in send.await_args.args[2]
