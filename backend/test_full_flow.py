"""
test_full_flow.py — проверяет полный цикл работы задеплоенного backend.
Запуск: python test_full_flow.py [URL]
Пример: python test_full_flow.py https://beton-backend-kwa9.onrender.com
"""

import sys
import json
import urllib.request
import urllib.error
import time

BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "https://beton-backend-kwa9.onrender.com"
TIMEOUT = 20

OK = "OK  "
FAIL = "FAIL"
SKIP = "SKIP"


def request(method: str, path: str, body=None, headers=None) -> tuple:
    """Возвращает (status_code, dict_or_none)."""
    url = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    req_headers = {"Content-Type": "application/json", "User-Agent": "test_full_flow/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"_raw": raw[:200]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"_raw": raw[:200]}
    except Exception as e:
        return 0, {"_error": str(e)}


def check(label: str, ok: bool, detail: str = ""):
    icon = OK if ok else FAIL
    line = f"[{icon}] {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    return ok


results = []

print(f"\n{'='*55}")
print(f"  ПОЛНЫЙ ТЕСТ BACKEND")
print(f"  URL: {BASE_URL}")
print(f"{'='*55}\n")

# 1. Ping
status, body = request("GET", "/ping")
results.append(check("GET /ping", status == 200, f"status={status}"))

# 2. Root
status, body = request("GET", "/")
results.append(check("GET /", status == 200, body.get("status", "")))

# 3. Health
status, body = request("GET", "/health")
results.append(check("GET /health", status == 200, body.get("status", "")))

# 4. Public config
status, body = request("GET", "/api/config")
results.append(check("GET /api/config", status == 200, str(body.get("services", ""))))

# 5. Calculator — М200, 5м³, 10км
status, body = request("POST", "/api/calculate", {
    "concrete_grade": "М200",
    "volume": 5.0,
    "distance": 10
})
ok = status == 200 and "calculation" in body
detail = f"total={body.get('calculation', {}).get('total', '?')}" if ok else f"status={status}"
results.append(check("POST /api/calculate", ok, detail))

# 6. Lead creation — тестовый лид
ts = int(time.time())
status, body = request("POST", "/api/leads/create", {
    "name": "Тест Авто",
    "phone": f"+7999{ts % 10000000:07d}",
    "source": "test_full_flow",
    "concrete_grade": "М200",
    "volume": 5.0
})
lead_ok = status == 201 and body.get("status") in ("success", "duplicate")
lead_id = body.get("lead_id") if lead_ok and body.get("status") == "success" else None
detail = f"lead_id={lead_id}" if lead_id else body.get("status", f"status={status}")
results.append(check("POST /api/leads/create", lead_ok, detail))

# 7. Get leads
status, body = request("GET", "/api/leads?limit=5")
ok = status == 200 and "leads" in body
results.append(check("GET /api/leads", ok, f"count={body.get('count', '?')}"))

# 8. Landing data
status, body = request("GET", "/api/landing-data")
results.append(check("GET /api/landing-data", status == 200, "config loaded" if status == 200 else f"status={status}"))

# 9. Prices
status, body = request("GET", "/api/prices")
results.append(check("GET /api/prices", status == 200, "prices loaded" if status == 200 else f"status={status}"))

# Summary
total = len(results)
passed = sum(results)
failed = total - passed

print(f"\n{'='*55}")
print(f"  ИТОГО: {passed}/{total} тестов прошло")
if failed:
    print(f"  ПРОВАЛЕНО: {failed}")
print(f"{'='*55}\n")

sys.exit(0 if failed == 0 else 1)
