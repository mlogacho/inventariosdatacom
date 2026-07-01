import flet as ft
from core.theme import ThemeColors, JetBrainsTheme
from components.status_badge import status_badge
from components.stats_card import stats_card
from components.timeline import asset_timeline
from services.movement_service import list_movements, get_movement_stats, get_asset_history
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


def movement_view(page: ft.Page, navigate):
    # =========================================================================
    # ESTADO Y VARIABLES
    # =========================================================================
    movements_data = []
    stats_data = {}

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

    stats_row = ft.Row(spacing=16, scroll="auto")

    # Loader
    loading = ft.ProgressBar(visible=False, color=ThemeColors.ACCENT_BLUE)

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

            table.rows.clear()

            if not results:
                table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(
                            "No se encontraron movimientos",
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
                    prev      = m.get("origen", {}).get("estado", "INICIO")
                    new_state = m.get("destino", {}).get("estado", "---")
                    tipo      = m.get("tipo_movimiento", "---")
                    resp_obj  = m.get("responsable", {})
                    resp      = (resp_obj.get("username", "---")
                                 if isinstance(resp_obj, dict) else str(resp_obj))
                    fecha_raw = m.get("fecha", "---")
                    fecha_str = (fecha_raw[:16].replace("T", " ")
                                 if len(fecha_raw) >= 16 else fecha_raw)

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
                                ft.DataCell(ft.IconButton(
                                    icon=ft.icons.TIMELINE,
                                    icon_color=ThemeColors.ACCENT_BLUE,
                                    icon_size=20,
                                    tooltip="Ver Trazabilidad Completa",
                                    on_click=lambda e, it=item: navigate(
                                        "item_traceability",
                                        item_id=it["id"],
                                        item_data=it
                                    )
                                )),
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
        apply_filters()

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
                grouped[loc_name] = grouped.get(loc_name, 0) + 1

            rows = sorted(grouped.items(), key=lambda x: x[1], reverse=True)
            title = "Activos En Stock por Ubicación" if estado == "STOCK" else "Activos Totales por Ubicación"

            page.dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(title, weight="bold"),
                content=ft.Container(
                    width=560,
                    height=420,
                    content=ft.Column(
                        [
                            ft.Row([
                                ft.Text("Ubicación", weight="bold", color=ThemeColors.TEXT_SECONDARY, expand=True),
                                ft.Text("Cantidad", weight="bold", color=ThemeColors.TEXT_SECONDARY),
                            ]),
                            ft.Divider(height=1, color=ft.colors.with_opacity(0.08, ft.colors.WHITE)),
                            ft.Column([
                                ft.Row([
                                    ft.Text(name, expand=True),
                                    ft.Text(str(count), weight="bold", color=ThemeColors.ACCENT_BLUE),
                                ])
                                for name, count in rows
                            ], spacing=8, scroll=ft.ScrollMode.AUTO, expand=True),
                        ],
                        spacing=10,
                        expand=True,
                    ),
                ),
                actions=[
                    ft.TextButton("Cerrar", on_click=lambda e: setattr(page.dialog, "open", False) or page.update())
                ],
            )
            page.dialog.open = True
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
    import threading
    threading.Timer(0.1, load_stats).start()
    threading.Timer(0.2, apply_filters).start()

    # =========================================================================
    # LAYOUT PRINCIPAL
    # =========================================================================
    return ft.Column([
        stats_row,
        ft.Container(height=4),
        filter_bar,
        loading,
        ft.Container(
            **JetBrainsTheme.card_style(),
            expand=True,
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
    ], expand=True, spacing=10)
