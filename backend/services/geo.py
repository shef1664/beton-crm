"""
Бесплатное определение расстояния «адрес клиента → завод».

Цель — «примерно понимать» километраж и стоимость доставки.

Геокодинг (адрес → координаты) — переключаемый провайдер через env GEO_PROVIDER:
  - "nominatim" (по умолчанию) — OpenStreetMap, БЕЗ ключа, бесплатно
  - "dadata"                    — DaData Suggestions API, нужен DADATA_TOKEN
                                  (10 000 запросов/день бесплатно, точнее по РФ)
Если задан DADATA_TOKEN, провайдер автоматически становится "dadata",
а Nominatim остаётся фолбэком при сбое.

Маршрут (координаты → км по дорогам):
  - OSRM (public demo server)  — БЕЗ ключа, бесплатно
  - Haversine (формула)        — офлайн-фолбэк ×1.35, если OSRM недоступен

Любой шаг может «отвалиться» — тогда мягко деградируем к следующему.

Ограничения бесплатных сервисов:
  - Nominatim: не чаще ~1 запроса/сек, обязателен User-Agent (см. usage policy).
  - OSRM demo: без гарантий доступности, для production лучше поднять свой.
  - DaData Suggestions: 10k/день, коммерческое использование по лицензии DaData.
Всё это оценка «примерно», а не юридически точный расчёт доставки.
"""

import json
import logging
import math
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# --- Справочник зон доставки (районы/нас.пункты → фикс-цена) -----------------
_ZONES_PATH = Path(__file__).resolve().parent.parent / "data" / "delivery_zones.json"
MIXER_VOLUME = float(os.getenv("MIXER_VOLUME", "7"))
# Городская ставка по умолчанию для адресов Кемерово без явной зоны (₽ за подачу).
CITY_DELIVERY_MIN = float(os.getenv("CITY_DELIVERY_MIN", "6000"))
CITY_DELIVERY_MAX = float(os.getenv("CITY_DELIVERY_MAX", "7000"))


