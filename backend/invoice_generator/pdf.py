from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from invoice_generator.models import InvoicePdfResult, InvoiceRequest, format_money
from invoice_generator.qr import build_payment_qr_payload, create_payment_qr_png


FONT_NAME = "InvoiceArialUnicode"
NAVY = colors.HexColor("#12243a")
LINE = colors.HexColor("#6c7885")
LIGHT_LINE = colors.HexColor("#d6dce2")
FONT_PATHS = [
    Path("/Library/Fonts/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    # Linux (Render/сервер) — метрический аналог Arial с кириллицей
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]


ONES = {
    0: "",
    1: "один",
    2: "два",
    3: "три",
    4: "четыре",
    5: "пять",
    6: "шесть",
    7: "семь",
    8: "восемь",
    9: "девять",
}
ONES_FEMALE = {1: "одна", 2: "две"}
TEENS = {
    10: "десять",
    11: "одиннадцать",
    12: "двенадцать",
    13: "тринадцать",
    14: "четырнадцать",
    15: "пятнадцать",
    16: "шестнадцать",
    17: "семнадцать",
    18: "восемнадцать",
    19: "девятнадцать",
}
TENS = {
    2: "двадцать",
    3: "тридцать",
    4: "сорок",
    5: "пятьдесят",
    6: "шестьдесят",
    7: "семьдесят",
    8: "восемьдесят",
    9: "девяносто",
}
HUNDREDS = {
    1: "сто",
    2: "двести",
    3: "триста",
    4: "четыреста",
    5: "пятьсот",
    6: "шестьсот",
    7: "семьсот",
    8: "восемьсот",
    9: "девятьсот",
}
MONTHS = {
    "01": "января",
    "02": "февраля",
    "03": "марта",
    "04": "апреля",
    "05": "мая",
    "06": "июня",
    "07": "июля",
    "08": "августа",
    "09": "сентября",
    "10": "октября",
    "11": "ноября",
    "12": "декабря",
}


def register_font() -> str:
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return FONT_NAME
    for font_path in FONT_PATHS:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont(FONT_NAME, str(font_path)))
            return FONT_NAME
    return "Helvetica"


def plural(number: int, forms: tuple[str, str, str]) -> str:
    last_two = number % 100
    last = number % 10
    if 11 <= last_two <= 14:
        return forms[2]
    if last == 1:
        return forms[0]
    if 2 <= last <= 4:
        return forms[1]
    return forms[2]


def triad_words(number: int, female: bool = False) -> list[str]:
    words = []
    hundreds = number // 100
    remainder = number % 100
    if hundreds:
        words.append(HUNDREDS[hundreds])
    if 10 <= remainder <= 19:
        words.append(TEENS[remainder])
        return words
    tens = remainder // 10
    ones = remainder % 10
    if tens:
        words.append(TENS[tens])
    if ones:
        if female and ones in ONES_FEMALE:
            words.append(ONES_FEMALE[ones])
        else:
            words.append(ONES[ones])
    return words


