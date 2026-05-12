"""Тесты для NotionLeadsSync — преобразование лидов в Notion properties."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_notion_not_available_without_token(monkeypatch):
    monkeypatch.setenv("NOTION_API_TOKEN", "")
    # Import after setenv to pick up token
    from services.notion import NotionLeadsSync
    n = NotionLeadsSync()
    assert n.is_available() is False


def test_notion_available_with_token(monkeypatch):
    monkeypatch.setenv("NOTION_API_TOKEN", "secret_xxx")
    from services.notion import NotionLeadsSync
    n = NotionLeadsSync()
    assert n.is_available() is True


def test_build_properties_full():
    from services.notion import NotionLeadsSync
    n = NotionLeadsSync()

    lead = {
        "name": "Иван Петров",
        "phone": "+79135559999",
        "source_platform": "site",
        "concrete_grade": "М300",
        "volume": 6,
        "urgency": "urgent",
        "client_type": "private",
        "calculated_amount": 43200,
        "address": "Кемерово",
        "comment": "тест",
        "utm_source": "yandex",
    }
    props = n._build_properties(lead, amo_lead_id=46350426)

    assert props["Лид"]["title"][0]["text"]["content"].startswith("Иван Петров")
    assert "М300, 6 м³" in props["Лид"]["title"][0]["text"]["content"]
    assert props["Телефон"]["phone_number"] == "+79135559999"
    assert props["Источник"]["select"]["name"] == "Сайт"
    assert props["Марка бетона"]["select"]["name"] == "М300"
    assert props["Объём м³"]["number"] == 6.0
    assert props["Срочность"]["select"]["name"] == "Срочно"
    assert props["Тип клиента"]["select"]["name"] == "Физлицо"
    assert props["Расчётная сумма"]["number"] == 43200.0
    assert props["AmoCRM ID"]["number"] == 46350426


def test_build_properties_minimal():
    from services.notion import NotionLeadsSync
    n = NotionLeadsSync()
    props = n._build_properties({"name": "Аноним", "phone": "+71112223344"}, amo_lead_id=None)
    assert "Лид" in props
    assert "Телефон" in props
    # No optional fields should be present
    assert "Марка бетона" not in props
    assert "AmoCRM ID" not in props


def test_unknown_source_skipped():
    from services.notion import NotionLeadsSync
    n = NotionLeadsSync()
    props = n._build_properties({"name": "X", "phone": "+7", "source_platform": "unknown_src"}, None)
    # Unknown source should NOT be set (no select option matches)
    assert "Источник" not in props
