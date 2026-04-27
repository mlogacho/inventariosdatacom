"""
Vista de Detalle de Instalación.
Sigue el patrón de category_item_view: la estructura exterior se construye
síncronamente; solo los slots interiores se actualizan desde el hilo de carga.
"""
import flet as ft
import threading
import os
import tempfile
import requests as _requests

from core.api_client import APIClient
from core.session import Session
from core.theme import ThemeColors, JetBrainsTheme
from components.status_badge import status_badge
from services.facility_service import (
    get_facility,
    start_facility,
    finish_facility,
    update_destinations,
    get_facility_movements,
    update_facility,
)
from services.item_service import transition_item, list_items


def show_snack(page, msg, is_error=False):
    page.snack_bar = ft.SnackBar(
        ft.Text(msg, color=ft.colors.WHITE, weight="bold"),
        bgcolor=ft.colors.RED_700 if is_error else ft.colors.GREEN_700,
        duration=3000,
    )
    page.snack_bar.open = True
    page.update()


def facility_detail_view(page: ft.Page, navigate, facility_id=None):
    if not facility_id:
        facility_id = page.session.get("facility_detail_id")

    if not facility_id:
        navigate("facilities")
        return ft.Container()

    state = {
        "facility":     {},
        "movements":    [],
        "destinations": {},
    }

    # ─── Slots síncronos (se actualizan desde el hilo) ───────────────────────
    loading_bar = ft.ProgressBar(visible=True, color=ThemeColors.ACCENT_BLUE)

    header_slot = ft.Column(
        controls=[],
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    sections_slot = ft.Column(
        controls=[
            ft.Container(height=20),
            ft.Text("Cargando detalles de la instalación...", color=ThemeColors.TEXT_SECONDARY, size=14)
        ],
        spacing=25,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # ─── Helpers de Diseño ───────────────────────────────────────────────────
    def section_card(title, icon, content, badge_text=None, actions=None):
        """Versión robusta de la tarjeta de sección con estilo JetBrains."""
        
        # Cabecera de la sección
        header_items = [
            ft.Icon(icon, color=ThemeColors.ACCENT_BLUE, size=22),
            ft.Text(title.upper(), size=14, weight="bold", color=ThemeColors.TEXT_PRIMARY),
        ]
        
        if badge_text:
            header_items.append(
                ft.Container(
                    content=ft.Text(badge_text, size=10, weight="bold", color=ft.colors.WHITE),
                    bgcolor=ThemeColors.ACCENT_BLUE,
                    padding=ft.padding.symmetric(horizontal=8, vertical=2),
                    border_radius=8
                )
            )
            
        header_items.append(ft.Container(expand=True))
        
        if actions:
            header_items.append(actions)

        main_header = ft.Row(header_items, spacing=12, vertical_alignment="center")

        return ft.Container(
            **JetBrainsTheme.card_style(),
            width=1050, 
            content=ft.Column([
                main_header,
                ft.Divider(height=10, color=ft.colors.with_opacity(0.05, ft.colors.WHITE)),
                ft.Container(content=content, padding=ft.padding.only(top=10)),
            ], spacing=10),
        )

    def data_item(label, value, icon):
        return ft.Column([
            ft.Row([
                ft.Icon(icon, size=14, color=ThemeColors.ACCENT_BLUE),
                ft.Text(label, size=11, color=ThemeColors.TEXT_SECONDARY, weight="bold"),
            ], spacing=8),
            ft.Text(str(value) if value else "—", size=15, color=ft.colors.WHITE, weight="w500"),
        ], spacing=4, expand=True)

    # ─── Constructores de Sección ────────────────────────────────────────────
    def build_general(f):
        cliente  = f.get("cliente") or {}
        tecnico  = f.get("tecnico") or {}
        vehiculo = f.get("vehiculo") or {}
        veh_id   = f.get("vehiculo_id") or "No asignado"
        if isinstance(vehiculo, dict) and vehiculo.get("marca"):
            veh_str = f"{vehiculo.get('marca','')} {vehiculo.get('modelo','')} ({vehiculo.get('placa','')})"
        else:
            veh_str = f"ID: {veh_id}" if veh_id != "No asignado" else "No asignado"

        return section_card("Información del Servicio", ft.icons.INFO_ROUNDED, ft.Column([
            ft.Row([
                data_item("CLIENTE",  cliente.get("nombre_cliente"), ft.icons.BUSINESS),
                data_item("TÉCNICO",  tecnico.get("username"),       ft.icons.PERSON),
                data_item("VEHÍCULO", veh_str,                       ft.icons.DIRECTIONS_CAR),
            ], spacing=30),
            ft.Row([
                data_item("DIRECCIÓN",    f.get("direccion_instalacion"), ft.icons.LOCATION_ON),
                data_item("PROGRAMADA",   (f.get("fecha_programada") or "")[:10], ft.icons.EVENT),
                data_item("INICIO REAL",  (f.get("fecha_inicio") or "")[:10],     ft.icons.PLAY_CIRCLE_FILL),
            ], spacing=30),
            ft.TextField(
                label="OBSERVACIONES",
                value=f.get("observaciones", ""),
                multiline=True,
                min_lines=2,
                read_only=(f.get("estado") in ("finalizada", "cancelada")),
                **JetBrainsTheme.input_style(),
            ),
        ], spacing=20))

    def build_assets(f, estado):
        items       = f.get("items_planificados", [])
        is_editable = (estado == "en_proceso")
        rows        = []

        for it in items:
            idata    = it.get("item") or it
            iid      = str(it.get("item_id") or idata.get("id", ""))
            curr_dest = state["destinations"].get(iid, "cliente")

            dest_widget = (
                ft.Dropdown(
                    value=curr_dest,
                    options=[ft.dropdown.Option("cliente", "CLIENTE"), ft.dropdown.Option("bodega", "BODEGA")],
                    width=130, height=35, text_size=11,
                    on_change=lambda e, _id=iid: handle_dest_change(_id, e.control.value),
                    **JetBrainsTheme.input_style()
                ) if is_editable else ft.Container(
                    content=ft.Text("CLIENTE" if curr_dest == "cliente" else "BODEGA",
                                    size=11, weight="bold", color=ThemeColors.ACCENT_BLUE),
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    border_radius=8,
                    border=ft.border.all(1, ThemeColors.ACCENT_BLUE),
                )
            )

            row_controls = [
                ft.Icon(ft.icons.DEVICES_OTHER_ROUNDED, color=ThemeColors.ACCENT_BLUE, size=24),
                ft.Column([
                    ft.Text(idata.get("nombre", "Equipo"), weight="bold", size=16),
                    ft.Row([
                        ft.Text(f"SKU: {idata.get('codigo','—')}", size=11, color=ThemeColors.TEXT_SECONDARY),
                        ft.Text("•", color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(f"SN: {idata.get('serial','—')}", size=11, color=ThemeColors.TEXT_SECONDARY),
                        ft.Text("•", color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(f"CATEGORÍA: {idata.get('categoria','—')}", size=11, color=ThemeColors.TEXT_SECONDARY),
                    ], spacing=6),
                ], expand=True),
                status_badge(idata.get("estado", "STOCK")),
                ft.VerticalDivider(width=20, color=ft.colors.TRANSPARENT),
                ft.Column([
                    ft.Text("DESTINO", size=9, weight="bold", color=ThemeColors.TEXT_SECONDARY),
                    dest_widget,
                ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ]

            if estado in ("planificada", "en_proceso"):
                row_controls.insert(-2, ft.IconButton(
                    ft.icons.DELETE_OUTLINE_ROUNDED, icon_color=ft.colors.RED_400,
                    tooltip="Quitar equipo",
                    on_click=lambda e, _id=iid, _st=idata.get("estado"): handle_remove_resource(_id, "equipo", _st),
                ))

            rows.append(ft.Container(
                bgcolor=ft.colors.with_opacity(0.05, ft.colors.BLACK),
                padding=20, border_radius=15,
                border=ft.border.all(1, ft.colors.with_opacity(0.05, ft.colors.WHITE)),
                content=ft.Row(row_controls, spacing=15),
            ))

        if not items:
            rows = [ft.Text("No se encontraron ítems vinculados.", italic=True, color=ThemeColors.TEXT_SECONDARY)]

        actions = None
        if estado in ("planificada", "en_proceso"):
            actions = ft.TextButton("AGREGAR EQUIPO", icon=ft.icons.ADD_CIRCLE_OUTLINE,
                                    on_click=lambda _: handle_add_resource("equipo"))

        return section_card("Equipos", ft.icons.INVENTORY_ROUNDED,
                            ft.Column(rows, spacing=10), str(len(items)), actions=actions)

    def build_tools(f):
        tools  = f.get("herramientas", [])
        estado = f.get("estado")
        rows   = []
        for t in tools:
            iid = str(t.get("item_id", ""))
            row_controls = [
                ft.Icon(ft.icons.BUILD_ROUNDED, color="#FF8F00", size=24),
                ft.Column([
                    ft.Text(t.get("nombre", "Herramienta"), weight="bold", size=16),
                    ft.Row([
                        ft.Text(f"CÓDIGO: {t.get('codigo','—')}", size=11, color=ThemeColors.TEXT_SECONDARY),
                        ft.Text("•", color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(f"CANTIDAD: {t.get('cantidad', 1)}", size=11, color=ThemeColors.TEXT_SECONDARY),
                    ], spacing=6),
                ], expand=True),
                status_badge(t.get("estado", "EN_USO")),
            ]
            if estado in ("planificada", "en_proceso"):
                row_controls.append(ft.IconButton(
                    ft.icons.DELETE_OUTLINE_ROUNDED, icon_color=ft.colors.RED_400,
                    tooltip="Quitar herramienta",
                    on_click=lambda e, _id=iid, _st=t.get("estado"): handle_remove_resource(_id, "herramienta", _st),
                ))
            rows.append(ft.Container(
                bgcolor=ft.colors.with_opacity(0.05, ft.colors.BLACK),
                padding=20, border_radius=15,
                border=ft.border.all(1, ft.colors.with_opacity(0.05, ft.colors.WHITE)),
                content=ft.Row(row_controls, spacing=15),
            ))

        if not tools:
            rows = [ft.Text("No hay herramientas asignadas.", italic=True, color=ThemeColors.TEXT_SECONDARY)]

        actions = None
        if estado in ("planificada", "en_proceso"):
            actions = ft.TextButton("AGREGAR HERRAMIENTA", icon=ft.icons.ADD_CIRCLE_OUTLINE,
                                    on_click=lambda _: handle_add_resource("herramienta"))

        return section_card("Herramientas", ft.icons.HANDYMAN_ROUNDED,
                            ft.Column(rows, spacing=10), str(len(tools)), actions=actions)

    def build_materials(f):
        cons   = f.get("consumibles", [])
        estado = f.get("estado")
        rows   = []
        for c in cons:
            iid = str(c.get("item_id", ""))
            row_controls = [
                ft.Icon(ft.icons.INVENTORY_2_ROUNDED, color=ThemeColors.STATE_STOCK, size=24),
                ft.Column([
                    ft.Text(c.get("nombre", "Material"), weight="bold", size=16),
                    ft.Row([
                        ft.Text(f"CÓDIGO: {c.get('codigo','—')}", size=11, color=ThemeColors.TEXT_SECONDARY),
                        ft.Text("•", color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(f"CANTIDAD: {c.get('cantidad', 1)} {c.get('unidad','')}", size=11, color=ThemeColors.TEXT_SECONDARY),
                    ], spacing=6),
                ], expand=True),
            ]
            if estado in ("planificada", "en_proceso"):
                row_controls.append(ft.IconButton(
                    ft.icons.DELETE_OUTLINE_ROUNDED, icon_color=ft.colors.RED_400,
                    tooltip="Quitar material",
                    on_click=lambda e, _id=iid: handle_remove_resource(_id, "material", "RESERVADO"),
                ))
            rows.append(ft.Container(
                bgcolor=ft.colors.with_opacity(0.05, ft.colors.BLACK),
                padding=20, border_radius=15,
                border=ft.border.all(1, ft.colors.with_opacity(0.05, ft.colors.WHITE)),
                content=ft.Row(row_controls, spacing=15),
            ))

        if not cons:
            rows = [ft.Text("No hay materiales asignados.", italic=True, color=ThemeColors.TEXT_SECONDARY)]

        actions = None
        if estado in ("planificada", "en_proceso"):
            actions = ft.TextButton("AGREGAR MATERIAL", icon=ft.icons.ADD_CIRCLE_OUTLINE,
                                    on_click=lambda _: handle_add_resource("material"))

        return section_card("Materiales / Consumibles", ft.icons.LAYERS_ROUNDED,
                            ft.Column(rows, spacing=10), str(len(cons)), actions=actions)

    def build_summary(f):
        # Asegurar que f sea un diccionario
        if not isinstance(f, dict):
            return ft.Text("Error: Datos de instalación no válidos", color="red")
            
        # Obtener listas de forma segura
        items = f.get("items_planificados") or []
        tools = f.get("herramientas") or []
        cons  = f.get("consumibles") or []
        
        n_items = len(items)
        n_tools = len(tools)
        n_cons  = len(cons)
        total   = n_items + n_tools + n_cons

        # Contenedor de filas de resumen
        summary_rows = ft.Column([
            ft.Row([
                ft.Icon(ft.icons.DEVICES_OTHER_ROUNDED, color=ThemeColors.ACCENT_BLUE, size=20),
                ft.Text("Equipos", size=14, weight="w500", expand=True),
                ft.Container(
                    content=ft.Text(str(n_items), size=12, weight="bold", color=ft.colors.WHITE),
                    bgcolor=ThemeColors.ACCENT_BLUE,
                    padding=ft.padding.symmetric(horizontal=12, vertical=4),
                    border_radius=15
                )
            ]),
            ft.Row([
                ft.Icon(ft.icons.HANDYMAN_ROUNDED, color="#FF8F00", size=20),
                ft.Text("Herramientas", size=14, weight="w500", expand=True),
                ft.Container(
                    content=ft.Text(str(n_tools), size=12, weight="bold", color=ft.colors.WHITE),
                    bgcolor="#FF8F00",
                    padding=ft.padding.symmetric(horizontal=12, vertical=4),
                    border_radius=15
                )
            ]),
            ft.Row([
                ft.Icon(ft.icons.INVENTORY_2_ROUNDED, color=ThemeColors.STATE_STOCK, size=20),
                ft.Text("Materiales / Consumibles", size=14, weight="w500", expand=True),
                ft.Container(
                    content=ft.Text(str(n_cons), size=12, weight="bold", color=ft.colors.WHITE),
                    bgcolor=ThemeColors.STATE_STOCK,
                    padding=ft.padding.symmetric(horizontal=12, vertical=4),
                    border_radius=15
                )
            ]),
        ], spacing=15)

        footer = ft.Container(
            margin=ft.padding.only(top=10),
            padding=ft.padding.only(top=15),
            border=ft.border.only(top=ft.BorderSide(1, ft.colors.with_opacity(0.1, ft.colors.WHITE))),
            content=ft.Row([
                ft.Text("Total de ítems seleccionados", size=15, weight="bold", expand=True),
                ft.Text(str(total), size=20, weight="bold", color=ThemeColors.ACCENT_BLUE)
            ])
        )

        content = ft.Column([
            summary_rows,
            footer if total > 0 else ft.Text("No hay recursos seleccionados para esta instalación.", 
                                            size=13, color=ThemeColors.TEXT_SECONDARY, italic=True)
        ], spacing=0)

        return section_card(
            "Resumen de Recursos",
            ft.icons.ANALYTICS_OUTLINED,
            content
        )

    def build_history(movs):
        rows = []
        for m in movs:
            item   = m.get("item") or {}
            iname  = item.get("nombre", "—") if isinstance(item, dict) else str(item)
            est_ant = (m.get("estado_anterior") or {}).get("estado", "—")
            est_nue = (m.get("estado_nuevo") or {}).get("estado", "—")
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(iname, size=12, weight="bold")),
                ft.DataCell(ft.Text(m.get("tipo_movimiento", "—"), size=11, color=ThemeColors.ACCENT_BLUE)),
                ft.DataCell(status_badge(est_ant)),
                ft.DataCell(ft.Row([ft.Icon(ft.icons.ARROW_FORWARD, size=12), status_badge(est_nue)], spacing=5)),
                ft.DataCell(ft.Text((m.get("fecha") or "")[:16].replace("T", " "), size=11, color=ThemeColors.TEXT_SECONDARY)),
            ]))

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ÍTEM", size=11, weight="bold")),
                ft.DataColumn(ft.Text("ACCIÓN", size=11, weight="bold")),
                ft.DataColumn(ft.Text("ORIGEN", size=11, weight="bold")),
                ft.DataColumn(ft.Text("DESTINO", size=11, weight="bold")),
                ft.DataColumn(ft.Text("FECHA", size=11, weight="bold")),
            ],
            rows=rows,
            heading_row_height=50,
            data_row_min_height=50,
            column_spacing=20,
        )
        return section_card("Historial de Movimientos", ft.icons.HISTORY,
                            ft.Column([table], scroll=ft.ScrollMode.AUTO))

    # ─── Handlers ────────────────────────────────────────────────────────────
    def handle_remove_resource(iid, category, current_state):
        def on_confirm(ev):
            # 1. ACTUALIZACIÓN OPTIMISTA (UI Local inmediata)
            f = state["facility"]
            if category == "equipo":
                f["items_planificados"] = [it for it in (f.get("items_planificados") or []) if str(it.get("item_id") or it.get("id")) != iid]
            elif category == "herramienta":
                f["herramientas"] = [it for it in (f.get("herramientas") or []) if str(it.get("item_id") or it.get("id")) != iid]
            elif category == "material":
                f["consumibles"] = [it for it in (f.get("consumibles") or []) if str(it.get("item_id") or it.get("id")) != iid]
            
            # Cerrar diálogo y refrescar UI de forma instantánea usando el nuevo render_ui
            page.dialog.open = False
            render_ui() 
            
            # 2. PROCESO BACKEND EN SEGUNDO PLANO
            def bg_process():
                try:
                    target_state = "STOCK"
                    if category == "equipo" and current_state == "SALIDA_INSTALACION":
                        target_state = "REINGRESO_BODEGA"
                    
                    # Llamada al backend
                    transition_item(
                        iid, 
                        target_state, 
                        ot_id=state["facility"].get("codigo_instalacion"), 
                        notes=f"Quitado de instalación {facility_id}"
                    )
                    
                    # 3. RECARGAR DATOS COMPLETOS (esto traerá el historial real)
                    load_data()
                    show_snack(page, f"Recurso quitado y enviado a {target_state}.")
                except Exception as ex:
                    show_snack(page, f"Error al procesar eliminación: {ex}", True)
                    load_data() # Revertir al estado real en caso de fallo
            
            threading.Thread(target=bg_process, daemon=True).start()

        page.dialog = ft.AlertDialog(
            title=ft.Text("Confirmar Eliminación"),
            content=ft.Text(f"¿Deseas quitar este {category} y devolverlo a STOCK?"),
            actions=[
                ft.TextButton("CANCELAR", on_click=lambda _: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("SÍ, QUITAR", bgcolor=ft.colors.RED_400, on_click=on_confirm),
            ],
        )
        page.dialog.open = True
        page.update()

    def handle_add_resource(category):
        try:
            tipo_map = {"equipo": "equipo", "herramienta": "herramienta", "material": "material"}
            # Obtener items en STOCK inmediatamente
            items = list_items({"estado": "STOCK", "tipo_item": tipo_map[category]})
            
            if not isinstance(items, list):
                items = []

            if not items:
                show_snack(page, f"No hay {category}s disponibles en STOCK.", True)
                return

            # Proporción Áurea (Phi ≈ 1.618)
            W = 850
            H = 525 # W / 1.618 approx
            L_W = 525 # Parte mayor (Sección de Selección)
            R_W = 325 # Parte menor (Sección de Detalles/Preview)

            # Slot para el preview del ítem seleccionado
            preview_slot = ft.Column(
                controls=[
                    ft.Icon(ft.icons.IMAGE_SEARCH_ROUNDED, size=64, color=ft.colors.with_opacity(0.2, ft.colors.WHITE)),
                    ft.Text("Selecciona un ítem\npara ver detalles", text_align="center", color=ThemeColors.TEXT_SECONDARY)
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=15
            )

            def update_preview(iid):
                it = next((x for x in items if str(x["id"]) == iid), None)
                if it:
                    preview_slot.controls.clear()
                    preview_slot.controls.extend([
                        ft.Icon(ft.icons.INVENTORY_ROUNDED, size=48, color=ThemeColors.ACCENT_BLUE),
                        ft.Text(it.get("nombre", "").upper(), weight="bold", size=16, text_align="center"),
                        ft.Divider(color=ft.colors.with_opacity(0.1, ft.colors.WHITE)),
                        ft.Column([
                            ft.Text(f"CÓDIGO: {it.get('codigo','—')}", size=11, color=ThemeColors.TEXT_SECONDARY),
                            ft.Text(f"SERIAL: {it.get('serial','—')}", size=11, color=ThemeColors.TEXT_SECONDARY),
                            ft.Text(f"CATEGORÍA: {it.get('categoria','—')}", size=11, color=ThemeColors.TEXT_SECONDARY),
                            ft.Text(f"STOCK: {it.get('cantidad', 1)} unidades", size=11, color=ThemeColors.ACCENT_BLUE, weight="bold"),
                        ], spacing=5)
                    ])
                    preview_slot.update()

            options = [
                ft.dropdown.Option(
                    key=str(it["id"]), 
                    text=f"{it.get('nombre')} [{it.get('codigo')}]"
                ) for it in items
            ]

            item_dropdown = ft.Dropdown(
                label=f"Elegir {category.capitalize()}",
                options=options,
                hint_text="Despliega para ver opciones...",
                width=L_W - 60,
                on_change=lambda e: update_preview(e.control.value),
                **JetBrainsTheme.input_style()
            )

            def add_this(it):
                try:
                    f_data = state["facility"]
                    if category == "equipo":
                        f_data["items_planificados"].append({"item_id": str(it["id"]), "store_id": "PRINCIPAL", "destino_final": "cliente"})
                    elif category == "herramienta":
                        f_data["herramientas"].append({"item_id": str(it["id"]), "cantidad": 1})
                    elif category == "material":
                        f_data["consumibles"].append({"item_id": str(it["id"]), "cantidad": 1, "cantidad_reservada": 1})
                    
                    update_facility(facility_id, f_data)
                    page.dialog.open = False
                    show_snack(page, f"{category.capitalize()} añadido con éxito.")
                    state["loading"] = True
                    page.update()
                    load_data()
                except Exception as ex:
                    show_snack(page, f"Error: {ex}", True)

            def on_add_confirm(e):
                if not item_dropdown.value:
                    show_snack(page, "Por favor, selecciona un ítem de la lista.", True)
                    return
                selected_it = next((it for it in items if str(it["id"]) == item_dropdown.value), None)
                if selected_it:
                    add_this(selected_it)

            # Layout basado en Proporción Áurea
            golden_layout = ft.Row([
                # Panel Izquierdo (Selección)
                ft.Container(
                    content=ft.Column([
                        ft.Text("RECURSOS DISPONIBLES", size=12, weight="bold", color=ThemeColors.ACCENT_BLUE),
                        ft.Text("Selecciona el elemento que deseas asignar a esta orden de trabajo.", size=13, color=ThemeColors.TEXT_SECONDARY),
                        ft.Container(height=10),
                        item_dropdown,
                    ], spacing=15),
                    width=L_W,
                    padding=30,
                    border=ft.border.only(right=ft.BorderSide(1, ft.colors.with_opacity(0.1, ft.colors.WHITE)))
                ),
                # Panel Derecho (Preview)
                ft.Container(
                    content=preview_slot,
                    width=R_W,
                    padding=30,
                    alignment=ft.alignment.center
                )
            ], spacing=0, vertical_alignment="stretch")

            page.dialog = ft.AlertDialog(
                content_padding=0,
                content=ft.Container(
                    content=golden_layout,
                    width=W,
                    height=H,
                    bgcolor=ThemeColors.BG_SURFACE,
                    border_radius=20,
                ),
                actions=[
                    ft.TextButton("CANCELAR", on_click=lambda _: setattr(page.dialog, "open", False) or page.update()),
                    ft.ElevatedButton("CONFIRMAR ASIGNACIÓN", bgcolor=ThemeColors.ACCENT_BLUE, color=ft.colors.WHITE, on_click=on_add_confirm, height=45),
                ],
                actions_padding=20,
            )
            page.dialog.open = True
            page.update()
        except Exception as e:
            show_snack(page, f"Error al cargar recursos: {e}", True)

    def handle_dest_change(iid, val):
        state["destinations"][iid] = val
        payload = [{"item_id": k, "destino": v} for k, v in state["destinations"].items()]
        threading.Thread(target=lambda: update_destinations(facility_id, payload), daemon=True).start()

    def handle_start(e):
        def go(ev):
            try:
                start_facility(facility_id)
                page.dialog.open = False
                navigate("facility_detail", facility_id=facility_id)
            except Exception as ex:
                show_snack(page, f"Error: {ex}", True)
        page.dialog = ft.AlertDialog(
            title=ft.Text("Confirmar Inicio"),
            content=ft.Text("¿Deseas iniciar la instalación?"),
            actions=[
                ft.TextButton("NO", on_click=lambda _: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("SÍ, INICIAR", bgcolor=ThemeColors.STATE_DISPATCH, on_click=go),
            ],
        )
        page.dialog.open = True
        page.update()

    def handle_finish(e):
        def go(ev):
            page.dialog.open = False
            page.update()
            try:
                payload = [{"item_id": k, "destino": v} for k, v in state["destinations"].items()]
                finish_facility(facility_id, payload)
                navigate("facility_detail", facility_id=facility_id)
            except Exception as ex:
                show_snack(page, f"Error: {ex}", True)
        page.dialog = ft.AlertDialog(
            title=ft.Text("Finalizar"),
            content=ft.Text("¿Confirmas la finalización?"),
            actions=[
                ft.TextButton("NO", on_click=lambda _: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("CONFIRMAR", bgcolor=ThemeColors.STATE_INSTALLED, on_click=go),
            ],
        )
        page.dialog.open = True
        page.update()

    def handle_pdf(_):
        def do_download():
            try:
                show_snack(page, "Generando reporte PDF...")
                url  = f"http://localhost:8000/api/inventory/facilities/{facility_id}/report/"
                resp = _requests.get(url, headers={"Authorization": f"Bearer {Session.token}"}, timeout=30)
                resp.raise_for_status()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="instalacion_") as tmp:
                    tmp.write(resp.content)
                    tmp_path = tmp.name
                os.startfile(tmp_path)
            except Exception as ex:
                show_snack(page, f"Error al generar PDF: {ex}", True)
        threading.Thread(target=do_download, daemon=True).start()

    # ─── Carga de Datos ──────────────────────────────────────────────────────
    def render_ui():
        f = state["facility"]
        if not f: return
        
        estado = f.get("estado", "planificada")
        
        # Botones del header
        btns = []
        if estado == "planificada":
            btns.append(ft.ElevatedButton("DAR INICIO", icon=ft.icons.PLAY_ARROW,
                                           bgcolor=ThemeColors.STATE_DISPATCH, on_click=handle_start, height=45))
        if estado == "en_proceso":
            btns.append(ft.ElevatedButton("FINALIZAR", icon=ft.icons.CHECK_CIRCLE,
                                           bgcolor=ThemeColors.STATE_INSTALLED, on_click=handle_finish, height=45))
        if estado == "finalizada":
            btns.append(ft.ElevatedButton("PDF REPORTE", icon=ft.icons.PICTURE_AS_PDF,
                                           bgcolor=ft.colors.RED_700, on_click=handle_pdf, height=45))

        header = ft.Container(
            bgcolor=ft.colors.with_opacity(0.08, ft.colors.WHITE),
            padding=25, border_radius=20, width=1050,
            content=ft.Row([
                ft.IconButton(ft.icons.CHEVRON_LEFT, on_click=lambda _: navigate("facilities"), icon_size=30),
                ft.Column([
                    ft.Text(f"INSTALACIÓN #{f.get('codigo_instalacion','—')}", size=22, weight="bold"),
                    status_badge(estado),
                ], spacing=2, expand=True),
                ft.Row(btns, spacing=15),
            ]),
        )

        def safe_build(func, *args):
            try:
                res = func(*args)
                return res if res is not None else ft.Container()
            except Exception as e:
                import traceback
                traceback.print_exc()
                return ft.Container(
                    padding=20,
                    bgcolor=ft.colors.with_opacity(0.1, ft.colors.RED_400),
                    border_radius=15,
                    width=1050,
                    content=ft.Text(f"Error en {func.__name__}: {e}", color=ft.colors.RED_400, weight="bold"),
                )

        # Poblar los slots
        header_slot.controls.clear()
        header_slot.controls.append(header)

        sections_slot.controls.clear()
        
        # Construir secciones
        sections = [
            (build_summary,   (f,)),
            (build_general,   (f,)),
            (build_assets,    (f, estado)),
            (build_tools,     (f,)),
            (build_materials, (f,)),
            (build_history,   (state["movements"],)),
        ]

        for func, args in sections:
            sections_slot.controls.append(safe_build(func, *args))
            sections_slot.controls.append(ft.Container(height=10)) 
            
        sections_slot.controls.append(ft.Container(height=50))
        loading_bar.visible = False
        page.update()

    # ─── Carga de Datos ──────────────────────────────────────────────────────
    def load_data():
        try:
            f = get_facility(facility_id)
            if not f:
                navigate("facilities")
                return
            state["facility"] = f
            state["movements"] = get_facility_movements(facility_id) or []
            for it in f.get("items_planificados", []):
                state["destinations"][str(it.get("item_id"))] = it.get("destino_final", "cliente")

            render_ui()

        except Exception as ex:
            import traceback
            traceback.print_exc()
            sections_slot.controls.clear()
            sections_slot.controls.append(
                ft.Container(
                    padding=40, width=1050,
                    content=ft.Column([
                        ft.Text("Error al cargar la instalación", size=18, weight="bold", color=ft.colors.RED_400),
                        ft.Text(str(ex), size=12, color=ThemeColors.TEXT_SECONDARY),
                        ft.ElevatedButton("Volver al listado", on_click=lambda _: navigate("facilities")),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
                )
            )
            loading_bar.visible = False
            page.update()

    # Iniciar carga con un pequeño delay para asegurar que el layout esté listo
    import threading
    threading.Timer(0.2, load_data).start()

    # ─── Layout estático (nunca se modifica, sigue el patrón de category_item_view) ─
    return ft.Column(
        [
            loading_bar,
            header_slot,
            sections_slot,
        ],
        expand=True,
        spacing=25,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
