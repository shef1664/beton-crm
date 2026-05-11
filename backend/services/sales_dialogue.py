"""Deterministic dialogue engine for the voice sales agent."""

from __future__ import annotations

import re
from typing import Any


FIELD_ORDER = (
    "concrete_grade",
    "volume",
    "address",
    "distance",
    "delivery_date",
    "payment_method",
    "urgency",
    "name",
)

FIELD_PROMPTS = {
    "concrete_grade": "\u041a\u0430\u043a\u0430\u044f \u043c\u0430\u0440\u043a\u0430 \u0431\u0435\u0442\u043e\u043d\u0430 \u043d\u0443\u0436\u043d\u0430, \u043d\u0430\u043f\u0440\u0438\u043c\u0435\u0440 \u041c200, \u041c250 \u0438\u043b\u0438 \u041c300?",
    "volume": "\u041a\u0430\u043a\u043e\u0439 \u043d\u0443\u0436\u0435\u043d \u043e\u0431\u044a\u0435\u043c \u0432 \u043a\u0443\u0431\u0430\u0445?",
    "address": "\u041f\u043e\u0434\u0441\u043a\u0430\u0436\u0438\u0442\u0435 \u0430\u0434\u0440\u0435\u0441 \u0434\u043e\u0441\u0442\u0430\u0432\u043a\u0438 \u0438\u043b\u0438 \u0445\u043e\u0442\u044f \u0431\u044b \u0440\u0430\u0439\u043e\u043d \u043e\u0431\u044a\u0435\u043a\u0442\u0430.",
    "distance": "\u0415\u0441\u043b\u0438 \u0437\u043d\u0430\u0435\u0442\u0435, \u0441\u043a\u043e\u043b\u044c\u043a\u043e \u043f\u0440\u0438\u043c\u0435\u0440\u043d\u043e \u043a\u0438\u043b\u043e\u043c\u0435\u0442\u0440\u043e\u0432 \u043e\u0442 \u0437\u0430\u0432\u043e\u0434\u0430 \u0434\u043e \u043e\u0431\u044a\u0435\u043a\u0442\u0430?",
    "delivery_date": "\u041d\u0430 \u043a\u0430\u043a\u0443\u044e \u0434\u0430\u0442\u0443 \u0438\u043b\u0438 \u0432\u0440\u0435\u043c\u044f \u043d\u0443\u0436\u043d\u0430 \u043f\u043e\u0441\u0442\u0430\u0432\u043a\u0430?",
    "payment_method": "\u041e\u043f\u043b\u0430\u0442\u0430 \u043f\u043b\u0430\u043d\u0438\u0440\u0443\u0435\u0442\u0441\u044f \u043d\u0430\u043b\u0438\u0447\u043d\u0430\u044f \u0438\u043b\u0438 \u0431\u0435\u0437\u043d\u0430\u043b\u0438\u0447\u043d\u0430\u044f?",
    "urgency": "\u042d\u0442\u043e \u0441\u0440\u043e\u0447\u043d\u0430\u044f \u0437\u0430\u044f\u0432\u043a\u0430, \u043d\u0443\u0436\u043d\u043e \u0441\u0435\u0433\u043e\u0434\u043d\u044f-\u0437\u0430\u0432\u0442\u0440\u0430, \u0438\u043b\u0438 \u043c\u043e\u0436\u043d\u043e \u043f\u043b\u0430\u043d\u043e\u0432\u043e?",
    "name": "\u0418 \u043f\u043e\u0434\u0441\u043a\u0430\u0436\u0438\u0442\u0435, \u043a\u0430\u043a \u043a \u0432\u0430\u043c \u043c\u043e\u0436\u043d\u043e \u043e\u0431\u0440\u0430\u0449\u0430\u0442\u044c\u0441\u044f?",
}

ACKS = (
    "\u041f\u043e\u043d\u044f\u043b\u0430.",
    "\u0425\u043e\u0440\u043e\u0448\u043e.",
    "\u041e\u0442\u043b\u0438\u0447\u043d\u043e.",
    "\u041f\u0440\u0438\u043d\u044f\u043b\u0430.",
)