def amount_in_words(amount: str) -> str:
    normalized = amount.replace(" ", "").replace(",", ".")
    rubles_raw, kopeks = f"{float(normalized):.2f}".split(".")
    rubles = int(rubles_raw)
    if rubles == 0:
        words = ["ноль"]
    else:
        words = []
        millions = rubles // 1_000_000
        thousands = (rubles // 1_000) % 1_000
        rest = rubles % 1_000
        if millions:
            words.extend(triad_words(millions))
            words.append(plural(millions, ("миллион", "миллиона", "миллионов")))
        if thousands:
            words.extend(triad_words(thousands, female=True))
            words.append(plural(thousands, ("тысяча", "тысячи", "тысяч")))
        if rest:
            words.extend(triad_words(rest))
    phrase = " ".join(words)
    return f"{phrase[:1].upper()}{phrase[1:]} {plural(rubles, ('рубль', 'рубля', 'рублей'))} {kopeks} копеек"


def pdf_money(value) -> str:
    return format_money(value).replace(".", ",")


def format_invoice_date(value: str) -> str:
    parts = value.split("-")
    if len(parts) == 3 and parts[1] in MONTHS:
        year, month, day = parts
        return f"{int(day)} {MONTHS[month]} {year} г."
    return value


class SignatureFlowable(Flowable):
    def __init__(self, title: str, name: str, stamp_path: Optional[Path], font_name: str):
        super().__init__()
        self.title = title
        self.name = name
        self.stamp_path = stamp_path
        self.font_name = font_name
        self.width = 175 * mm
        self.height = 42 * mm

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        canvas.setFont(self.font_name, 9)
        canvas.setFillColor(NAVY)
        baseline = 7 * mm
        line_x = 48 * mm
        line_width = 46 * mm
        canvas.drawString(0, baseline, self.title)
        canvas.line(line_x, baseline - 1.2, line_x + line_width, baseline - 1.2)
        canvas.drawString(line_x + line_width + 3 * mm, baseline, f"/ {self.name} /")
        if self.stamp_path and self.stamp_path.exists():
            canvas.drawImage(
                str(self.stamp_path),
                line_x + 9 * mm,
                baseline - 9 * mm,
                width=32 * mm,
                height=48 * mm,
                mask="auto",
                preserveAspectRatio=True,
                anchor="c",
            )
        canvas.restoreState()


def existing_image(path: Optional[Path]) -> Optional[Path]:
    if path and path.exists():
        return path
    return None


def create_invoice_pdf(
    request: InvoiceRequest,
    output_dir: Path,
    logo_path: Optional[Path] = None,
    stamp_signature_path: Optional[Path] = None,
) -> InvoicePdfResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"invoice-{request.invoice_number}.pdf"
    font_name = register_font()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("InvoiceNormal", parent=styles["Normal"], fontName=font_name, fontSize=9, leading=12, textColor=NAVY)
    small = ParagraphStyle("InvoiceSmall", parent=normal, fontSize=7, leading=9)
    bold = ParagraphStyle("InvoiceBold", parent=normal, fontSize=9, leading=12)
    title = ParagraphStyle("InvoiceTitle", parent=styles["Title"], fontName=font_name, fontSize=17, leading=21, textColor=NAVY, alignment=0)

    story = []
    logo = existing_image(logo_path)
    qr_payload = build_payment_qr_payload(request)
    qr_image_top = Image(create_payment_qr_png(qr_payload), width=28 * mm, height=28 * mm)
    if logo:
        top_row = Table(
            [[Image(str(logo), width=30 * mm, height=10 * mm), "", qr_image_top]],
            colWidths=[36 * mm, 116 * mm, 30 * mm],
            hAlign="LEFT",
        )
    else:
        top_row = Table([["", "", qr_image_top]], colWidths=[36 * mm, 116 * mm, 30 * mm], hAlign="LEFT")
    story.extend([top_row, Spacer(1, 6 * mm)])

    bank_table = Table(
        [
            [Paragraph(request.seller.bank.bank_name, normal), Paragraph("БИК", bold), Paragraph(request.seller.bank.bik, normal)],
            [Paragraph("Банк получателя", normal), Paragraph("Сч.№", bold), Paragraph(request.seller.bank.correspondent_account, normal)],
            [Paragraph(f"ИНН   {request.seller.inn}", normal), Paragraph(f"КПП   {request.seller.kpp or '-'}", normal), ""],
            [Paragraph(request.seller.name, normal), "", ""],
            [Paragraph("Получатель", normal), Paragraph("Сч.№", bold), Paragraph(request.seller.bank.account, normal)],
        ],
        colWidths=[100 * mm, 30 * mm, 50 * mm],
    )
    bank_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 8.6),
                ("TEXTCOLOR", (0, 0), (-1, -1), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("SPAN", (0, 0), (0, 1)),
                ("SPAN", (2, 2), (2, 3)),
                ("SPAN", (0, 3), (1, 3)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([bank_table, Spacer(1, 8 * mm)])

    story.extend(
        [
            Paragraph(f"Счет на оплату №{request.invoice_number} от {format_invoice_date(request.invoice_date)}", title),
            Spacer(1, 5 * mm),
            Table(
                [
                    [Paragraph("Исполнитель", normal), Paragraph(f"{request.seller.name}, {request.seller.address}", normal)],
                    [Paragraph("Заказчик", normal), Paragraph(request.buyer.name, normal)],
                    [Paragraph("Комментарий", normal), Paragraph("", normal)],
                ],
                colWidths=[30 * mm, 150 * mm],
                hAlign="LEFT",
            ),
            Spacer(1, 8 * mm),
        ]
    )

    table_data = [
        [
            Paragraph("№", normal),
            Paragraph("Название услуги", normal),
            Paragraph("Кол-во", normal),
            Paragraph("Ед.изм", normal),
            Paragraph("НДС", normal),
            Paragraph("Цена", normal),
            Paragraph("Сумма", normal),
        ]
    ]
    for index, item in enumerate(request.items, start=1):
        table_data.append(
            [
                Paragraph(str(index), normal),
                Paragraph(item.name, normal),
                Paragraph(format_money(item.quantity).rstrip("0").rstrip("."), normal),
                Paragraph(item.unit, normal),
                Paragraph(f"{format_money(request.vat_rate).rstrip('0').rstrip('.')}%", normal),
                Paragraph(pdf_money(item.unit_price), normal),
                Paragraph(pdf_money(item.total), normal),
            ]
        )

    table = Table(table_data, colWidths=[7 * mm, 67 * mm, 17 * mm, 18 * mm, 16 * mm, 33 * mm, 32 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), NAVY),
                ("LINEABOVE", (0, 0), (-1, 0), 0.8, LINE),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, LIGHT_LINE),
                ("FONTNAME", (0, 0), (-1, 0), font_name),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(table)

    totals_table = Table(
        [
            ["Итого:", pdf_money(request.subtotal)],
            ["Сумма НДС:", pdf_money(request.vat_amount)],
            ["Всего к оплате:", pdf_money(request.total_amount)],
        ],
        colWidths=[45 * mm, 35 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), NAVY),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), font_name),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend(
        [
            Spacer(1, 6 * mm),
            Table(
                [[Paragraph(f"Всего наименований {len(request.items)} на сумму {pdf_money(request.total_amount)} руб.", normal), totals_table]],
                colWidths=[98 * mm, 82 * mm],
            ),
            Paragraph(amount_in_words(str(request.total_amount)), normal),
            Spacer(1, 14 * mm),
        ]
    )

    story.append(
        SignatureFlowable(
            request.seller.director_title or "Руководитель",
            request.seller.director_name or "подпись",
            existing_image(stamp_signature_path),
            font_name,
        )
    )
    doc.build(story)
    return InvoicePdfResult(
        invoice_number=request.invoice_number,
        pdf_path=pdf_path,
        subtotal=format_money(request.subtotal),
        vat_amount=format_money(request.vat_amount),
        total_amount=format_money(request.total_amount),
        qr_payload=qr_payload,
    )
