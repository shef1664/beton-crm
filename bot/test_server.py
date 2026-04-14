"""Минимальный тестовый сервер для Railway"""
import os
from aiohttp import web

async def health(request):
    return web.json_response({"status": "alive", "port": os.getenv("PORT", "8080")})

async def api(request):
    body = await request.json()
    return web.json_response({"status": "ok", "action": body.get("action", "")})

app = web.Application()
app.router.add_get("/health", health)
app.router.add_post("/api", api)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    print(f"Starting on port {port}")
    web.run_app(app, host="0.0.0.0", port=port)