YES_WORDS = (
    "\u0434\u0430",
    "\u0430\u0433\u0430",
    "\u043a\u043e\u043d\u0435\u0447\u043d\u043e",
    "\u043e\u0444\u043e\u0440\u043c\u043b\u044f\u0439\u0442\u0435",
    "\u043f\u043e\u0434\u0445\u043e\u0434\u0438\u0442",
    "\u0443\u0441\u0442\u0440\u0430\u0438\u0432\u0430\u0435\u0442",
    "\u0432\u0435\u0440\u043d\u043e",
)
NO_WORDS = (
    "\u043d\u0435\u0442",
    "\u043d\u0435 \u043f\u043e\u0434\u0445\u043e\u0434\u0438\u0442",
    "\u043d\u0435 \u0443\u0441\u0442\u0440\u0430\u0438\u0432\u0430\u0435\u0442",
    "\u043d\u0435 \u0441\u0435\u0439\u0447\u0430\u0441",
    "\u043f\u043e\u0434\u0443\u043c\u0430\u044e",
)
HUMAN_WORDS = (
    "\u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440",
    "\u043e\u043f\u0435\u0440\u0430\u0442\u043e\u0440",
    "\u0447\u0435\u043b\u043e\u0432\u0435\u043a",
    "\u0436\u0438\u0432\u043e\u0439",
    "\u0441\u043e\u0435\u0434\u0438\u043d\u0438",
    "\u043f\u0435\u0440\u0435\u043a\u043b\u044e\u0447\u0438",
)
PRICE_OBJECTION_WORDS = (
    "\u0434\u043e\u0440\u043e\u0433\u043e",
    "\u0434\u0435\u0448\u0435\u0432\u043b\u0435",
    "\u0441\u043a\u0438\u0434\u043a",
    "\u0443\u0441\u0442\u0443\u043f",
    "\u0441\u043d\u0438\u0437",
    "\u0446\u0435\u043d\u0430",
)
ADDRESS_MARKERS = (
    "\u0443\u043b",
    "\u0443\u043b\u0438\u0446",
    "\u0434\u043e\u043c",
    "\u0440\u0430\u0439\u043e\u043d",
    "\u043f\u0440\u043e\u0441\u043f",
    "\u0448\u043e\u0441\u0441\u0435",
    "\u043f\u043e\u0441\u0435\u043b",
    "\u043e\u0431\u044a\u0435\u043a\u0442",
)
DATE_WORDS = (
    "\u0441\u0435\u0433\u043e\u0434\u043d\u044f",
    "\u0437\u0430\u0432\u0442\u0440\u0430",
    "\u043f\u043e\u0441\u043b\u0435\u0437\u0430\u0432\u0442\u0440\u0430",
    "\u0443\u0442\u0440\u043e\u043c",
    "\u0432\u0435\u0447\u0435\u0440\u043e\u043c",
    "\u0434\u043d\u0435\u043c",
    "\u0447\u0438\u0441\u043b",
    "\u0434\u0430\u0442",
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _lower(text: str) -> str:
    return text.casefold()


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    lowered = _lower(text)
    return any(word in lowered for word in words)


def _extract_grade(text: str) -> str | None:
    match = re.search(r"[\u041c\u043cMm]\s*-?\s*(100|150|200|250|300|350|400|450)", text)
    if not match:
        return None
    return f"\u041c{match.group(1)}"


def _extract_number(text: str) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _normalize_payment(text: str) -> str | None:
    lowered = _lower(text)
    if "\u0431\u0435\u0437\u043d\u0430\u043b" in lowered:
        return "\u0431\u0435\u0437\u043d\u0430\u043b\u0438\u0447\u043d\u044b\u0439"
    if "\u043d\u0430\u043b" in lowered:
        return "\u043d\u0430\u043b\u0438\u0447\u043d\u044b\u0439"
    return None


def _normalize_urgency(text: str) -> str | None:
    lowered = _lower(text)
    if any(word in lowered for word in ("\u0441\u0440\u043e\u0447", "\u0441\u0435\u0433\u043e\u0434\u043d\u044f", "\u0441\u0435\u0439\u0447\u0430\u0441", "\u043a\u0430\u043a \u043c\u043e\u0436\u043d\u043e \u0431\u044b\u0441\u0442\u0440\u0435\u0435")):
        return "urgent"
    if any(word in lowered for word in ("\u043f\u043b\u0430\u043d\u043e\u0432", "\u043f\u043e\u0437\u0436\u0435", "\u043d\u0435 \u0441\u0440\u043e\u0447\u043d\u043e")):
        return "normal"
    if any(word in lowered for word in ("\u0431\u044b\u0441\u0442\u0440", "\u043f\u043e\u0441\u043a\u043e\u0440\u0435\u0435", "\u0431\u043b\u0438\u0436\u0430\u0439\u0448")):
        return "asap"
    return None


class SalesDialogueEngine:
    def opening_message(self) -> str:
        return (
            "\u0417\u0434\u0440\u0430\u0432\u0441\u0442\u0432\u0443\u0439\u0442\u0435. \u041d\u0430 \u043b\u0438\u043d\u0438\u0438 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440 \u043e\u0442\u0434\u0435\u043b\u0430 \u043f\u0440\u043e\u0434\u0430\u0436 \u0431\u0435\u0442\u043e\u043d\u0430. "
            "\u042f \u0431\u044b\u0441\u0442\u0440\u043e \u0441\u043e\u0431\u0435\u0440\u0443 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b, \u0441\u043e\u0440\u0438\u0435\u043d\u0442\u0438\u0440\u0443\u044e \u043f\u043e \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u0438 \u0438 \u043f\u0440\u0438 \u043d\u0435\u043e\u0431\u0445\u043e\u0434\u0438\u043c\u043e\u0441\u0442\u0438 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0443 \u0436\u0438\u0432\u043e\u0433\u043e \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u0430. "
            + FIELD_PROMPTS["concrete_grade"]
        )

    def next_missing_field(self, collected: dict[str, Any]) -> str | None:
        for field in FIELD_ORDER:
            if collected.get(field) in (None, "", []):
                return field
        return None

    def wants_human(self, text: str) -> bool:
        return _contains_any(text, HUMAN_WORDS)

    def has_price_objection(self, text: str) -> bool:
        return "\u0434\u043e\u0440\u043e\u0433\u043e" in _lower(text) or (
            _contains_any(text, PRICE_OBJECTION_WORDS) and "\u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440" in _lower(text)
        )

    def _extract_value(self, field: str, text: str, *, pending_field: str | None = None) -> Any:
        lowered = _lower(text)

        if field == "concrete_grade":
            return _extract_grade(text)

        if field == "volume":
            if pending_field == "volume" or "\u043a\u0443\u0431" in lowered or "\u043c3" in lowered or "\u043c^3" in lowered:
                return _extract_number(text)
            return None

        if field == "address":
            if pending_field != "address" and not any(marker in lowered for marker in ADDRESS_MARKERS):
                return None
            value = text.strip()
            return value if len(value) >= 5 else None

        if field == "distance":
            if pending_field == "distance" or "\u043a\u043c" in lowered or "\u043a\u0438\u043b\u043e\u043c" in lowered:
                return _extract_number(text)
            return None

        if field == "delivery_date":
            if pending_field == "delivery_date" or any(word in lowered for word in DATE_WORDS):
                value = text.strip()
                return value if len(value) >= 3 else None
            return None

        if field == "payment_method":
            return _normalize_payment(text)

        if field == "urgency":
            if pending_field == "urgency" or _normalize_urgency(text):
                return _normalize_urgency(text)
            return None

        if field == "name":
            if pending_field != "name":
                return None
            value = text.strip(" .,!?:;")
            if len(value) < 2 or len(value.split()) > 3:
                return None
            if re.search(r"\d", value):
                return None
            if _contains_any(value, HUMAN_WORDS + PRICE_OBJECTION_WORDS):
                return None
            return value

        return None

    def _with_ack(self, session: dict[str, Any], prompt: str) -> str:
        idx = session.setdefault("assistant_style_idx", 0)
        ack = ACKS[idx % len(ACKS)]
        session["assistant_style_idx"] = idx + 1
        return f"{ack} {prompt}"

    def build_quote_message(self, collected: dict[str, Any], calculation: dict[str, Any]) -> str:
        name_part = f"{collected['name']}, " if collected.get("name") else ""
        urgency_part = ""
        if collected.get("urgency") in ("urgent", "asap"):
            urgency_part = " \u0417\u0430\u044f\u0432\u043a\u0443 \u043e\u0442\u043c\u0435\u0447\u0430\u044e \u043a\u0430\u043a \u0441\u0440\u043e\u0447\u043d\u0443\u044e, \u0447\u0442\u043e\u0431\u044b \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440 \u0432\u0437\u044f\u043b \u0435\u0435 \u0432 \u043f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442."
        return (
            f"{name_part}\u043f\u0440\u0435\u0434\u0432\u0430\u0440\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0439 \u0440\u0430\u0441\u0447\u0435\u0442 \u0433\u043e\u0442\u043e\u0432. "
            f"\u041f\u043e \u0437\u0430\u044f\u0432\u043a\u0435 \u043d\u0430 {collected['volume']} \u043c3 \u0431\u0435\u0442\u043e\u043d\u0430 {collected['concrete_grade']} "
            f"\u0441 \u0434\u043e\u0441\u0442\u0430\u0432\u043a\u043e\u0439 \u043d\u0430 \u043e\u0431\u044a\u0435\u043a\u0442 {collected['address']}: "
            f"\u0431\u0435\u0442\u043e\u043d {calculation['beton_cost']:.0f} \u0440\u0443\u0431\u043b\u0435\u0439, "
            f"\u0434\u043e\u0441\u0442\u0430\u0432\u043a\u0430 {calculation['delivery_cost']:.0f} \u0440\u0443\u0431\u043b\u0435\u0439, "
            f"\u0438\u0442\u043e\u0433\u043e {calculation['total']:.0f} \u0440\u0443\u0431\u043b\u0435\u0439."
            f"{urgency_part} "
            "\u0415\u0441\u043b\u0438 \u0432\u0430\u0441 \u0443\u0441\u0442\u0440\u0430\u0438\u0432\u0430\u0435\u0442, \u044f \u0441\u0440\u0430\u0437\u0443 \u043f\u0435\u0440\u0435\u0434\u0430\u043c \u0437\u0430\u044f\u0432\u043a\u0443 \u0432 \u0440\u0430\u0431\u043e\u0442\u0443. "
            "\u0415\u0441\u043b\u0438 \u0445\u043e\u0442\u0438\u0442\u0435 \u043e\u0431\u0441\u0443\u0434\u0438\u0442\u044c \u0443\u0441\u043b\u043e\u0432\u0438\u044f, \u043c\u043e\u0433\u0443 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0438\u0442\u044c \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u0430."
        )

    def build_objection_message(self, session: dict[str, Any]) -> str:
        collected = session.get("collected_data", {})
        grade = collected.get("concrete_grade", "\u0431\u0435\u0442\u043e\u043d\u0443")
        volume = collected.get("volume", "\u043e\u0431\u044a\u0435\u043c\u0443")
        return (
            f"\u041f\u043e\u043d\u0438\u043c\u0430\u044e, \u0446\u0435\u043d\u0430 \u0432\u0430\u0436\u043d\u0430. \u041f\u043e {grade} \u0438 \u043e\u0431\u044a\u0435\u043c\u0443 {volume} "
            "\u0441\u0440\u0430\u0437\u0443 \u043f\u0435\u0440\u0435\u0434\u0430\u044e \u0437\u0430\u043f\u0440\u043e\u0441 \u0436\u0438\u0432\u043e\u043c\u0443 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u0443, "
            "\u0447\u0442\u043e\u0431\u044b \u043e\u043d \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u043b \u0441\u043a\u0438\u0434\u043a\u0443, \u0431\u043b\u0438\u0436\u0430\u0439\u0448\u0443\u044e \u043c\u0430\u0448\u0438\u043d\u0443 \u0438 \u0442\u043e\u0447\u043d\u044b\u0435 \u0443\u0441\u043b\u043e\u0432\u0438\u044f \u043f\u043e \u0434\u043e\u0441\u0442\u0430\u0432\u043a\u0435. \u041f\u0435\u0440\u0435\u043a\u043b\u044e\u0447\u0430\u044e."
        )

    def process_turn(self, session: dict[str, Any], user_text: str) -> dict[str, Any]:
        text = _clean_text(user_text)
        if not text:
            return {
                "action": "repeat",
                "response_text": "\u042f \u043d\u0435 \u0440\u0430\u0441\u0441\u043b\u044b\u0448\u0430\u043b\u0430 \u043e\u0442\u0432\u0435\u0442. \u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u0435, \u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430, \u0435\u0449\u0435 \u0440\u0430\u0437.",
            }

        if self.wants_human(text):
            return {
                "action": "handoff",
                "response_text": "\u0425\u043e\u0440\u043e\u0448\u043e, \u0441\u043e\u0435\u0434\u0438\u043d\u044f\u044e \u0432\u0430\u0441 \u0441 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u043e\u043c \u043e\u0442\u0434\u0435\u043b\u0430 \u043f\u0440\u043e\u0434\u0430\u0436.",
                "handoff_reason": "requested_human",
            }

        stage = session.get("stage", "qualification")
        collected = session.setdefault("collected_data", {})
        meta = session.setdefault("sales_context", {"objections": [], "close_attempts": 0})

        if stage == "quote_confirmation":
            lowered = _lower(text)
            if self.has_price_objection(text):
                meta["objections"].append("price")
                return {
                    "action": "handoff",
                    "response_text": self.build_objection_message(session),
                    "handoff_reason": "price_objection",
                }
            if any(word in lowered for word in YES_WORDS):
                return {
                    "action": "create_lead",
                    "response_text": (
                        "\u041e\u0442\u043b\u0438\u0447\u043d\u043e, \u0444\u0438\u043a\u0441\u0438\u0440\u0443\u044e \u0437\u0430\u044f\u0432\u043a\u0443 \u0438 \u043f\u0435\u0440\u0435\u0434\u0430\u044e \u0435\u0435 \u0432 \u0440\u0430\u0431\u043e\u0442\u0443. "
                        "\u041c\u0435\u043d\u0435\u0434\u0436\u0435\u0440 \u0441\u0432\u044f\u0436\u0435\u0442\u0441\u044f \u0441 \u0432\u0430\u043c\u0438 \u0434\u043b\u044f \u0444\u0438\u043d\u0430\u043b\u044c\u043d\u043e\u0433\u043e \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f \u0434\u0435\u0442\u0430\u043b\u0435\u0439."
                    ),
                }
            if any(word in lowered for word in NO_WORDS):
                meta["objections"].append("not_ready")
                return {
                    "action": "handoff",
                    "response_text": (
                        "\u041f\u043e\u043d\u044f\u043b\u0430. \u0427\u0442\u043e\u0431\u044b \u043d\u0435 \u043f\u043e\u0442\u0435\u0440\u044f\u0442\u044c \u0437\u0430\u044f\u0432\u043a\u0443, \u043f\u0435\u0440\u0435\u0434\u0430\u044e \u0432\u0430\u0441 \u0436\u0438\u0432\u043e\u043c\u0443 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u0443. "
                        "\u041e\u043d \u043f\u043e\u043c\u043e\u0436\u0435\u0442 \u0434\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u0442\u044c \u0443\u0441\u043b\u043e\u0432\u0438\u044f \u0438 \u043f\u043e\u0434\u0431\u0435\u0440\u0435\u0442 \u043b\u0443\u0447\u0448\u0438\u0439 \u0432\u0430\u0440\u0438\u0430\u043d\u0442."
                    ),
                    "handoff_reason": "quote_objection",
                }
            meta["close_attempts"] += 1
            if meta["close_attempts"] >= 2:
                return {
                    "action": "handoff",
                    "response_text": (
                        "\u0427\u0442\u043e\u0431\u044b \u043d\u0435 \u0437\u0430\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u0442\u044c \u0432\u0430\u0441, \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0430\u044e \u0436\u0438\u0432\u043e\u0433\u043e \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u0430. "
                        "\u041e\u043d \u0431\u044b\u0441\u0442\u0440\u043e \u0443\u0442\u043e\u0447\u043d\u0438\u0442 \u0434\u0435\u0442\u0430\u043b\u0438 \u0438 \u0434\u043e\u0432\u0435\u0434\u0435\u0442 \u0437\u0430\u044f\u0432\u043a\u0443 \u0434\u043e \u0437\u0430\u043a\u0430\u0437\u0430."
                    ),
                    "handoff_reason": "confirmation_unclear",
                }
            return {
                "action": "repeat_confirmation",
                "response_text": (
                    "\u0415\u0441\u043b\u0438 \u0440\u0430\u0441\u0447\u0435\u0442 \u043f\u043e\u0434\u0445\u043e\u0434\u0438\u0442, \u0441\u043a\u0430\u0436\u0438\u0442\u0435 \u0434\u0430, \u0438 \u044f \u0441\u0440\u0430\u0437\u0443 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044e \u0437\u0430\u044f\u0432\u043a\u0443 \u0432 \u0440\u0430\u0431\u043e\u0442\u0443. "
                    "\u0415\u0441\u043b\u0438 \u0445\u043e\u0442\u0438\u0442\u0435 \u043e\u0431\u0441\u0443\u0434\u0438\u0442\u044c \u0443\u0441\u043b\u043e\u0432\u0438\u044f, \u0441\u043a\u0430\u0436\u0438\u0442\u0435 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440."
                ),
            }

        pending_field = self.next_missing_field(collected)
        extracted = self._extract_value(pending_field, text, pending_field=pending_field)
        if extracted is not None:
            collected[pending_field] = extracted

        next_field = self.next_missing_field(collected)
        if next_field == pending_field:
            return {
                "action": "clarify",
                "response_text": FIELD_PROMPTS[pending_field],
                "pending_field": pending_field,
            }

        if next_field:
            return {
                "action": "collect",
                "response_text": self._with_ack(session, FIELD_PROMPTS[next_field]),
                "pending_field": next_field,
                "collected_data": collected,
            }

        return {
            "action": "ready_for_quote",
            "response_text": "\u0421\u043f\u0430\u0441\u0438\u0431\u043e, \u043e\u0441\u043d\u043e\u0432\u043d\u044b\u0435 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b \u0437\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u043b\u0430. \u0421\u0447\u0438\u0442\u0430\u044e \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c.",
            "collected_data": collected,
        }
