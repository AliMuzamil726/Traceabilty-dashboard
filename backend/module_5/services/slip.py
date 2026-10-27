"""One-page delivery slip for the driver (reportlab), with a QR of the delivery number."""

from __future__ import annotations

import io

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from module_5.services.weights import maunds

FOREST = colors.HexColor("#1D6039")
INK = colors.HexColor("#15221B")
MUTED = colors.HexColor("#5B675F")
LINE = colors.HexColor("#E3E6DE")


def _qr(text: str) -> ImageReader:
    image = qrcode.make(text, box_size=8, border=2)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def render_slip(rows: list[tuple[str, str]], *, delivery_no: str, title: str) -> bytes:
    """``rows`` are (label, value) pairs printed in order."""
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    pdf.setTitle(f"Delivery slip {delivery_no}")
    pdf.setAuthor("SAWIE")
    width, height = A4
    left, top = 20 * mm, height - 20 * mm

    pdf.setFillColor(FOREST)
    pdf.rect(0, height - 12 * mm, width, 12 * mm, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(left, height - 8 * mm, "SAWIE")

    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(left, top - 10 * mm, title)
    pdf.setFont("Courier-Bold", 16)
    pdf.drawString(left, top - 19 * mm, delivery_no)

    size = 42 * mm
    pdf.drawImage(_qr(delivery_no), width - left - size, top - 4 * mm - size, size, size)
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(MUTED)
    pdf.drawCentredString(width - left - size / 2, top - 8 * mm - size, "Scan at the gate")

    y = top - 60 * mm
    for label, value in rows:
        pdf.setStrokeColor(LINE)
        pdf.line(left, y - 3 * mm, width - left, y - 3 * mm)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(left, y, label)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(left + 55 * mm, y, value or "-")
        y -= 10 * mm

    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(
        left,
        30 * mm,
        "Gate officer signature: ______________________     Weighbridge ticket no: ______________",
    )
    pdf.drawString(left, 22 * mm, "Driver signature: ______________________")
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


def weight_text(kg: float | None, crop: str) -> str:
    if kg is None:
        return "-"
    text = f"{kg:,.1f} kg"
    if crop == "cotton":
        text += f" ({maunds(kg):,.1f} maunds)"
    return text
