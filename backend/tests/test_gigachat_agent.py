import asyncio

from services import ai_agent


def test_extract_json_object_tolerates_code_fence():
    assert ai_agent._extract_json_object('```json\n{"reply":"Здравствуйте","tool":null}\n```') == {
        "reply": "Здравствуйте", "tool": None
    }


def test_gigachat_agent_runs_local_tool(monkeypatch):
    replies = iter([
        '{"reply":null,"tool":{"name":"estimate_price","arguments":{"grade":"М300","volume":5}}}',
        '{"reply":"Пять кубов М300 стоят 35 000 рублей без доставки. Куда привезти?","tool":null}',
    ])
    monkeypatch.setenv("GIGACHAT_TOKEN", "test-credentials")
    monkeypatch.setattr(ai_agent, "_gigachat_complete", lambda *args: next(replies))

    result = asyncio.run(ai_agent._chat_gigachat([{"role": "user", "content": "Сколько стоит 5 кубов М300?"}]))

    assert result["action"] is None
    assert "35 000" in result["reply"]
