"""Normalization adapters for external sales channels."""

from __future__ import annotations

from typing import Any

from config import settings


def _deep_get(data: Any, path: str):
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _pick(data: dict[str, Any], *paths: str):
    for path in paths:
        value = _deep_get(data, path)
        if value not in (None, "", []):
            return value
    return None


class IntegrationAdapters:
    @staticmethod
    def normalize(integration: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        integration = integration.lower().strip()
        adapter = getattr(IntegrationAdapters, f"_normalize_{integration}", None)
        if not adapter:
            return IntegrationAdapters._normalize_generic(integration, payload)
        return adapter(payload)

    @staticmethod
    def _with_defaults(integration: str, lead: dict[str, Any]) -> dict[str, Any]:
        defaults = settings.INTEGRATION_DEFAULTS.get(integration, {})
        normalized = {
            "source": defaults.get("source", integration),
            "source_platform": defaults.get("source_platform", integration),
            "source_channel": defaults.get("source_channel", "message"),
            **lead,
        }
        return {k: v for k, v in normalized.items() if v not in (None, "")}

    @staticmethod
    def _normalize_generic(integration: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        lead = {
            "name": _pick(payload, "name", "client_name", "contact.name", "customer.name", "user.name"),
            "phone": _pick(payload, "phone", "client_phone", "contact.phone", "customer.phone", "user.phone", "caller"),
            "source_account": _pick(payload, "account", "account_id", "source.account", "meta.account"),
            "source_listing": _pick(payload, "listing", "listing_id", "item.id", "source.listing", "meta.listing"),
            "source_campaign": _pick(payload, "campaign", "campaign_id", "source.campaign", "meta.campaign"),
            "comment": _pick(payload, "comment", "message", "text", "description", "notes"),
        }
        if not lead.get("phone"):
            return None, "phone is missing"
        return IntegrationAdapters._with_defaults(integration, lead), None

    @staticmethod
    def _normalize_telephony(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        lead = {
            "name": _pick(payload, "name", "client_name", "contact.name") or "Телефонный лид",
            "phone": _pick(payload, "phone", "client_phone", "caller", "contact.phone"),
            "source_channel": "call",
            "source_account": _pick(payload, "account", "line", "manager"),
            "source_listing": _pick(payload, "line_name", "call_source"),
            "source_campaign": _pick(payload, "campaign", "call_campaign"),
            "comment": _pick(payload, "comment", "record_url", "notes"),
            "client_type": _pick(payload, "client_type") or "private",
        }
        if not lead.get("phone"):
            return None, "phone is missing"
        return IntegrationAdapters._with_defaults("telephony", lead), None

    @staticmethod
    def _normalize_yandex_maps(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        lead = {
            "name": _pick(payload, "name", "contact.name", "client.name", "user.name") or "Лид с Яндекс Карт",
            "phone": _pick(payload, "phone", "contact.phone", "client.phone", "caller"),
            "source_channel": _pick(payload, "channel", "event.channel", "lead.channel") or "chat",
            "source_account": _pick(payload, "business.id", "account_id", "organization.id"),
            "source_listing": _pick(payload, "listing", "card_name", "business.name", "organization.name") or "Яндекс Карты",
            "source_campaign": _pick(payload, "campaign", "traffic_source", "ad_source"),
            "comment": _pick(payload, "message", "comment", "review.text", "request.text"),
            "address": _pick(payload, "address", "business.address", "organization.address_name"),
        }
        if not lead.get("phone"):
            return None, "phone is missing"
        return IntegrationAdapters._with_defaults("yandex_maps", lead), None

    @staticmethod
    def _normalize_2gis(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        lead = {
            "name": _pick(payload, "name", "contact.name", "client.name", "user.name") or "Лид с 2ГИС",
            "phone": _pick(payload, "phone", "contact.phone", "client.phone", "caller"),
            "source_channel": _pick(payload, "channel", "event.channel", "lead.channel") or "chat",
            "source_account": _pick(payload, "branch_id", "account_id", "company.id"),
            "source_listing": _pick(payload, "card_name", "branch_name", "company.name") or "2ГИС",
            "source_campaign": _pick(payload, "campaign", "traffic_source"),
            "comment": _pick(payload, "message", "comment", "review.text", "request.text"),
            "address": _pick(payload, "address", "branch.address_name", "company.address_name"),
        }
        if not lead.get("phone"):
            return None, "phone is missing"
        return IntegrationAdapters._with_defaults("2gis", lead), None

    @staticmethod
    def _normalize_avito(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        lead = {
            "name": _pick(payload, "name", "buyer.name", "contact.name", "user.name") or "Лид с Avito",
            "phone": _pick(payload, "phone", "buyer.phone", "contact.phone", "user.phone", "caller"),
            "source_channel": _pick(payload, "channel", "message_type", "event.channel") or "chat",
            "source_account": _pick(payload, "account_id", "account", "profile.id", "shop.id"),
            "source_listing": _pick(payload, "listing_id", "item.id", "ad.id", "item.title", "ad.title"),
            "source_campaign": _pick(payload, "campaign", "category", "meta.campaign"),
            "comment": _pick(payload, "message", "comment", "text", "description"),
            "client_type": _pick(payload, "client_type") or "private",
        }
        if not lead.get("phone"):
            return None, "phone is missing"
        return IntegrationAdapters._with_defaults("avito", lead), None

    @staticmethod
    def _normalize_vk(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        lead, reason = IntegrationAdapters._normalize_generic("vk", payload)
        if lead:
            lead["source_channel"] = lead.get("source_channel") or "message"
            lead["name"] = lead.get("name") or "Лид из VK"
        return lead, reason

    @staticmethod
    def _normalize_whatsapp(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        lead, reason = IntegrationAdapters._normalize_generic("whatsapp", payload)
        if lead:
            lead["source_channel"] = lead.get("source_channel") or "message"
            lead["name"] = lead.get("name") or "Лид из WhatsApp"
        return lead, reason

    @staticmethod
    def _normalize_telegram(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        lead, reason = IntegrationAdapters._normalize_generic("telegram", payload)
        if lead:
            lead["source_channel"] = lead.get("source_channel") or "message"
            lead["name"] = lead.get("name") or "Лид из Telegram"
        return lead, reason

