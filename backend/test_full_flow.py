"""
Simple smoke test for the concrete sales backend.

Run:
    python test_full_flow.py
    python test_full_flow.py https://beton-backend-kwa9.onrender.com
"""

import sys
import os

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

TIMEOUT = 15
DEFAULT_URL = "http://localhost:8000"
TELEPHONY_WEBHOOK_SECRET = os.getenv("TELEPHONY_WEBHOOK_SECRET", "").strip()
TELEPHONY_AUTH_HEADER = os.getenv("TELEPHONY_AUTH_HEADER", "X-Telephony-Secret").strip() or "X-Telephony-Secret"

CALC_DATA = {"concrete_grade": "М300", "volume": 1.5, "distance": 7}
LEAD_DATA = {
    "name": "Test Auto",
    "phone": "+79991234567",
    "concrete_grade": "М300",
    "volume": 10,
    "source": "test",
}
EXTERNAL_LEAD_DATA = {
    "lead_data": {
        "name": "Test Source",
        "phone": "+79990001122",
        "source_platform": "phone",
        "source_channel": "call",
        "comment": "smoke external intake",
    },
    "integration": "telephony",
    "event_type": "call",
    "raw_payload": {"test": True},
}
RAW_AVITO_WEBHOOK = {
    "buyer": {"name": "Avito Buyer", "phone": "+79990002233"},
    "item": {"id": "av-1001", "title": "Бетон М300"},
    "account_id": "avito-main",
    "campaign": "weekly-listing-batch",
    "message": "Нужен бетон на завтра",
}
RAW_YANDEX_WEBHOOK = {
    "contact": {"name": "Yandex Lead", "phone": "+79990002244"},
    "business": {"id": "yandex-card-1", "name": "Бетон Экспресс", "address": "Новосибирск"},
    "channel": "call",
    "message": "Нужна доставка бетона",
}
AUTOMATION_PREVIEW_DATA = {
    "name": "Preview Lead",
    "phone": "+79995556677",
    "source_platform": "yandex_maps",
    "source_channel": "call",
    "calculated_amount": 92000,
    "urgency": "urgent",
}
VOICE_START_DATA = {
    "phone": "+79990003355",
    "provider": "telephony",
    "direction": "inbound",
    "metadata": {"line_name": "Основная линия", "campaign": "voice-test"},
}

results = []


def ok(name, detail=""):
    print(f"  [OK  ] {name}" + (f"  ({detail})" if detail else ""))
    results.append((name, True, detail))


def fail(name, detail=""):
    print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))
    results.append((name, False, detail))


def req(method, base, path, data=None, headers=None):
    url = base + path
    try:
        if method == "GET":
            response = requests.get(url, timeout=TIMEOUT, headers=headers)
        else:
            response = requests.post(url, json=data, timeout=TIMEOUT, headers=headers)
        try:
            body = response.json()
        except Exception:
            body = {}
        return response.status_code, body
    except Exception as exc:
        return 0, {"error": str(exc)}


