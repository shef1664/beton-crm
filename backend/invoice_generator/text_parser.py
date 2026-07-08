from decimal import Decimal
import re
from typing import Optional

from invoice_generator.models import Buyer, DefaultInvoiceRequest, InvoiceItem


INN_PATTERN = re.compile(r"\b\d{10}(?:\d{2})?\b")
FREE_POSITION_PATTERN = re.compile(
    r"^(?P<name>.+?)\s+(?P<quantity>\d+(?:[,.]\d+)?)\s+"
    r"(?P<unit>тонн(?:а|ы)?|т|м3|м³|куб(?:а|ов)?|усл\.?|шт\.?|час(?:а|ов)?)\s+"
    r"(?:по\s+)?(?P<price>\d+(?:[,.]\d+)?)\s*(?:₽|руб\.?|р\.?)?$",
    re.IGNORECASE,
)
COMPACT_FREE_POSITION_PATTERN = re.compile(
    r"^(?P<name>.+?)\s+(?P<quantity>\d+(?:[,.]\d+)?)\s*"
    r"(?P<unit>тонн(?:а|ы)?|т|м3|м³|куб(?:а|ов)?|усл\.?|шт\.?|час(?:а|ов)?)\s+"
    r"(?:по\s+)?(?P<price>\d+(?:[,.]\d+)?)\s*(?:₽|руб\.?|р\.?)?$",
    re.IGNORECASE,
)
SERVICE_WITHOUT_UNIT_PATTERN = re.compile(
    r"^(?P<name>услуги\s+.+?|аренда\s+.+?)\s+(?P<quantity>\d+(?:[,.]\d+)?)\s+"
    r"(?:по\s+)?(?P<price>\d+(?:[,.]\d+)?)\s*(?:₽|руб\.?|р\.?)?$",
    re.IGNORECASE,
)
DEFAULT_UNIT_POSITION_PATTERN = re.compile(
    r"^(?P<name>.+?)\s+(?P<quantity>\d+(?:[,.]\d+)?)\s+"
    r"(?:по\s+)?(?P<price>\d+(?:[,.]\d+)?)\s*(?:₽|руб\.?|р\.?)?$",
    re.IGNORECASE,
)


def value_after_colon(line: str) -> str:
    if ":" not in line:
        return ""
    return line.split(":", 1)[1].strip()


def parse_position(line: str) -> InvoiceItem:
    raw = value_after_colon(line)
    parts = [part.strip() for part in raw.split(";")]
    if len(parts) != 4:
        raise ValueError("Позиция должна быть в формате: Позиция: название; количество; ед.; цена")
    return InvoiceItem(name=parts[0], quantity=Decimal(parts[1].replace(",", ".")), unit=parts[2], unit_price=parts[3])


def normalize_unit(unit: str) -> str:
    lower = unit.lower().strip().replace("³", "3")
    if lower.startswith("тонн") or lower == "т":
        return "т"
    if lower in {"м3", "куб", "куба", "кубов"}:
        return "м3"
    if lower.startswith("усл"):
        return "усл."
    if lower.startswith("шт"):
        return "шт."
    if lower.startswith("час"):
        return "час"
    return unit


def normalize_item_name(name: str) -> str:
    clean = " ".join(name.strip().split())
    lower = clean.lower()
    if lower.startswith("счет "):
        clean = clean[5:].strip()
        lower = clean.lower()
    concrete_match = re.fullmatch(r"бетон\s*м?\s*(100|150|200|250|300|350|400)", lower)
    if concrete_match:
        return f"Бетон М{concrete_match.group(1)}"
    if lower == "песок строительный":
        return "Песок строительный"
    if lower in {"песок с доставкой", "песок строительный с доставкой"}:
        return "Песок с доставкой"
    if lower in {"услуги доставки", "доставка"}:
        return "Услуги доставки"
    if lower == "услуги автотранспорта":
        return "Услуги автотранспорта"
    if lower == "услуги автобетононасоса":
        return "Услуги автобетононасоса"
    if lower == "аренда техники":
        return "Аренда техники"
    return clean


def default_unit_for_name(name: str) -> Optional[str]:
    lower = name.lower()
    if re.fullmatch(r"бетон\s*м?\s*(100|150|200|250|300|350|400)", lower) or lower == "бетон":
        return "м3"
    if "песок" in lower:
        return "т"
    if lower.startswith("услуги ") or lower.startswith("аренда ") or lower == "доставка":
        return "усл."
    return None


def parse_free_position(line: str) -> Optional[InvoiceItem]:
    match = FREE_POSITION_PATTERN.match(line.strip()) or COMPACT_FREE_POSITION_PATTERN.match(line.strip())
    if not match:
        service_match = SERVICE_WITHOUT_UNIT_PATTERN.match(line.strip())
        if service_match:
            return InvoiceItem(
                name=normalize_item_name(service_match.group("name")),
                quantity=Decimal(service_match.group("quantity").replace(",", ".")),
                unit="усл.",
                unit_price=service_match.group("price").replace(",", "."),
            )
        default_unit_match = DEFAULT_UNIT_POSITION_PATTERN.match(line.strip())
        if not default_unit_match:
            return None
        item_name = normalize_item_name(default_unit_match.group("name"))
        default_unit = default_unit_for_name(item_name)
        if not default_unit:
            return None
        return InvoiceItem(
            name=item_name,
            quantity=Decimal(default_unit_match.group("quantity").replace(",", ".")),
            unit=default_unit,
            unit_price=default_unit_match.group("price").replace(",", "."),
        )
    return InvoiceItem(
        name=normalize_item_name(match.group("name")),
        quantity=Decimal(match.group("quantity").replace(",", ".")),
        unit=normalize_unit(match.group("unit")),
        unit_price=match.group("price").replace(",", "."),
    )


SELLER_ALIASES = {
    "секвойя": "sequoia", "секвоя": "sequoia", "sequoia": "sequoia",
    "пульсар": "pulsar", "pulsar": "pulsar",
}


def resolve_seller_key(value: str) -> Optional[str]:
    return SELLER_ALIASES.get(value.strip().lower())


def parse_invoice_text(text: str) -> DefaultInvoiceRequest:
    buyer_data = {}
    items = []
    seller_key: Optional[str] = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if not line:
            continue
        if lower.startswith("организация:") or lower.startswith("продавец:") or lower.startswith("от:"):
            seller_key = resolve_seller_key(value_after_colon(line)) or seller_key
            continue
        if lower.startswith("покупатель:"):
            buyer_data["name"] = value_after_colon(line)
        elif lower.startswith("инн:"):
            buyer_data["inn"] = value_after_colon(line)
        elif lower.startswith("инн "):
            match = INN_PATTERN.search(line)
            if match:
                buyer_data["inn"] = match.group(0)
        elif lower.startswith("кпп:"):
            buyer_data["kpp"] = value_after_colon(line)
        elif lower.startswith("адрес:"):
            buyer_data["address"] = value_after_colon(line)
        elif lower.startswith("позиция:"):
            items.append(parse_position(line))
        else:
            if "inn" not in buyer_data:
                match = INN_PATTERN.search(line)
                if match:
                    buyer_data["inn"] = match.group(0)
                    continue
            free_position = parse_free_position(line)
            if free_position:
                items.append(free_position)

    if "inn" not in buyer_data:
        raise ValueError("Нужно указать ИНН")
    buyer_data.setdefault("name", "")
    if not items:
        raise ValueError("Нужно указать хотя бы одну позицию")

    return DefaultInvoiceRequest(buyer=Buyer(**buyer_data), items=items, seller=seller_key)