def _load_zones() -> list:
    """Плоский список зон (районы + нас.пункты) с ценами; отсортирован по длине алиаса."""
    try:
        cfg = json.loads(_ZONES_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("delivery_zones.json недоступен: %s", exc)
        return []
    zones = list(cfg.get("districts") or []) + list(cfg.get("settlements") or [])
    entries = []
    for z in zones:
        for alias in z.get("aliases") or []:
            entries.append((alias.lower(), z))
    # длинные алиасы раньше — «лесная поляна» до generic, точные нас.пункты приоритетнее
    entries.sort(key=lambda e: len(e[0]), reverse=True)
    return entries


_ZONE_INDEX = _load_zones()


def match_zone(address: str) -> dict | None:
    """
    Определяет зону доставки по тексту адреса.
    Возвращает {"name", "km", "price_min", "price_max"} или синтетическую
    «Кемерово (город)» с городской ставкой, если адрес в Кемерово без явной зоны.
    None — если адрес не распознан как зона (дальний/непонятный → на менеджера).
    """
    if not address:
        return None
    low = address.lower()
    for alias, z in _ZONE_INDEX:
        if alias in low:
            price = z.get("price_delivery") or {}
            return {
                "name": z.get("name"),
                "km": z.get("km"),
                "price_min": price.get("min"),
                "price_max": price.get("max"),
            }
    # адрес по Кемерово без явной зоны → городская ставка
    if "кемеров" in low:
        return {"name": "Кемерово (город)", "km": None,
                "price_min": CITY_DELIVERY_MIN, "price_max": CITY_DELIVERY_MAX}
    return None

# --- Точка отгрузки (завод). Переопределяется через env. --------------------
# По умолчанию — Кемерово. Уточни координаты своего РБУ в env PLANT_LAT/PLANT_LON.
PLANT_LAT: float = float(os.getenv("PLANT_LAT", "55.3550"))
PLANT_LON: float = float(os.getenv("PLANT_LON", "86.0870"))
PLANT_ADDRESS: str = os.getenv("PLANT_ADDRESS", "Кемерово")

# Максимальное плечо доставки, км. Дальше — «доставка под вопрос, нужен расчёт».
MAX_DELIVERY_KM: float = float(os.getenv("MAX_DELIVERY_KM", "60"))

# Регион для смещения гео­кодинга (чтобы «Ленина 90» находилось в Кемерово,
# а не в другом городе). Bounding box Кемеровской области, примерно.
_VIEWBOX = os.getenv("GEO_VIEWBOX", "84.5,56.5,88.5,53.0")  # left,top,right,bottom
_USER_AGENT = os.getenv("GEO_USER_AGENT", "beton42-crm/1.0 (shef1664@gmail.com)")
_NOMINATIM = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
_OSRM = os.getenv("OSRM_URL", "https://router.project-osrm.org/route/v1/driving")

# DaData — точный геокодинг по адресам РФ. Нужен только токен (Suggestions API).
_DADATA_TOKEN = os.getenv("DADATA_TOKEN", "").strip()
_DADATA_URL = os.getenv(
    "DADATA_URL",
    "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address",
)
# Провайдер геокодинга: dadata, если задан токен, иначе nominatim. Override через env.
GEO_PROVIDER = os.getenv("GEO_PROVIDER", "dadata" if _DADATA_TOKEN else "nominatim").lower()

_TIMEOUT = httpx.Timeout(12.0)
# Поправочный коэффициент «прямая → дорога», когда OSRM недоступен.
_ROAD_FACTOR = 1.35


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние по прямой между двумя точками, км."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


async def geocode_dadata(address: str) -> dict | None:
    """
    Адрес → координаты через DaData Suggestions API. Нужен DADATA_TOKEN.
    10 000 запросов/день бесплатно, лучшая точность по адресам РФ.
    Возвращает {"lat", "lon", "display_name"} или None.
    """
    if not _DADATA_TOKEN:
        return None
    query = address.strip()
    if not query:
        return None
    if "кемеров" not in query.lower():
        query = f"Кемерово, {query}"
    headers = {
        "Authorization": f"Token {_DADATA_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(_DADATA_URL, headers=headers, json={"query": query, "count": 1})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("DaData geocode failed for %r: %s", address, exc)
        return None
    suggestions = data.get("suggestions") or []
    if not suggestions:
        return None
    top = suggestions[0]
    d = top.get("data") or {}
    if not d.get("geo_lat") or not d.get("geo_lon"):
        return None
    return {
        "lat": float(d["geo_lat"]),
        "lon": float(d["geo_lon"]),
        "display_name": top.get("value", query),
    }


async def geocode_nominatim(address: str) -> dict | None:
    """
    Адрес → координаты через Nominatim (OSM). Бесплатно, без ключа.
    Возвращает {"lat", "lon", "display_name"} или None, если не найдено.
    """
    query = address.strip()
    if not query:
        return None
    # Если в адресе нет города — добавим Кемерово, чтобы не искать по всей стране.
    if "кемеров" not in query.lower():
        query = f"{query}, Кемерово"
    params = {
        "q": query,
        "format": "json",
        "limit": "1",
        "countrycodes": "ru",
        "viewbox": _VIEWBOX,
        "bounded": "0",
        "accept-language": "ru",
    }
    headers = {"User-Agent": _USER_AGENT}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_NOMINATIM, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # сеть/парсинг/лимит — не роняем поток
        logger.warning("Nominatim geocode failed for %r: %s", address, exc)
        return None
    if not data:
        return None
    top = data[0]
    return {
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "display_name": top.get("display_name", query),
    }


async def geocode(address: str) -> dict | None:
    """
    Адрес → координаты. Выбирает провайдер по GEO_PROVIDER, с фолбэком.
    dadata (если задан токен) → nominatim; или наоборот при обратной настройке.
    """
    if GEO_PROVIDER == "dadata":
        result = await geocode_dadata(address)
        if result:
            return result
        return await geocode_nominatim(address)  # мягкий фолбэк
    result = await geocode_nominatim(address)
    if result:
        return result
    return await geocode_dadata(address)  # фолбэк, если токен всё же есть


async def road_distance_km(lat: float, lon: float) -> tuple[float, str]:
    """
    Расстояние по дорогам от завода до точки через OSRM. Бесплатно, без ключа.
    Возвращает (км, метод). Метод: "osrm" | "haversine" (фолбэк).
    """
    straight = haversine_km(PLANT_LAT, PLANT_LON, lat, lon)
    # OSRM формат координат: lon,lat;lon,lat
    url = f"{_OSRM}/{PLANT_LON},{PLANT_LAT};{lon},{lat}"
    params = {"overview": "false"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        if data.get("code") == "Ok" and data.get("routes"):
            meters = data["routes"][0]["distance"]
            return round(meters / 1000.0, 1), "osrm"
    except Exception as exc:
        logger.warning("OSRM route failed (%.4f,%.4f): %s", lat, lon, exc)
    # Фолбэк — прямая с поправкой на дороги.
    return round(straight * _ROAD_FACTOR, 1), "haversine"


async def estimate_distance(address: str) -> dict:
    """
    Главная точка входа: адрес клиента → оценка расстояния и возможности доставки.

    Возвращает:
      {
        "found": bool,               # удалось ли распознать адрес
        "distance_km": float | None, # плечо от завода
        "method": "osrm"|"haversine"|None,
        "deliverable": bool,         # в пределах MAX_DELIVERY_KM
        "coords": {"lat","lon"} | None,
        "matched_address": str | None,
        "plant_address": str,
      }
    """
    geo = await geocode(address)
    if not geo:
        return {
            "found": False,
            "distance_km": None,
            "method": None,
            "deliverable": False,
            "coords": None,
            "matched_address": None,
            "plant_address": PLANT_ADDRESS,
        }
    km, method = await road_distance_km(geo["lat"], geo["lon"])
    return {
        "found": True,
        "distance_km": km,
        "method": method,
        "deliverable": km <= MAX_DELIVERY_KM,
        "coords": {"lat": geo["lat"], "lon": geo["lon"]},
        "matched_address": geo["display_name"],
        "plant_address": PLANT_ADDRESS,
    }
