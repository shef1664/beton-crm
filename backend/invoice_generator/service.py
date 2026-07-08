"""Генерация счёта для встроенного бота (@otdprod_bot).

Реквизиты продавца и печати берутся из секретной папки (см. company.py) — вне git.
Номер счёта и PDF пишутся в INVOICE_OUTPUT_DIR (по умолчанию /tmp/beton-invoices;
на Render файловая система эфемерна — нумерация сбрасывается при рестарте, при
необходимости указать персистентный путь).
"""

import os
from datetime import date
from pathlib import Path
from typing import Optional

from invoice_generator import company
from invoice_generator.models import DefaultInvoiceRequest, InvoicePdfResult, InvoiceRequest
from invoice_generator.pdf import create_invoice_pdf
from invoice_generator.sequence import next_invoice_number
from invoice_generator.text_parser import parse_invoice_text


def output_dir() -> Path:
    return Path(os.environ.get("INVOICE_OUTPUT_DIR", "/tmp/beton-invoices"))


def sequence_path() -> Path:
    raw = os.environ.get("INVOICE_SEQUENCE_PATH")
    return Path(raw) if raw else output_dir() / "invoice-sequence.json"


def generate_invoice(request: DefaultInvoiceRequest) -> Optional[InvoicePdfResult]:
    """Собрать PDF-счёт. None, если в секретной папке нет реквизитов продавца."""
    seller = company.resolve_seller(request.seller)
    if seller is None:
        return None
    invoice_request = InvoiceRequest(
        invoice_number=next_invoice_number(sequence_path()),
        invoice_date=date.today().isoformat(),
        seller=seller,
        buyer=request.buyer,
        items=request.items,
        vat_rate=22,
    )
    return create_invoice_pdf(
        invoice_request,
        output_dir=output_dir(),
        logo_path=company.brand_logo_path(),
        stamp_signature_path=company.stamp_for_seller(seller),
    )


def parse_invoice(text: str) -> DefaultInvoiceRequest:
    """Разобрать текст в заявку (может бросить ValueError с понятным сообщением)."""
    return parse_invoice_text(text)
