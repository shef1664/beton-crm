from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


KOPEKS = Decimal("0.01")


def to_money(value: Decimal) -> Decimal:
    return value.quantize(KOPEKS, rounding=ROUND_HALF_UP)


def format_money(value: Decimal) -> str:
    normalized = to_money(value)
    whole, fraction = f"{normalized:.2f}".split(".")
    groups = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    return f"{' '.join(reversed(groups))}.{fraction}"


class BankDetails(BaseModel):
    bank_name: str
    bik: str
    account: str
    correspondent_account: str


class Seller(BaseModel):
    name: str
    inn: str
    kpp: Optional[str] = None
    address: str
    phone: Optional[str] = None
    email: Optional[str] = None
    director_title: Optional[str] = None
    director_name: Optional[str] = None
    accountant_name: Optional[str] = None
    bank: BankDetails


class Buyer(BaseModel):
    name: str
    inn: str
    kpp: Optional[str] = None
    address: Optional[str] = None


class InvoiceItem(BaseModel):
    name: str
    quantity: Decimal = Field(gt=0)
    unit: str
    unit_price: Decimal = Field(gt=0)

    @field_validator("unit_price", mode="before")
    @classmethod
    def parse_unit_price(cls, value: object) -> object:
        if isinstance(value, str):
            return value.replace(" ", "").replace(",", ".")
        return value

    @property
    def total(self) -> Decimal:
        return to_money(self.quantity * self.unit_price)


class InvoiceRequest(BaseModel):
    invoice_number: str
    invoice_date: str
    seller: Seller
    buyer: Buyer
    items: List[InvoiceItem]
    vat_rate: Decimal = Field(default=Decimal("22"), ge=0)

    @field_validator("vat_rate", mode="before")
    @classmethod
    def parse_vat_rate(cls, value: object) -> object:
        if isinstance(value, str):
            return value.replace("%", "").replace(",", ".").strip()
        return value

    @property
    def subtotal(self) -> Decimal:
        return to_money(self.total_amount - self.vat_amount)

    @property
    def vat_amount(self) -> Decimal:
        if self.vat_rate == 0:
            return Decimal("0.00")
        return to_money(self.total_amount * self.vat_rate / (Decimal("100") + self.vat_rate))

    @property
    def total_amount(self) -> Decimal:
        return to_money(sum((item.total for item in self.items), Decimal("0")))


class InvoicePdfResult(BaseModel):
    invoice_number: str
    pdf_path: Path
    subtotal: str
    vat_amount: str
    total_amount: str
    qr_payload: str


class DefaultInvoiceRequest(BaseModel):
    """Заявка на счёт от продавца по умолчанию (номер/дата/реквизиты подставит сервис)."""
    buyer: Buyer
    items: List[InvoiceItem]
    # ключ организации-продавца (sequoia/pulsar/…); пусто → продавец по умолчанию
    seller: Optional[str] = None
