"""MAX orders can be repeated by the same customer phone."""

from __future__ import annotations

from unittest.mock import AsyncMock


def _lead_payload(source: str, source_platform: str) -> dict:
    return {
        "name": "Юлия",
        "phone": "+79039164040",
        "source": source,
        "source_platform": source_platform,
        "source_channel": "message",
        "concrete_grade": "М300",
        "volume": 5,
        "address": "Кемерово, тест",
    }


def test_regular_source_still_returns_duplicate(app_client, monkeypatch):
    import main as main_module

    monkeypatch.setattr(main_module.duplicate_checker, "check", AsyncMock(return_value=12345))

    response = app_client.post("/api/leads/create", json=_lead_payload("landing", "site"))

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "duplicate"
    assert data["existing_lead_id"] == 12345
    main_module.amocrm.create_lead.assert_not_awaited()


def test_max_source_allows_repeat_order_with_same_phone(app_client, monkeypatch):
    import main as main_module

    monkeypatch.setattr(main_module.duplicate_checker, "check", AsyncMock(return_value=12345))

    response = app_client.post("/api/leads/create", json=_lead_payload("max", "max"))

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["lead_id"] == 999_888
    main_module.amocrm.create_lead.assert_awaited_once()
    main_module.baserow.log_lead.assert_awaited_once()
