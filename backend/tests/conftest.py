"""Pytest fixtures — изолируем тесты от внешних сервисов."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make backend/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force test-friendly env BEFORE importing main
os.environ.setdefault("AMOCRM_DOMAIN", "test.amocrm.ru")
os.environ.setdefault("AMOCRM_ACCESS_TOKEN", "")  # disabled — fallback path
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")
os.environ.setdefault("BASEROW_TOKEN", "")
os.environ.setdefault("NOTION_API_TOKEN", "")
os.environ.setdefault("YANDEX_METRIKA_ID", "")
os.environ.setdefault("SQLITE_DB_PATH", "/tmp/beton-tests.db")


@pytest.fixture
def app_client(monkeypatch):
    """Returns TestClient with all external services mocked to be no-ops."""
    from fastapi.testclient import TestClient

    import main as main_module

    # Patch AmoCRM — pretend it's available but returns dummy lead_id
    monkeypatch.setattr(main_module.amocrm, "is_available", lambda: True, raising=False)
    monkeypatch.setattr(main_module.amocrm, "create_lead", AsyncMock(return_value=999_888))
    monkeypatch.setattr(main_module.amocrm, "update_lead", AsyncMock(return_value={"id": 999_888}))
    monkeypatch.setattr(
        main_module.duplicate_checker,
        "check",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(main_module.baserow, "log_lead", AsyncMock())
    monkeypatch.setattr(main_module.baserow, "log_error", AsyncMock())
    monkeypatch.setattr(main_module.notifier, "notify_new_lead", AsyncMock())

    return TestClient(main_module.app)
