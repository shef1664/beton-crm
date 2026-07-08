from decimal import Decimal
from io import BytesIO

import qrcode

from invoice_generator.models import InvoiceRequest


def clean_qr_value(value: object) -> str:
    return str(value).replace("|", " ").replace("\n", " ").strip()


def amount_to_kopeks(amount: Decimal) -> str:
    return str(int((amount * Decimal("100")).quantize(Decimal("1"))))


def build_payment_qr_payload(request: InvoiceRequest) -> str:
    seller = request.seller
    bank = seller.bank
    purpose = f"Оплата по счету №{request.invoice_number} от {request.invoice_date}"
    fields = [
        ("Name", seller.name),
        ("PersonalAcc", bank.account),
        ("BankName", bank.bank_name),
        ("BIC", bank.bik),
        ("CorrespAcc", bank.correspondent_account),
        ("PayeeINN", seller.inn),
        ("KPP", seller.kpp or ""),
        ("Purpose", purpose),
        ("Sum", amount_to_kopeks(request.total_amount)),
    ]
    return "ST00012|" + "|".join(f"{key}={clean_qr_value(value)}" for key, value in fields if clean_qr_value(value))


def create_payment_qr_png(payload: str) -> BytesIO:
    image = qrcode.make(payload, border=2)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