def main():
    base = sys.argv[1].strip().rstrip("/") if len(sys.argv) > 1 else DEFAULT_URL

    print()
    print("=" * 55)
    print(f"  TEST BACKEND: {base}")
    print("=" * 55)
    print()

    s, _ = req("GET", base, "/ping")
    ok("GET /ping", f"status={s}") if s == 200 else fail("GET /ping", f"status={s}")

    s, _ = req("GET", base, "/")
    ok("GET /", "ok") if s == 200 else fail("GET /", f"status={s}")

    s, _ = req("GET", base, "/health")
    ok("GET /health", "healthy") if s == 200 else fail("GET /health", f"status={s}")

    s, b = req("GET", base, "/status")
    telephony_ok = s == 200 and isinstance(b.get("telephony"), dict)
    detail = b.get("telephony", {}).get("provider", f"status={s}")
    ok("GET /status", detail) if telephony_ok else fail("GET /status", f"status={s}, body={str(b)[:100]}")

    s, b = req("GET", base, "/api/config")
    if s == 200:
        services = b.get("services", {})
        ok("GET /api/config", str(services))
    else:
        fail("GET /api/config", f"status={s}")

    s, b = req("GET", base, "/api/telephony/status")
    telephony_status_ok = s == 200 and isinstance(b.get("telephony"), dict)
    detail = b.get("telephony", {}).get("provider", f"status={s}")
    ok("GET /api/telephony/status", detail) if telephony_status_ok else fail(
        "GET /api/telephony/status", f"status={s}, body={str(b)[:100]}"
    )

    s, b = req("POST", base, "/api/calculate", CALC_DATA)
    total = b.get("total") or b.get("total_price") or b.get("calculation", {}).get("total") or 0
    ok("POST /api/calculate", f"total={total}") if s == 200 and total else fail(
        "POST /api/calculate", f"status={s}, body={str(b)[:100]}"
    )

    s, b = req("POST", base, "/api/voice/calls/start", VOICE_START_DATA)
    call_id = b.get("call", {}).get("call_id")
    ok("POST /api/voice/calls/start", f"call_id={call_id}") if s == 200 and call_id else fail(
        "POST /api/voice/calls/start", f"status={s}, body={str(b)[:140]}"
    )

    if call_id:
        sales_turns = [
            "М300",
            "12 кубов",
            "Новосибирск, улица Кирова 10",
            "18 километров",
            "завтра утром",
            "безнал",
            "срочно, желательно завтра",
            "Иван",
        ]
        last_body = {}
        sales_flow_ok = True
        for turn_text in sales_turns:
            s, last_body = req("POST", base, f"/api/voice/calls/{call_id}/turn", {"text": turn_text})
            if s != 200 or not last_body.get("assistant", {}).get("text"):
                sales_flow_ok = False
                break
        ok("POST /api/voice/calls/{call_id}/turn", "sales flow active") if sales_flow_ok else fail(
            "POST /api/voice/calls/{call_id}/turn", f"status={s}, body={str(last_body)[:160]}"
        )
        quote_ok = sales_flow_ok and last_body.get("action") == "ready_for_quote"
        ok("VOICE quote generation", last_body.get("action", "none")) if quote_ok else fail(
            "VOICE quote generation", f"status={s}, body={str(last_body)[:160]}"
        )
        if quote_ok:
            s, objection_body = req("POST", base, f"/api/voice/calls/{call_id}/turn", {"text": "дорого, нужен менеджер"})
            objection_ok = s == 200 and objection_body.get("action") == "handoff"
            ok("VOICE objection handling", objection_body.get("action", f"status={s}")) if objection_ok else fail(
                "VOICE objection handling", f"status={s}, body={str(objection_body)[:160]}"
            )

    s, b = req("POST", base, "/api/leads/create", LEAD_DATA)
    lead_ok = s in (200, 201) and b.get("status") in ("success", "duplicate")
    detail = f"lead_id={b.get('lead_id', 0)}" if b.get("status") == "success" else b.get("status", f"status={s}")
    ok("POST /api/leads/create", detail) if lead_ok else fail(
        "POST /api/leads/create", f"status={s}, body={str(b)[:100]}"
    )

    s, b = req("GET", base, "/api/leads?limit=5")
    count = b.get("count") or len(b.get("leads", []))
    ok("GET /api/leads", f"count={count}") if s == 200 else fail("GET /api/leads", f"status={s}")

    s, _ = req("GET", base, "/api/landing-data")
    ok("GET /api/landing-data", "config loaded") if s == 200 else fail("GET /api/landing-data", f"status={s}")

    s, _ = req("GET", base, "/api/prices")
    ok("GET /api/prices", "prices loaded") if s == 200 else fail("GET /api/prices", f"status={s}")

    s, b = req("GET", base, "/api/crm/schema")
    schema_ok = s == 200 and bool(b.get("pipeline_statuses")) and bool(b.get("lead_fields"))
    detail = f"fields={len(b.get('lead_fields', []))}" if schema_ok else f"status={s}, body={str(b)[:100]}"
    ok("GET /api/crm/schema", detail) if schema_ok else fail("GET /api/crm/schema", detail)

    s, b = req("GET", base, "/api/integrations/schema")
    integrations_ok = s == 200 and isinstance(b.get("integrations"), dict) and bool(b.get("generic_webhook"))
    detail = f"integrations={len(b.get('integrations', {}))}" if integrations_ok else f"status={s}, body={str(b)[:100]}"
    ok("GET /api/integrations/schema", detail) if integrations_ok else fail("GET /api/integrations/schema", detail)

    s, b = req("POST", base, "/api/integrations/normalize-preview/avito", RAW_AVITO_WEBHOOK)
    normalize_ok = s == 200 and b.get("status") == "success" and isinstance(b.get("normalized_lead"), dict)
    detail = b.get("normalized_lead", {}).get("source_platform", f"status={s}")
    ok("POST /api/integrations/normalize-preview/{integration}", detail) if normalize_ok else fail(
        "POST /api/integrations/normalize-preview/{integration}", f"status={s}, body={str(b)[:100]}"
    )

    s, b = req("GET", base, "/api/sales/dashboard")
    dashboard = b.get("dashboard", {})
    dashboard_ok = (
        s == 200
        and isinstance(dashboard, dict)
        and "overdue_contacts" in dashboard
        and "due_soon_contacts" in dashboard
    )
    detail = f"total={dashboard.get('total', 0)}" if dashboard_ok else f"status={s}, body={str(b)[:100]}"
    ok("GET /api/sales/dashboard", detail) if dashboard_ok else fail("GET /api/sales/dashboard", detail)

    s, b = req("GET", base, "/api/sales/report")
    report_ok = s == 200 and isinstance(b.get("dashboard"), dict) and isinstance(b.get("recent_external_intake"), list)
    detail = f"duplicates={len(b.get('recent_duplicates', []))}" if report_ok else f"status={s}, body={str(b)[:100]}"
    ok("GET /api/sales/report", detail) if report_ok else fail("GET /api/sales/report", detail)

    s, b = req("GET", base, "/api/sales/workqueue")
    workqueue_ok = s == 200 and isinstance(b.get("items"), list) and isinstance(b.get("count"), int)
    detail = f"count={b.get('count', 0)}" if workqueue_ok else f"status={s}, body={str(b)[:100]}"
    ok("GET /api/sales/workqueue", detail) if workqueue_ok else fail("GET /api/sales/workqueue", detail)

    first_local_id = b.get("items", [{}])[0].get("id") if workqueue_ok and b.get("items") else None
    if first_local_id:
        s, b = req(
            "POST",
            base,
            f"/api/sales/workqueue/{first_local_id}/claim",
            {"assigned_manager": "sales-team", "next_action": "Позвонить в ближайшие 5 минут"},
        )
        claim_ok = s == 200 and b.get("status") == "success" and b.get("item", {}).get("assigned_manager") == "sales-team"
        detail = b.get("item", {}).get("assigned_manager", f"status={s}")
        ok("POST /api/sales/workqueue/{id}/claim", detail) if claim_ok else fail(
            "POST /api/sales/workqueue/{id}/claim", f"status={s}, body={str(b)[:100]}"
        )

        s, b = req(
            "POST",
            base,
            f"/api/sales/workqueue/{first_local_id}/contacted",
            {"lead_status": "data_collection", "next_action": "Ожидаем параметры объекта", "comment": "smoke contact"},
        )
        contacted_ok = s == 200 and b.get("status") == "success" and b.get("item", {}).get("lead_status") == "data_collection"
        detail = b.get("item", {}).get("lead_status", f"status={s}")
        ok("POST /api/sales/workqueue/{id}/contacted", detail) if contacted_ok else fail(
            "POST /api/sales/workqueue/{id}/contacted", f"status={s}, body={str(b)[:100]}"
        )

    s, b = req("POST", base, "/api/sales/automation-preview", AUTOMATION_PREVIEW_DATA)
    automation = b.get("automation", {})
    automation_ok = (
        s == 200
        and isinstance(automation, dict)
        and bool(automation.get("assigned_manager"))
        and bool(automation.get("sales_playbook"))
        and bool(automation.get("sla_minutes"))
    )
    detail = f"{automation.get('sales_priority', 'unknown')}/{automation.get('sales_playbook', 'n/a')}"
    ok("POST /api/sales/automation-preview", detail) if automation_ok else fail(
        "POST /api/sales/automation-preview", f"status={s}, body={str(b)[:100]}"
    )

    s, b = req("POST", base, "/api/intake/external", EXTERNAL_LEAD_DATA)
    external_ok = s in (200, 201) and b.get("status") in ("success", "duplicate")
    detail = b.get("status", f"status={s}")
    ok("POST /api/intake/external", detail) if external_ok else fail(
        "POST /api/intake/external", f"status={s}, body={str(b)[:100]}"
    )

    s, b = req("POST", base, "/webhooks/external/telephony", EXTERNAL_LEAD_DATA)
    webhook_ok = s in (200, 201) and b.get("status") in ("success", "duplicate")
    detail = b.get("status", f"status={s}")
    ok("POST /webhooks/external/{integration}", detail) if webhook_ok else fail(
        "POST /webhooks/external/{integration}", f"status={s}, body={str(b)[:100]}"
    )

    telephony_headers = {TELEPHONY_AUTH_HEADER: TELEPHONY_WEBHOOK_SECRET} if TELEPHONY_WEBHOOK_SECRET else None
    s, b = req(
        "POST",
        base,
        "/webhooks/telephony",
        {
            "name": "Telephony Lead",
            "phone": "+79991112233",
            "event_type": "call_finished",
            "line_name": "Main line",
            "campaign": "telephony-smoke",
        },
        headers=telephony_headers,
    )
    telephony_webhook_ok = s in (200, 201) and b.get("status") in ("success", "duplicate", "ignored")
    detail = b.get("status", f"status={s}")
    ok("POST /webhooks/telephony", detail) if telephony_webhook_ok else fail(
        "POST /webhooks/telephony", f"status={s}, body={str(b)[:100]}"
    )

    s, b = req("POST", base, "/webhooks/external/avito", RAW_AVITO_WEBHOOK)
    raw_avito_ok = s in (200, 201) and b.get("status") in ("success", "duplicate")
    detail = b.get("status", f"status={s}")
    ok("POST /webhooks/external/avito", detail) if raw_avito_ok else fail(
        "POST /webhooks/external/avito", f"status={s}, body={str(b)[:100]}"
    )

    s, b = req("POST", base, "/webhooks/external/yandex_maps", RAW_YANDEX_WEBHOOK)
    raw_yandex_ok = s in (200, 201) and b.get("status") in ("success", "duplicate")
    detail = b.get("status", f"status={s}")
    ok("POST /webhooks/external/yandex_maps", detail) if raw_yandex_ok else fail(
        "POST /webhooks/external/yandex_maps", f"status={s}, body={str(b)[:100]}"
    )

    passed = sum(1 for _, success, _ in results if success)
    total_tests = len(results)
    print()
    print("=" * 55)
    print(f"  Total: {passed}/{total_tests}")
    if passed < total_tests:
        print(f"  Failed: {total_tests - passed}")
    print("=" * 55)

    sys.exit(0 if passed == total_tests else 1)


if __name__ == "__main__":
    main()
