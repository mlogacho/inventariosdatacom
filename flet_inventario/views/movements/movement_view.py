import flet as ft
import threading
import webbrowser
from core.theme import ThemeColors, JetBrainsTheme
from components.status_badge import status_badge
from components.stats_card import stats_card
from components.timeline import asset_timeline
from services.movement_service import list_movements, get_movement_stats, get_asset_history, download_movement_acta_pdf
from services.item_service import list_items
from services.store_service import list_stores

# Tipos de movimiento — sincronizados con backend OperationType.ALL
TIPO_MOVIMIENTO_OPTIONS = [
    ("TODOS",               "Todos los tipos"),
    ("ENTRADA",             "Entrada"),
    ("SALIDA",              "Salida"),
    ("AJUSTE",              "Ajuste"),
    ("TRANSFERENCIA",       "Transferencia"),
    ("BAJA",                "Baja / Obsoleto"),
    ("RESERVA",             "Reserva"),
    ("INSTALACION",         "Instalación"),
    ("RETORNO",             "Retorno"),
    ("SALIDA_HERRAMIENTA",  "Salida Herramienta"),
    ("RETORNO_HERRAMIENTA", "Retorno Herramienta"),
    ("CONSUMO",             "Consumo"),
    ("RETORNO_PARCIAL",     "Retorno Parcial"),
]

TIPO_COLOR = {
    "ENTRADA":             "#39ff14",
    "SALIDA":              "#ff4500",
    "AJUSTE":              "#007fff",
    "TRANSFERENCIA":       "#00ffff",
    "BAJA":                "#808080",
    "RESERVA":             "#ffbf00",
    "INSTALACION":         "#8a2be2",
    "RETORNO":             "#00ffff",
    "SALIDA_HERRAMIENTA":  "#ff7f50",
    "RETORNO_HERRAMIENTA": "#00ffff",
    "CONSUMO":             "#ff2400",
    "RETORNO_PARCIAL":     "#ffbf00",
}


def _tipo_chip(tipo: str) -> ft.Container:
    color = TIPO_COLOR.get(tipo, "#a0a0b0")
    label = tipo.replace("_", " ")
    return ft.Container(
        content=ft.Text(label, size=10, weight="bold", color=ft.colors.WHITE),
        bgcolor=ft.colors.with_opacity(0.18, color),
        border=ft.border.all(1, ft.colors.with_opacity(0.55, color)),
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
        border_radius=6,
    )


