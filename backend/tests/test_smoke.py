"""Smoke-tests — проверяют что основные endpoint'ы не падают."""

from __future__ import annotations


def test_health(app_client):
    r = app_client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert "services" in data


def test_ping(app_client):
    r = app_client.get("/ping")
    assert r.status_code == 200
    assert r.json()["pong"] is True


def test_root_serves_landing(app_client):
    r = app_client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text
    # В лендинге должен быть наш заголовок
    assert "Бетон" in body or "бетон" in body or "concrete" in body.lower()


def test_privacy_page(app_client):
    r = app_client.get("/privacy.html")
    assert r.status_code == 200
    assert "Политика" in r.text or "персональн" in r.text


def test_api_config(app_client):
    r = app_client.get("/api/config")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "services" in data


def test_create_lead_basic(app_client):
    payload = {
        "name": "Тест Иванов",
        "phone": "+79135551234",
        "concrete_grade": "М300",
        "volume": 5,
        "address": "Кемерово, тест",
        "source_platform": "site",
    }
    r = app_client.post("/api/leads/create", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "success"
    assert data["lead_id"] == 999_888  # из mock'а


def test_create_lead_validation_missing_required(app_client):
    r = app_client.post("/api/leads/create", json={"name": "X"})
    # Pydantic должен вернуть 422
    assert r.status_code == 422


def test_calculator_basic(app_client):
    r = app_client.post(
        "/api/calculate",
        json={"concrete_grade": "М300", "volume": 6, "distance": 0},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    calc = data["calculation"]
    # М300 = 7200₽/м³ × 6м³ = 43200; delivery_cost зависит от distance/billable volume
    assert calc["beton_cost"] == 43200.0
    assert calc["concrete_grade"] == "М300"
    # Должна быть total (либо total, либо total_cost)
    total = calc.get("total") or calc.get("total_cost") or (calc["beton_cost"] + calc.get("delivery_cost", 0))
    assert total > 40_000


def test_crm_schema(app_client):
    r = app_client.get("/api/crm/schema")
    assert r.status_code == 200
    data = r.json()
    assert "pipeline_statuses" in data
    assert "supported_source_platforms" in data
