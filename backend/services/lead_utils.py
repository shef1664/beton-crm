"""Helpers for normalizing lead payloads across services."""

from __future__ import annotations

from typing import Any


def coerce_amount(value: Any) -> float | None:
    if value in (None, "", False):
        return None

    if isinstance(value, dict):
        for key in ("total", "calculated_amount", "amount", "value"):
            if key in value:
                return coerce_amount(value.get(key))
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = value.strip().replace(" ", "").replace(",", ".")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def normalize_phone(phone: Any) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if not digits:
        return ""

    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits

    if len(digits) == 11 and digits.startswith("7"):
        return f"+{digits}"

    return f"+{digits}" if digits else ""


def phone_variants(phone: Any) -> list[str]:
    normalized = normalize_phone(phone)
    digits = normalized.lstrip("+")
    variants: list[str] = []

    if normalized:
        variants.append(normalized)
    if digits:
        variants.append(digits)
    if len(digits) == 11 and digits.startswith("7"):
        variants.append("8" + digits[1:])
        variants.append(digits[1:])

    deduped: list[str] = []
    for item in variants:
        if item and item not in deduped:
            deduped.append(item)
    return deduped