def movement_view(page: ft.Page, navigate, **kwargs):
    # =========================================================================
    # ESTADO Y VARIABLES
    # =========================================================================
    movements_data = []
    stats_data = {}
    selected_location = {"id": None, "name": None}
    SESSION_LOC_ID_KEY = "movements_location_id"
    SESSION_LOC_NAME_KEY = "movements_location_name"

    # ── Filtros ───────────────────────────────────────────────────────────────
    search_tf = ft.TextField(
        hint_text="Código, nombre o serie...",
        prefix_icon=ft.icons.SEARCH,
        expand=True,
        on_submit=lambda e: apply_filters(),
        **JetBrainsTheme.input_style()
    )

    tipo_dd = ft.Dropdown(
        label="Tipo de Movimiento",
        width=230,
        options=[
            ft.dropdown.Option(key=k, text=v)
            for k, v in TIPO_MOVIMIENTO_OPTIONS
        ],
        value="TODOS",
        **JetBrainsTheme.input_style()
    )

    cliente_tf = ft.TextField(
        label="Cliente",
        width=175,
        **JetBrainsTheme.input_style()
    )

    # ── Tabla de movimientos (DataTable con filas de mayor altura) ────────────
    table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("ACTIVO",       size=12, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("TIPO",         size=12, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("FLUJO",        size=12, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("RESPONSABLE",  size=12, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("FECHA",        size=12, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("",             size=12)),
        ],
        rows=[],
        heading_row_color=ft.colors.with_opacity(0.06, ft.colors.WHITE),
        heading_row_height=44,
        data_row_min_height=64,   # filas más altas → sin superposición
        data_row_max_height=80,
        column_spacing=24,
        expand=True,
        border_radius=8,
        border=ft.border.all(1, ft.colors.with_opacity(0.05, ft.colors.WHITE)),
    )

    # Label contador
    page_label = ft.Text("", size=12, color=ThemeColors.TEXT_SECONDARY)
    location_filter_label = ft.Text("", size=12, color=ThemeColors.ACCENT_BLUE, visible=False)
    clear_location_btn = ft.TextButton(
        "Quitar ubicación",
        visible=False,
        style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY),
    )

    stats_row = ft.Row(spacing=16, scroll="auto")
    compact_title = ft.Text("", size=14, weight="bold", color=ThemeColors.TEXT_PRIMARY)
    compact_total = ft.Text("", size=12, color=ThemeColors.TEXT_SECONDARY)
    compact_rows = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO)
    compact_panel = ft.Container(
        visible=False,
        height=260,
        **JetBrainsTheme.card_style(),
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.icons.MAP, color=ThemeColors.ACCENT_BLUE, size=18),
                compact_title,
                ft.Container(expand=True),
                compact_total,
                ft.IconButton(
                    icon=ft.icons.CLOSE,
                    tooltip="Cerrar vista compacta",
                    icon_color=ThemeColors.TEXT_SECONDARY,
                    on_click=lambda e: close_compact_panel(),
                ),
            ], alignment="spaceBetween"),
            ft.Divider(height=1, color=ft.colors.with_opacity(0.08, ft.colors.WHITE)),
            ft.Container(content=compact_rows, expand=True),
        ], spacing=8),
    )

    # Loader
    loading = ft.ProgressBar(visible=False, color=ThemeColors.ACCENT_BLUE)

    def show_snack(message: str, is_error: bool = False):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color=ft.colors.WHITE),
            bgcolor=ft.colors.RED_700 if is_error else ft.colors.GREEN_700,
            duration=4000,
        )
        page.snack_bar.open = True
        page.update()

    inventory_hint_title = ft.Text("Coincidencias en Inventario", size=14, weight="bold", color=ThemeColors.TEXT_PRIMARY)
    inventory_hint_rows = ft.Column(spacing=6)
    inventory_hint_panel = ft.Container(
        visible=False,
        **JetBrainsTheme.card_style(),
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.icons.INVENTORY_2, color=ThemeColors.ACCENT_BLUE, size=18),
                inventory_hint_title,
            ], spacing=8),
            inventory_hint_rows,
        ], spacing=8),
    )

    def close_compact_panel():
        compact_panel.visible = False
        page.update()

    # =========================================================================
    # ACCIONES
    # =========================================================================
    def load_stats():
        nonlocal stats_data
        try:
            stats_data = get_movement_stats()
            stats_row.controls = [
                stats_card("Activos Totales",
                           str(stats_data.get("total_items", 0)),
                           ft.icons.INVENTORY_2,
                           on_click=lambda e: open_items_by_location()),
                stats_card("En Stock",
                           str(stats_data.get("stats_by_state", {}).get("STOCK", 0)),
                           ft.icons.WAREHOUSE,
                           ThemeColors.STATE_STOCK,
                           on_click=lambda e: open_items_by_location("STOCK")),
                stats_card("Reservados",
                           str(stats_data.get("stats_by_state", {}).get("RESERVADO", 0)),
                           ft.icons.VPN_KEY,
                           ThemeColors.STATE_RESERVED),
                stats_card("Movimientos Hoy",
                           str(stats_data.get("movements_today", 0)),
                           ft.icons.SYNC_ALT,
                           ThemeColors.ACCENT_MAGENTA),
            ]
            page.update()
        except:
            pass

    def apply_filters(e=None):
        loading.visible = True
        inventory_hint_panel.visible = False
        inventory_hint_rows.controls = []
        page.update()

        params = {"page_size": 100}
        if search_tf.value:
            params["search"] = search_tf.value
        if tipo_dd.value and tipo_dd.value not in ("TODOS", ""):
            params["tipo_movimiento"] = tipo_dd.value
        if cliente_tf.value:
            params["cliente"] = cliente_tf.value
        if fecha_desde.value:
            params["fecha_desde"] = fecha_desde.value
        if fecha_hasta.value:
            params["fecha_hasta"] = fecha_hasta.value
        if selected_location["id"] is not None:
            params["ubicacion_id"] = selected_location["id"]

        try:
            data    = list_movements(params)
            results = []
            total   = 0
            if isinstance(data, dict):
                results = data.get("results", [])
                total   = data.get("pagination", {}).get("count", len(results))
            elif isinstance(data, list):
                results = data
                total   = len(results)

            # Apoyo de claridad: búsqueda paralela en inventario para mostrar
            # descripción/cantidad aun cuando no existan movimientos del código.
            search_value = (search_tf.value or "").strip()
            if search_value:
                try:
                    inv_matches = list_items({"search": search_value, "page_size": 10}) or []
                    if inv_matches:
                        inventory_hint_rows.controls = [
                            ft.Row([
                                ft.Text("Código", color=ThemeColors.TEXT_SECONDARY, weight="bold", width=170),
                                ft.Text("Descripción", color=ThemeColors.TEXT_SECONDARY, weight="bold", expand=True),
                                ft.Text("Stock", color=ThemeColors.TEXT_SECONDARY, weight="bold", width=80),
                                ft.Text("Estado", color=ThemeColors.TEXT_SECONDARY, weight="bold", width=120),
                            ])
                        ]

                        for inv in inv_matches[:8]:
                            inventory_hint_rows.controls.append(
                                ft.Container(
                                    padding=ft.padding.symmetric(horizontal=8, vertical=6),
                                    border_radius=8,
                                    bgcolor=ft.colors.with_opacity(0.04, ft.colors.WHITE),
                                    content=ft.Row([
                                        ft.Text(str(inv.get("codigo") or "---"), width=170, color=ThemeColors.ACCENT_BLUE, weight="bold"),
                                        ft.Text(str(inv.get("nombre") or "---"), expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(str(inv.get("cantidad") if inv.get("cantidad") is not None else 0), width=80),
                                        ft.Text(str(inv.get("estado") or "---"), width=120),
                                    ], spacing=10),
                                )
                            )

                        inventory_hint_title.value = "Coincidencias en Inventario"
                        inventory_hint_panel.visible = True
                except Exception as inv_ex:
                    print(f"Error consultando inventario para busqueda: {inv_ex}")

            table.rows.clear()

            if not results:
                table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(
                            "No se encontraron movimientos para este filtro",
                            italic=True,
                            color=ThemeColors.TEXT_SECONDARY
                        )),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                    ])
                )
            else:
                for m in results:
                    item      = m.get("item", {})
                    item_name = item.get("nombre", "Desconocido")
                    item_code = item.get("codigo", "---")
                    origen    = m.get("origen") if isinstance(m.get("origen"), dict) else {}
                    destino   = m.get("destino") if isinstance(m.get("destino"), dict) else {}
                    prev      = origen.get("nombre") or origen.get("estado", "INICIO")
                    new_state = destino.get("nombre") or destino.get("estado", "---")
                    tipo      = m.get("tipo_movimiento", "---")
                    module_source = str(m.get("module_source") or "").strip().upper()
                    if module_source == "ACTA_ENTREGA_RECEPCION":
                        receiver_name = destino.get("nombre") or destino.get("recibe_nombre") or new_state
                        new_state = f"DESCARGO A {receiver_name}"
                    resp_obj  = m.get("responsable", {})
                    resp      = (resp_obj.get("username", "---")
                                 if isinstance(resp_obj, dict) else str(resp_obj))
                    fecha_raw = m.get("fecha", "---")
                    fecha_str = (fecha_raw[:16].replace("T", " ")
                                 if len(fecha_raw) >= 16 else fecha_raw)
                    has_acta_pdf = bool(m.get("has_acta_pdf"))
                    movement_id = str(m.get("id") or "").strip()

                    def _download_acta(_e=None, current_movement_id=movement_id):
                        def _worker():
                            try:
                                show_snack("Descargando ACTA del movimiento...")
                                pdf_path = download_movement_acta_pdf(current_movement_id)
                                webbrowser.open(f"file://{pdf_path}")
                                show_snack(f"ACTA descargada en: {pdf_path}")
                            except Exception as ex:
                                show_snack(f"No se pudo descargar el ACTA: {ex}", True)

                        threading.Thread(target=_worker, daemon=True).start()

                    # Avatar inicial del responsable
                    avatar = ft.Container(
                        width=28, height=28, border_radius=14,
                        bgcolor=ft.colors.with_opacity(0.2, ThemeColors.ACCENT_BLUE),
                        alignment=ft.alignment.center,
                        content=ft.Text(
                            resp[0].upper() if resp and resp != "---" else "?",
                            size=11, weight="bold", color=ThemeColors.ACCENT_BLUE,
                        ),
                    )

                    table.rows.append(
                        ft.DataRow(
                            cells=[
                                # ── Activo ──────────────────────────────────
                                ft.DataCell(ft.Column([
                                    ft.Text(item_name, size=13, weight="bold",
                                            color=ThemeColors.TEXT_PRIMARY,
                                            max_lines=2,
                                            overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Container(
                                        content=ft.Text(item_code, size=10,
                                                        color=ThemeColors.ACCENT_BLUE,
                                                        weight="w500"),
                                        bgcolor=ft.colors.with_opacity(0.1, ThemeColors.ACCENT_BLUE),
                                        border_radius=4,
                                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                    ),
                                ], spacing=4, tight=True)),
                                # ── Tipo ────────────────────────────────────
                                ft.DataCell(_tipo_chip(tipo)),
                                # ── Flujo ───────────────────────────────────
                                ft.DataCell(ft.Row([
                                    ft.Container(
                                        content=ft.Text(
                                            prev.replace("_", " "), size=10,
                                            color=ThemeColors.TEXT_SECONDARY, weight="w500",
                                        ),
                                        bgcolor=ft.colors.with_opacity(0.06, ft.colors.WHITE),
                                        border=ft.border.all(1, ft.colors.with_opacity(0.1, ft.colors.WHITE)),
                                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                        border_radius=6,
                                    ),
                                    ft.Icon(ft.icons.ARROW_FORWARD_IOS,
                                            size=11, color=ThemeColors.ACCENT_BLUE),
                                    status_badge(new_state),
                                ], spacing=6)),
                                # ── Responsable ─────────────────────────────
                                ft.DataCell(ft.Row([
                                    avatar,
                                    ft.Text(resp, size=12, color=ThemeColors.TEXT_PRIMARY),
                                ], spacing=8)),
                                # ── Fecha ───────────────────────────────────
                                ft.DataCell(ft.Text(fecha_str, size=12,
                                                    color=ThemeColors.TEXT_PRIMARY)),
                                # ── Acción ──────────────────────────────────
                                ft.DataCell(ft.Row([
                                    ft.IconButton(
                                        icon=ft.icons.TIMELINE,
                                        icon_color=ThemeColors.ACCENT_BLUE,
                                        icon_size=20,
                                        tooltip="Ver Trazabilidad Completa",
                                        on_click=lambda e, it=item: navigate(
                                            "item_traceability",
                                            item_id=it["id"],
                                            item_data=it
                                        )
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.PICTURE_AS_PDF,
                                        icon_color=ThemeColors.ACCENT_BLUE if has_acta_pdf else ThemeColors.TEXT_SECONDARY,
                                        icon_size=20,
                                        tooltip="Descargar ACTA asociada" if has_acta_pdf else "Sin ACTA asociada",
                                        disabled=(not has_acta_pdf) or (not movement_id),
                                        on_click=_download_acta if has_acta_pdf and movement_id else None,
                                    ),
                                ], spacing=2)),
                            ]
                        )
                    )

            page_label.value = f"{len(results)} resultado(s)"
        except Exception as ex:
            print(f"Error cargando movimientos: {ex}")

        loading.visible = False
        page.update()

    # =========================================================================
    # DATE PICKERS
    # =========================================================================
    def on_date_from_change(e):
        fecha_desde.value = date_picker_from.value.strftime("%Y-%m-%d")
        page.update()

    def on_date_to_change(e):
        fecha_hasta.value = date_picker_to.value.strftime("%Y-%m-%d")
        page.update()

    date_picker_from = ft.DatePicker(on_change=on_date_from_change)
    date_picker_to   = ft.DatePicker(on_change=on_date_to_change)
    if date_picker_from not in page.overlay:
        page.overlay.extend([date_picker_from, date_picker_to])

    fecha_desde = ft.TextField(
        label="Desde", width=120, read_only=True,
        **JetBrainsTheme.input_style()
    )
    btn_desde = ft.IconButton(
        icon=ft.icons.CALENDAR_MONTH,
        icon_color=ThemeColors.ACCENT_BLUE,
        tooltip="Fecha inicio",
        on_click=lambda e: date_picker_from.pick_date()
    )
    fecha_hasta = ft.TextField(
        label="Hasta", width=120, read_only=True,
        **JetBrainsTheme.input_style()
    )
    btn_hasta = ft.IconButton(
        icon=ft.icons.CALENDAR_MONTH,
        icon_color=ThemeColors.ACCENT_BLUE,
        tooltip="Fecha fin",
        on_click=lambda e: date_picker_to.pick_date()
    )

    def reset_filters(e):
        search_tf.value   = ""
        tipo_dd.value     = "TODOS"
        cliente_tf.value  = ""
        fecha_desde.value = ""
        fecha_hasta.value = ""
        selected_location["id"] = None
        selected_location["name"] = None
        page.session.set(SESSION_LOC_ID_KEY, None)
        page.session.set(SESSION_LOC_NAME_KEY, None)
        location_filter_label.visible = False
        clear_location_btn.visible = False
        apply_filters()

    def select_location_filter(location_id, location_name):
        selected_location["id"] = location_id
        selected_location["name"] = location_name
        page.session.set(SESSION_LOC_ID_KEY, location_id)
        page.session.set(SESSION_LOC_NAME_KEY, location_name)
        location_filter_label.value = f"Ubicación: {location_name}"
        location_filter_label.visible = True
        clear_location_btn.visible = True
        compact_panel.visible = False
        apply_filters()

    def clear_location_filter(e=None):
        selected_location["id"] = None
        selected_location["name"] = None
        page.session.set(SESSION_LOC_ID_KEY, None)
        page.session.set(SESSION_LOC_NAME_KEY, None)
        location_filter_label.visible = False
        clear_location_btn.visible = False
        apply_filters()

    clear_location_btn.on_click = clear_location_filter

    def open_items_by_location(estado=None):
        loading.visible = True
        page.update()

        try:
            items = list_items({"estado": estado} if estado else {}) or []
            stores = list_stores() or []
            store_name_by_id = {
                str(s.get("id")): s.get("nombre_bodega", "Sin nombre")
                for s in stores
            }

            grouped = {}
            for item in items:
                loc_id = str(item.get("ubicacion_actual_id") or "")
                loc_name = store_name_by_id.get(loc_id, "Sin ubicación")
                key = loc_id if loc_id else "__none__"
                if key not in grouped:
                    grouped[key] = {"name": loc_name, "count": 0}
                grouped[key]["count"] += 1

            rows = sorted(grouped.items(), key=lambda x: x[1]["count"], reverse=True)
            compact_title.value = "Activos En Stock por Ubicación" if estado == "STOCK" else "Activos Totales por Ubicación"
            compact_total.value = f"{len(items)} activo(s)"
            compact_rows.controls = [
                ft.Row([
                    ft.Text("Ubicación", weight="bold", color=ThemeColors.TEXT_SECONDARY, expand=True),
                    ft.Text("Cantidad", weight="bold", color=ThemeColors.TEXT_SECONDARY),
                ])
            ]

            if rows:
                compact_rows.controls.extend([
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=8, vertical=6),
                        border_radius=8,
                        bgcolor=ft.colors.with_opacity(0.04, ft.colors.WHITE),
                        ink=True,
                        on_click=lambda e, loc_id=loc_id, loc_name=row["name"]: select_location_filter(loc_id, loc_name),
                        content=ft.Row([
                            ft.Text(row["name"], expand=True, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(str(row["count"]), weight="bold", color=ThemeColors.ACCENT_BLUE),
                        ]),
                    )
                    for loc_id, row in rows
                ])
            else:
                compact_rows.controls.append(
                    ft.Text("No hay activos para este criterio", italic=True, color=ThemeColors.TEXT_SECONDARY)
                )

            compact_panel.visible = True
        except Exception as ex:
            print(f"Error cargando activos por ubicacion: {ex}")
        finally:
            loading.visible = False
            page.update()

    # =========================================================================
    # BARRA DE FILTROS (una sola fila — compatible con Flet 0.19)
    # =========================================================================
    filter_bar = ft.Container(
        **JetBrainsTheme.card_style(),
        content=ft.Row([
            search_tf,
            tipo_dd,
            cliente_tf,
            ft.Row([fecha_desde, btn_desde], spacing=2),
            ft.Row([fecha_hasta, btn_hasta], spacing=2),
            ft.ElevatedButton(
                "Buscar",
                icon=ft.icons.SEARCH,
                style=JetBrainsTheme.primary_button_style(),
                on_click=apply_filters,
                height=45,
            ),
            ft.IconButton(
                ft.icons.FILTER_ALT_OFF,
                tooltip="Limpiar filtros",
                icon_color=ThemeColors.TEXT_SECONDARY,
                on_click=reset_filters,
            ),
        ], spacing=12),
    )

    # =========================================================================
    # INICIALIZACIÓN
    # =========================================================================
    saved_location_id = page.session.get(SESSION_LOC_ID_KEY)
    saved_location_name = page.session.get(SESSION_LOC_NAME_KEY)
    if saved_location_id:
        selected_location["id"] = saved_location_id
        selected_location["name"] = saved_location_name or "Ubicación"
        location_filter_label.value = f"Ubicación: {selected_location['name']}"
        location_filter_label.visible = True
        clear_location_btn.visible = True

    threading.Timer(0.1, load_stats).start()
    threading.Timer(0.2, apply_filters).start()

    compact_mode = str(kwargs.get("open_compact") or "").upper()
    if compact_mode == "STOCK":
        threading.Timer(0.25, lambda: open_items_by_location("STOCK")).start()
    elif compact_mode == "TOTAL":
        threading.Timer(0.25, lambda: open_items_by_location()).start()

    # =========================================================================
    # LAYOUT PRINCIPAL
    # =========================================================================
    return ft.Column([
        stats_row,
        compact_panel,
        ft.Container(height=4),
        filter_bar,
        ft.Row([
            location_filter_label,
            clear_location_btn,
        ], spacing=10),
        inventory_hint_panel,
        loading,
        ft.Container(
            **JetBrainsTheme.card_style(),
            height=460,
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.TABLE_ROWS,
                            color=ThemeColors.ACCENT_BLUE, size=20),
                    ft.Text("Movimientos Recientes", size=17, weight="bold",
                            color=ThemeColors.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    page_label,
                ], alignment="spaceBetween"),
                ft.Divider(height=1,
                           color=ft.colors.with_opacity(0.08, ft.colors.WHITE)),
                ft.Column([table], scroll="auto", expand=True),
            ], expand=True, spacing=10),
        ),
    ], expand=True, spacing=10, scroll=ft.ScrollMode.ALWAYS)
