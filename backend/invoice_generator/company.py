"""Продавцы (организации) и брендинг для счетов.

Реквизиты и печати — чувствительные данные, поэтому НЕ хранятся в git. Они читаются
из секретной папки INVOICE_SECRETS_DIR (на Render — Secret Files, по умолчанию /etc/secrets;
локально можно указать свой путь). Логотип «Бетон Экспресс» не секрет — он лежит в пакете.

В секретной папке ожидаются:
  • seller.<key>.json                   — реквизиты организации (напр. seller.sequoia.json);
  • <key>-stamp-signature-pdf.png       — печать+подпись организации (опционально).
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional

from invoice_generator.models import Seller


PACKAGE_ROOT = Path(__file__).resolve().parent
BUNDLED_LOGO = PACKAGE_ROOT / "assets" / "logo-pdf.png"

DEFAULT_SELLER_KEY = os.environ.get("DEFAULT_SELLER_KEY", "sequoia")


def secrets_dir() -> Path:
    return Path(os.environ.get("INVOICE_SECRETS_DIR", "/etc/secrets"))


def brand_logo_path() -> Optional[Path]:
    """Логотип: переопределяется env BRAND_LOGO_PATH, иначе — встроенный в пакет."""
    raw = os.environ.get("BRAND_LOGO_PATH")
    if raw and Path(raw).exists():
        return Path(raw)
    return BUNDLED_LOGO if BUNDLED_LOGO.exists() else None


def stamp_path_for(key: str) -> Optional[Path]:
    """Печать+подпись организации из секретной папки (строго по ключу).

    Печать Пульсара НЕ подставляется в счёт Секвойи. Если файла нет — None
    (в PDF будет подпись без печати).
    """
    candidate = secrets_dir() / f"{key}-stamp-signature-pdf.png"
    return candidate if candidate.exists() else None


def discover_sellers() -> Dict[str, Seller]:
    """Собрать продавцов из секретной папки: seller.<key>.json → {ключ: Seller}."""
    sellers: Dict[str, Seller] = {}
    base = secrets_dir()
    if not base.exists():
        return sellers
    for path in sorted(base.glob("seller.*.json")):
        key = path.stem.split(".", 1)[1]
        try:
            sellers[key] = Seller(**json.loads(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 — битый конфиг не должен ронять сервис
            continue
    return sellers


def resolve_seller(key: Optional[str] = None) -> Optional[Seller]:
    """Продавец по ключу; иначе — по умолчанию; None, если реквизитов нет вовсе."""
    reg = discover_sellers()
    if not reg:
        return None
    if key and key in reg:
        return reg[key]
    if DEFAULT_SELLER_KEY in reg:
        return reg[DEFAULT_SELLER_KEY]
    return next(iter(reg.values()))


def stamp_for_seller(seller: Seller) -> Optional[Path]:
    """Печать по организации: ключ находим по ИНН среди доступных продавцов."""
    for key, candidate in discover_sellers().items():
        if candidate.inn == seller.inn:
            return stamp_path_for(key)
    return None


def invoices_enabled() -> bool:
    """Счета доступны только если в секретной папке есть хотя бы один продавец."""
    return bool(discover_sellers())
