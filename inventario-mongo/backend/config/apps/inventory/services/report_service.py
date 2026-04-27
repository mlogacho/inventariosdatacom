"""
Servicio de generación de reportes PDF.

Diseño profesional para reportes de instalación DataCom.
Requiere: reportlab
"""
import io
from datetime import datetime, timezone

def generate_facility_pdf(facility) -> bytes:
    """
    Genera un reporte PDF completo de una instalación finalizada.
    Diseño DataCom V1.0
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm, cm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, KeepTogether
        )
        from reportlab.lib.colors import HexColor
    except ImportError:
        raise ImportError("Instale reportlab: pip install reportlab==4.1.0")

    # ─── Paleta de colores DataCom ───────────────────────────────────────────
    COLOR_PRIMARY    = HexColor("#0A2D6E")  # Azul corporativo
    COLOR_SECONDARY  = HexColor("#00AEEF")  # Azul claro
    COLOR_ACCENT     = HexColor("#F7941D")  # Naranja DataCom
    COLOR_BG_HEADER  = HexColor("#0A2D6E")
    COLOR_BG_ROW_ALT = HexColor("#EFF6FF")
    COLOR_BORDER     = HexColor("#DBEAFE")
    COLOR_TEXT_LIGHT = HexColor("#FFFFFF")
    COLOR_TEXT_DARK  = HexColor("#1E293B")
    COLOR_TEXT_SUB   = HexColor("#64748B")
    COLOR_SUCCESS    = HexColor("#059669")
    COLOR_WARNING    = HexColor("#D97706")

    buffer = io.BytesIO()
    PAGE_W, PAGE_H = A4

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=2*cm,
        title=f"Reporte Instalación {facility.codigo_instalacion}",
        author="Sistema DATALIVE — DataCom"
    )

    styles = getSampleStyleSheet()

    # Estilos personalizados
    def style(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    sTitle      = style("sTitle",      fontSize=20, textColor=COLOR_TEXT_LIGHT, alignment=TA_LEFT, leading=24, fontName="Helvetica-Bold")
    sSubtitle   = style("sSubtitle",   fontSize=10, textColor=COLOR_SECONDARY,  alignment=TA_LEFT, leading=14)
    sSectionH   = style("sSectionH",   fontSize=12, textColor=COLOR_PRIMARY,    fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4)
    sLabel      = style("sLabel",      fontSize=8,  textColor=COLOR_TEXT_SUB,   fontName="Helvetica-Bold")
    sValue      = style("sValue",      fontSize=10, textColor=COLOR_TEXT_DARK)
    sSmall      = style("sSmall",      fontSize=8,  textColor=COLOR_TEXT_SUB)
    sTableHead  = style("sTableHead",  fontSize=9,  textColor=COLOR_TEXT_LIGHT, fontName="Helvetica-Bold", alignment=TA_CENTER)
    sTableCell  = style("sTableCell",  fontSize=8,  textColor=COLOR_TEXT_DARK,  alignment=TA_LEFT)
    sFooter     = style("sFooter",     fontSize=7,  textColor=COLOR_TEXT_SUB,   alignment=TA_CENTER)

    story = []

    # ─── ENCABEZADO ─────────────────────────────────────────────────────────
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    header_data = [[
        Paragraph("<b>DataCom</b>", style("logoText", fontSize=22, textColor=COLOR_SECONDARY, fontName="Helvetica-Bold")),
        Paragraph(
            f"<b>REPORTE DE INSTALACIÓN</b><br/>"
            f"<font size='10' color='#00AEEF'>#{facility.codigo_instalacion}</font>",
            style("rTitle", fontSize=16, textColor=COLOR_TEXT_LIGHT, fontName="Helvetica-Bold", alignment=TA_RIGHT)
        ),
    ]]
    header_table = Table(header_data, colWidths=[8*cm, None])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_HEADER),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [COLOR_BG_HEADER]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("LEFTPADDING", (0, 0), (0, -1), 18),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 18),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    story.append(header_table)

    # Barra de estado
    estado = facility.estado.upper().replace("_", " ")
    estado_color = COLOR_SUCCESS if facility.estado == "finalizada" else COLOR_WARNING
    status_data = [[
        Paragraph(f"Estado: <b>{estado}</b>", style("statusStyle", fontSize=9, textColor=estado_color, fontName="Helvetica-Bold")),
        Paragraph(f"Generado: {now_str}", style("genStyle", fontSize=8, textColor=COLOR_TEXT_SUB, alignment=TA_RIGHT)),
    ]]
    status_table = Table(status_data, colWidths=[10*cm, None])
    status_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_ROW_ALT),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (0, -1), 18),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 18),
    ]))
    story.append(status_table)
    story.append(Spacer(1, 10))

    # ─── SECCIÓN 1: INFORMACIÓN GENERAL ─────────────────────────────────────
    story.append(Paragraph("1. Información General", sSectionH))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_BORDER, spaceAfter=6))

    cliente_nombre = "---"
    if facility.cliente:
        try:
            cliente_nombre = facility.cliente.nombre_cliente
        except Exception:
            pass

    tecnico_nombre = "---"
    if facility.tecnico:
        try:
            tecnico_nombre = facility.tecnico.username
        except Exception:
            pass

    vehiculo_info = "No asignado"
    if facility.vehiculo_id:
        try:
            from config.apps.inventory.models.vehicle import Vehicle
            v = Vehicle.objects(id=facility.vehiculo_id).first()
            if v:
                vehiculo_info = f"{getattr(v, 'marca', '')} {getattr(v, 'modelo', '')} | Placa: {v.placa}".strip()
        except Exception:
            vehiculo_info = facility.vehiculo_id

    f_prog = facility.fecha_programada.strftime("%d/%m/%Y") if facility.fecha_programada else "---"
    f_ini  = facility.fecha_inicio.strftime("%d/%m/%Y %H:%M") if facility.fecha_inicio else "---"
    f_fin  = facility.fecha_fin.strftime("%d/%m/%Y %H:%M") if facility.fecha_fin else "---"

    # Calcular duración
    duracion = "---"
    if facility.fecha_inicio and facility.fecha_fin:
        delta = facility.fecha_fin - facility.fecha_inicio
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m = rem // 60
        duracion = f"{h}h {m}min"

    info_data = [
        [Paragraph("Cliente", sLabel), Paragraph(cliente_nombre, sValue),
         Paragraph("Técnico Responsable", sLabel), Paragraph(tecnico_nombre, sValue)],
        [Paragraph("Vehículo", sLabel), Paragraph(vehiculo_info, sValue),
         Paragraph("Dirección", sLabel), Paragraph(getattr(facility, "direccion_instalacion", "") or "---", sValue)],
        [Paragraph("Fecha Programada", sLabel), Paragraph(f_prog, sValue),
         Paragraph("Fecha Inicio", sLabel), Paragraph(f_ini, sValue)],
        [Paragraph("Fecha Finalización", sLabel), Paragraph(f_fin, sValue),
         Paragraph("Duración Total", sLabel), Paragraph(duracion, sValue)],
    ]

    info_table = Table(info_data, colWidths=[4*cm, 7*cm, 4*cm, None])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, COLOR_BG_ROW_ALT]),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 8))

    if getattr(facility, "observaciones", None):
        story.append(Paragraph("Observaciones Generales", sLabel))
        story.append(Paragraph(facility.observaciones, sValue))
        story.append(Spacer(1, 4))

    # ─── SECCIÓN 2: EQUIPOS INSTALADOS ──────────────────────────────────────
    story.append(Spacer(1, 8))
    story.append(Paragraph("2. Equipos Instalados", sSectionH))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_BORDER, spaceAfter=6))

    items = facility.items_planificados or []
    if items:
        eq_headers = ["#", "Código", "Nombre / Descripción", "Serial", "Estado Final", "Destino"]
        eq_data = [[Paragraph(h, sTableHead) for h in eq_headers]]

        for idx, it in enumerate(items, 1):
            item_obj = None
            try:
                from config.apps.inventory.models.item import Item
                item_obj = Item.objects(id=it.get("item_id")).first()
            except Exception:
                pass

            codigo = item_obj.codigo if item_obj else it.get("item_id", "---")
            nombre = item_obj.nombre if item_obj else "---"
            serial = getattr(item_obj, "serial", "---") if item_obj else "---"
            estado_item = getattr(item_obj, "estado", "---") if item_obj else "---"
            destino = it.get("destino_final", "cliente").upper()
            destino_color = COLOR_SUCCESS if destino == "CLIENTE" else COLOR_PRIMARY

            eq_data.append([
                Paragraph(str(idx), sTableCell),
                Paragraph(codigo, sTableCell),
                Paragraph(nombre, sTableCell),
                Paragraph(str(serial) if serial else "---", sTableCell),
                Paragraph(estado_item, sTableCell),
                Paragraph(f"<b>{destino}</b>", style("destStyle", fontSize=8, textColor=destino_color, fontName="Helvetica-Bold")),
            ])

        eq_table = Table(eq_data, colWidths=[0.6*cm, 2.5*cm, 6*cm, 3*cm, 3*cm, 2*cm])
        eq_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_TEXT_LIGHT),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_ROW_ALT]),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(KeepTogether([eq_table]))
    else:
        story.append(Paragraph("No se registraron equipos en esta instalación.", sSmall))

    # ─── SECCIÓN 3: HERRAMIENTAS ─────────────────────────────────────────────
    story.append(Spacer(1, 10))
    story.append(Paragraph("3. Herramientas Utilizadas", sSectionH))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_BORDER, spaceAfter=6))

    herramientas = getattr(facility, "herramientas", []) or []
    if herramientas:
        h_headers = ["#", "Herramienta / Descripción", "Cantidad", "Observaciones"]
        h_data = [[Paragraph(h, sTableHead) for h in h_headers]]
        for idx, h in enumerate(herramientas, 1):
            h_data.append([
                Paragraph(str(idx), sTableCell),
                Paragraph(h.get("nombre", "---"), sTableCell),
                Paragraph(str(h.get("cantidad", 1)), sTableCell),
                Paragraph(h.get("observaciones", ""), sTableCell),
            ])
        h_table = Table(h_data, colWidths=[0.6*cm, 9*cm, 2*cm, None])
        h_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_SECONDARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_TEXT_LIGHT),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_ROW_ALT]),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(h_table)
    else:
        story.append(Paragraph("No se registraron herramientas.", sSmall))

    # ─── SECCIÓN 4: MATERIALES ───────────────────────────────────────────────
    story.append(Spacer(1, 10))
    story.append(Paragraph("4. Materiales / Consumibles", sSectionH))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_BORDER, spaceAfter=6))

    consumibles = facility.consumibles or []
    if consumibles:
        m_headers = ["#", "Material / Descripción", "Cantidad", "Unidad", "Observaciones"]
        m_data = [[Paragraph(h, sTableHead) for h in m_headers]]
        for idx, c in enumerate(consumibles, 1):
            m_data.append([
                Paragraph(str(idx), sTableCell),
                Paragraph(c.get("nombre", "---"), sTableCell),
                Paragraph(str(c.get("cantidad", "")), sTableCell),
                Paragraph(c.get("unidad", ""), sTableCell),
                Paragraph(c.get("observaciones", ""), sTableCell),
            ])
        m_table = Table(m_data, colWidths=[0.6*cm, 8*cm, 2*cm, 2*cm, None])
        m_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_SECONDARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_TEXT_LIGHT),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_ROW_ALT]),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(m_table)
    else:
        story.append(Paragraph("No se registraron materiales consumibles.", sSmall))

    # ─── SECCIÓN 5: HISTORIAL DE MOVIMIENTOS ────────────────────────────────
    story.append(Spacer(1, 10))
    story.append(Paragraph("5. Historial de Movimientos", sSectionH))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_BORDER, spaceAfter=6))

    try:
        from config.apps.inventory.models.movement import Movement
        item_ids = [it.get("item_id") for it in items if it.get("item_id")]
        movements = Movement.objects(item__in=item_ids).order_by("fecha") if item_ids else []

        if movements:
            mv_headers = ["Ítem", "Estado Anterior", "Estado Nuevo", "Responsable", "Fecha/Hora"]
            mv_data = [[Paragraph(h, sTableHead) for h in mv_headers]]
            for mv in movements:
                try:
                    item_nm = mv.item.codigo if mv.item else "---"
                except Exception:
                    item_nm = "---"
                resp = mv.responsable.username if mv.responsable else "---"
                try:
                    resp = mv.responsable.username
                except Exception:
                    resp = "---"
                mv_data.append([
                    Paragraph(item_nm, sTableCell),
                    Paragraph(mv.origen.get("estado", "---") if mv.origen else "---", sTableCell),
                    Paragraph(mv.destino.get("estado", "---") if mv.destino else "---", sTableCell),
                    Paragraph(resp, sTableCell),
                    Paragraph(mv.fecha.strftime("%d/%m/%Y %H:%M") if mv.fecha else "---", sTableCell),
                ])
            mv_table = Table(mv_data, colWidths=[3*cm, 4*cm, 4*cm, 3*cm, 4*cm])
            mv_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_TEXT_LIGHT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_ROW_ALT]),
                ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(KeepTogether([mv_table]))
        else:
            story.append(Paragraph("No se encontraron movimientos registrados.", sSmall))
    except Exception:
        story.append(Paragraph("No se pudo cargar el historial de movimientos.", sSmall))

    # ─── SECCIÓN 6: FIRMAS ───────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(Paragraph("6. Firmas y Conformidad", sSectionH))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_BORDER, spaceAfter=12))

    firma_data = [
        [
            Paragraph("___________________________", sValue),
            Paragraph("___________________________", sValue),
        ],
        [
            Paragraph(f"<b>Técnico Responsable</b><br/>{tecnico_nombre}", style("fLabel", fontSize=9, textColor=COLOR_TEXT_DARK, alignment=TA_CENTER)),
            Paragraph("<b>Firma del Cliente</b><br/>Nombre: ___________________", style("fLabel", fontSize=9, textColor=COLOR_TEXT_DARK, alignment=TA_CENTER)),
        ],
    ]
    firma_table = Table(firma_data, colWidths=[9*cm, 9*cm])
    firma_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(firma_table)

    # ─── PIE DE PÁGINA (via canvas callback) ────────────────────────────────
    def on_page(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(COLOR_TEXT_SUB)
        canvas_obj.drawString(1.5*cm, 1.2*cm, "DataCom — Sistema DATALIVE de Inventario")
        canvas_obj.drawRightString(
            PAGE_W - 1.5*cm,
            1.2*cm,
            f"Generado: {now_str}  |  Pág. {doc_obj.page}"
        )
        canvas_obj.setStrokeColor(COLOR_SECONDARY)
        canvas_obj.setLineWidth(1.5)
        canvas_obj.line(1.5*cm, 1.5*cm, PAGE_W - 1.5*cm, 1.5*cm)
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buffer.seek(0)
    return buffer.read()
