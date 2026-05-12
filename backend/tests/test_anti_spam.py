"""Tests for honeypot + rate limiter."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time


def test_honeypot_detects_filled_field():
    from services.anti_spam import is_honeypot_triggered, HONEYPOT_FIELD
    assert is_honeypot_triggered({HONEYPOT_FIELD: "https://spam.example"}) is True


def test_honeypot_passes_empty():
    from services.anti_spam import is_honeypot_triggered, HONEYPOT_FIELD
    assert is_honeypot_triggered({}) is False
    assert is_honeypot_triggered({HONEYPOT_FIELD: ""}) is False
    assert is_honeypot_triggered({HONEYPOT_FIELD: None}) is False


def test_rate_limiter_under_limit():
    from services.anti_spam import RateLimiter
    rl = RateLimiter(max_requests=3, window_seconds=10)
    assert rl.allow("1.2.3.4") is True
    assert rl.allow("1.2.3.4") is True
    assert rl.allow("1.2.3.4") is True


def test_rate_limiter_blocks_excess():
    from services.anti_spam import RateLimiter
    rl = RateLimiter(max_requests=2, window_seconds=10)
    assert rl.allow("9.9.9.9") is True
    assert rl.allow("9.9.9.9") is True
    assert rl.allow("9.9.9.9") is False  # 3rd request blocked


def test_rate_limiter_per_ip_isolated():
    from services.anti_spam import RateLimiter
    rl = RateLimiter(max_requests=1, window_seconds=10)
    assert rl.allow("1.1.1.1") is True
    assert rl.allow("2.2.2.2") is True
    assert rl.allow("1.1.1.1") is False
    assert rl.allow("2.2.2.2") is False


def test_honeypot_in_lead_endpoint_returns_fake_success(app_client):
    """Bot fills honeypot — we pretend success but don't create real lead."""
    payload = {
        "name": "Bot",
        "phone": "+71112223344",
        "company_website": "https://i-am-a-bot.example",
    }
    r = app_client.post("/api/leads/create", json=payload)
    # Returns 200 (default for non-201) with fake success
    assert r.status_code in (200, 201)
    data = r.json()
    assert data["status"] == "success"
    assert data["lead_id"] == 0
    assert data["amo_lead_created"] is False
