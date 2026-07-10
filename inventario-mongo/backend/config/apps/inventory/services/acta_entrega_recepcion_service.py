"""
Generador de ACTA DE ENTREGA - RECEPCION para Inventarios DataCom.

El layout replica el formato corporativo ACT-SIGC-SI-1.0-OFE con:
- Encabezado institucional
- Tabla de items entregados
- Observaciones
- Firmas Entrega/Recibe
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import simpleSplit


_PAGE_W, _PAGE_H = A4

_MESES_ES = {
    "January": "enero",
    "February": "febrero",
    "March": "marzo",
    "April": "abril",
    "May": "mayo",
    "June": "junio",
    "July": "julio",
    "August": "agosto",
    "September": "septiembre",
    "October": "octubre",
    "November": "noviembre",
    "December": "diciembre",
}


def _register_fonts() -> tuple[str, str]:
    """Intenta registrar fuentes Unicode; cae a Helvetica si no existen."""
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
        return "DejaVu", "DejaVu-Bold"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


def _draw_header(c: canvas.Canvas, font: str, font_bold: str, y_top: float):
    c.setFont(font_bold, 9)
    c.drawRightString(_PAGE_W - 20 * mm, y_top, "ACT-SIGC-SI-1.0-OFE | Abril 2026")

    c.setFont(font_bold, 22)
    c.drawCentredString(_PAGE_W / 2, y_top - 52, "ACTA DE ENTREGA - RECEPCION")


def _draw_place_date(c: canvas.Canvas, font: str, city: str, dt: datetime, y: float):
    mes = _MESES_ES.get(dt.strftime("%B"), dt.strftime("%B"))
    c.setFont(font, 11)
    c.drawRightString(_PAGE_W - 20 * mm, y, f"{city}, {dt.day:02d} de {mes} del {dt.year}")


def _table_data(items: list[dict]) -> list[list[str]]:
    rows = [["Item", "Detalle", "Marca", "Modelo", "Serie", "MAC", "Cantidad", "Unidad"]]
    for idx, item in enumerate(items, start=1):
        rows.append(
            [
                str(idx),
                str(item.get("detalle") or "---"),
                str(item.get("marca") or "---"),
                str(item.get("modelo") or "---"),
                str(item.get("serie") or "---"),
                str(item.get("mac") or ""),
                str(item.get("cantidad") or 1),
                str(item.get("unidad") or "Unidad"),
            ]
        )
    return rows


def generate_acta_entrega_recepcion_pdf(
    *,
    entrega_nombre: str,
    entrega_cargo: str,
    recibe_nombre: str,
    recibe_cargo: str,
    items: list[dict],
    observacion: str,
    city: str = "Quito",
    generated_at: datetime | None = None,
) -> bytes:
    generated_at = generated_at or datetime.now()

    body_font, bold_font = _register_fonts()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    top_y = _PAGE_H - 20 * mm
    _draw_header(c, body_font, bold_font, top_y)
    _draw_place_date(c, body_font, city, generated_at, top_y - 14)

    data = _table_data(items)
    col_widths = [14 * mm, 64 * mm, 22 * mm, 22 * mm, 18 * mm, 18 * mm, 22 * mm, 18 * mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("FONTNAME", (0, 1), (-1, -1), body_font),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (6, 1), (7, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    table_w, table_h = table.wrapOn(c, _PAGE_W - 40 * mm, _PAGE_H)
    table_y = top_y - 120
    table.drawOn(c, (_PAGE_W - table_w) / 2, table_y - table_h)

    obs_y = table_y - table_h - 16
    c.setFont(bold_font, 11)
    c.drawString(20 * mm, obs_y, "Observacion:")

    c.setFont(body_font, 10)
    max_obs_width = _PAGE_W - 40 * mm
    obs_lines = simpleSplit(observacion or "Sin observaciones.", body_font, 10, max_obs_width)
    line_y = obs_y - 14
    for line in obs_lines[:4]:
        c.drawString(20 * mm, line_y, line)
        line_y -= 12

    sign_y = line_y - 34

    c.line(42 * mm, sign_y, 92 * mm, sign_y)
    c.line(118 * mm, sign_y, 168 * mm, sign_y)

    c.setFont(bold_font, 12)
    c.drawCentredString(67 * mm, sign_y - 16, "Entrega")
    c.drawCentredString(143 * mm, sign_y - 16, "Recibe")

    c.setFont(body_font, 11)
    c.drawCentredString(67 * mm, sign_y - 30, entrega_nombre)
    c.drawCentredString(143 * mm, sign_y - 30, recibe_nombre)
    c.drawCentredString(67 * mm, sign_y - 44, entrega_cargo)
    c.drawCentredString(143 * mm, sign_y - 44, recibe_cargo)
    c.drawCentredString(67 * mm, sign_y - 58, "DataCom S.A.")
    c.drawCentredString(143 * mm, sign_y - 58, "DataCom S.A.")

    c.setStrokeColor(colors.HexColor("#BBBBBB"))
    c.line(20 * mm, 24 * mm, _PAGE_W - 20 * mm, 24 * mm)
    c.setFont(body_font, 8)
    c.setFillColor(colors.HexColor("#333333"))
    c.drawCentredString(
        _PAGE_W / 2,
        18 * mm,
        "Av. Pampite y Chimborazo, Edificio Centro Plaza, Quito - Ecuador | www.datacom.ec",
    )
    c.setFont(body_font, 6.8)
    c.drawCentredString(
        _PAGE_W / 2,
        13 * mm,
        "Este documento es propiedad exclusiva de DATACOM. Las copias no controladas no tienen validez para su uso.",
    )

    c.showPage()
    c.save()
    return buf.getvalue()
