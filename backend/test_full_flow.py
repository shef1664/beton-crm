"""
test_full_flow.py — проверка полного цикла работы системы.

Запуск:
    python test_full_flow.py
    python test_full_flow.py https://beton-backend-kwa9.onrender.com
"""

import sys
import json

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

TIMEOUT = 15
DEFAULT_URL = "http://localhost:8000"

CALC_DATA = {"concrete_grade": "М300", "volume": 10, "distance": 15}
LEAD_DATA = {"name": "Тест Авто", "phone": "+79991234567", "concrete_grade": "М300", "volume": 10, "source": "test"}

results = []


def ok(name, detail=""):
    print(f"  [OK  ] {name}" + (f"  ({detail})" if detail else ""))
    results.append((name, True, detail))


def fail(name, detail=""):
    print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))
    results.append((name, False, detail))


def req(method, base, path, data=None):
    url = base + path
    try:
        if method == "GET":
            r = requests.get(url, timeout=TIMEOUT)
        else:
            r = requests.post(url, json=data, timeout=TIMEOUT)
        try:
            body = r.json()
        except Exception:
            body = {}
        return r.status_code, body
    except Exception as e:
        return 0, {"error": str(e)}


def main():
    base = sys.argv[1].strip().rstrip("/") if len(sys.argv) > 1 else DEFAULT_URL

    print()
    print("=" * 55)
    print(f"  ТЕСТ BACKEND: {base}")
    print("=" * 55)
    print()

    # 1. ping
    s, b = req("GET", base, "/ping")
    ok("GET /ping", f"status={s}") if s == 200 else fail("GET /ping", f"status={s}")

    # 2. root
    s, b = req("GET", base, "/")
    ok("GET /", "ok") if s == 200 else fail("GET /", f"status={s}")

    # 3. health
    s, b = req("GET", base, "/health")
    ok("GET /health", "healthy") if s == 200 else fail("GET /health", f"status={s}")

    # 4. config
    s, b = req("GET", base, "/api/config")
    ok("GET /api/config", str({k: b[k] for k in ("amocrm", "telegram") if k in b.get("services", {})})) if s == 200 else fail("GET /api/config", f"status={s}")

    # 5. calculate
    s, b = req("POST", base, "/api/calculate", CALC_DATA)
    total = b.get("total") or b.get("total_price") or 0
    ok("POST /api/calculate", f"total={total}") if s == 200 and total else fail("POST /api/calculate", f"status={s}, body={str(b)[:100]}")

    # 6. create lead
    s, b = req("POST", base, "/api/leads/create", LEAD_DATA)
    lead_ok = s in (200, 201) and b.get("status") in ("success", "duplicate")
    lead_id = b.get("lead_id", "?")
    detail = f"lead_id={lead_id}" if lead_ok and b.get("status") == "success" else b.get("status", f"status={s}")
    ok("POST /api/leads/create", detail) if lead_ok else fail("POST /api/leads/create", f"status={s}, body={str(b)[:100]}")

    # 7. get leads
    s, b = req("GET", base, "/api/leads?limit=5")
    count = b.get("count") or len(b.get("leads", []))
    ok("GET /api/leads", f"count={count}") if s == 200 else fail("GET /api/leads", f"status={s}")

    # 8. landing data
    s, b = req("GET", base, "/api/landing-data")
    ok("GET /api/landing-data", "config loaded") if s == 200 else fail("GET /api/landing-data", f"status={s}")

    # 9. prices
    s, b = req("GET", base, "/api/prices")
    ok("GET /api/prices", "prices loaded") if s == 200 else fail("GET /api/prices", f"status={s}")

    # Итог
    passed = sum(1 for _, p, _ in results if p)
    total_tests = len(results)
    print()
    print("=" * 55)
    print(f"  Итого: {passed}/{total_tests} тестов прошли")
    if passed < total_tests:
        print(f"  Провалено: {total_tests - passed}")
    print("=" * 55)

    sys.exit(0 if passed == total_tests else 1)


if __name__ == "__main__":
    main()
