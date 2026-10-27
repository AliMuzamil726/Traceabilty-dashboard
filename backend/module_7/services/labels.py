"""Bale labels: an A4 sheet (reportlab), one label as PNG, and a ZIP of QR images."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from datetime import date

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from module_7.services import images


@dataclass(frozen=True)
class LabelConfig:
    """Grid and sizes for the label sheet. Defaults fit common 3 x 8 A4 label stock."""

    columns: int = 3
    rows: int = 8
    margin_top_mm: float = 13.0
    margin_left_mm: float = 7.0
    label_width_mm: float = 63.5
    label_height_mm: float = 33.9
    gap_x_mm: float = 2.5
    gap_y_mm: float = 0.0


LABELS = LabelConfig()

#: Printed small under every code. The default; Settings can change it.
DEFAULT_CAPTION = "Scan to trace"


def configured() -> LabelConfig:
    """The label sheet in force, from Settings, falling back to :data:`LABELS`."""
    from core import app_settings

    grid = app_settings.setting_or("qr.label_grid", None)
    if not isinstance(grid, dict):
        return LABELS
    return LabelConfig(
        columns=int(grid.get("columns", LABELS.columns)),
        rows=int(grid.get("rows", LABELS.rows)),
        margin_top_mm=float(grid.get("margin_top_mm", LABELS.margin_top_mm)),
        margin_left_mm=float(grid.get("margin_left_mm", LABELS.margin_left_mm)),
        label_width_mm=float(grid.get("label_width_mm", LABELS.label_width_mm)),
        label_height_mm=float(grid.get("label_height_mm", LABELS.label_height_mm)),
        gap_x_mm=float(grid.get("gap_x_mm", LABELS.gap_x_mm)),
        gap_y_mm=float(grid.get("gap_y_mm", LABELS.gap_y_mm)),
    )


def caption() -> str:
    """The caption printed under each code, from Settings."""
    from core import app_settings

    return str(app_settings.setting_or("qr.label_caption", DEFAULT_CAPTION))


INK = colors.HexColor(images.INK)
MUTED = colors.HexColor("#5B675F")


@dataclass(frozen=True)
class Label:
    url: str
    serial: str
    heap_id: str
    site_name: str
    produced: date


def pdf(labels: list[Label], cfg: LabelConfig | None = None) -> bytes:
    cfg = cfg or configured()
    text = caption()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("SAWIE bale labels")
    _, height = A4
    per_page = cfg.columns * cfg.rows
    for i, label in enumerate(labels):
        if i and i % per_page == 0:
            c.showPage()
        slot = i % per_page
        row, col = divmod(slot, cfg.columns)
        x = (cfg.margin_left_mm + col * (cfg.label_width_mm + cfg.gap_x_mm)) * mm
        top = height - (cfg.margin_top_mm + row * (cfg.label_height_mm + cfg.gap_y_mm)) * mm
        size = (cfg.label_height_mm - 4) * mm
        c.drawImage(
            ImageReader(io.BytesIO(images.png(label.url, box_size=6))),
            x + 2 * mm,
            top - 2 * mm - size,
            size,
            size,
        )
        tx = x + size + 4 * mm
        c.setFillColor(INK)
        c.setFont("Courier-Bold", 8.5)
        c.drawString(tx, top - 7 * mm, label.serial)
        c.setFont("Helvetica", 7)
        c.drawString(tx, top - 12 * mm, label.heap_id)
        c.drawString(tx, top - 16 * mm, label.site_name[:28])
        c.setFillColor(MUTED)
        c.drawString(tx, top - 20 * mm, label.produced.isoformat())
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 7.5)
        if text:
            c.drawString(tx, top - 26 * mm, text[:34])
    c.showPage()
    c.save()
    return buf.getvalue()


def label_png(label: Label) -> bytes:
    """One label at 600 x 320 px, for small label printers."""
    width, height = 600, 320
    canvas_img = Image.new("RGB", (width, height), "white")
    qr = images.pil_image(label.url, box_size=8).convert("RGB")
    qr = qr.resize((280, 280))
    canvas_img.paste(qr, (20, 20))
    draw = ImageDraw.Draw(canvas_img)
    font = ImageFont.load_default()
    lines = [
        label.serial,
        label.heap_id,
        label.site_name[:30],
        label.produced.isoformat(),
        caption()[:34],
    ]
    for i, text in enumerate(lines):
        draw.text((320, 50 + i * 44), text, fill=images.INK, font=font)
    buf = io.BytesIO()
    canvas_img.save(buf, format="PNG")
    return buf.getvalue()


def zip_of_pngs(items: list[tuple[str, str]]) -> bytes:
    """``items`` are (file name stem, trace URL)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for stem, url in items:
            zf.writestr(f"{stem}.png", images.png(url))
    return buf.getvalue()
