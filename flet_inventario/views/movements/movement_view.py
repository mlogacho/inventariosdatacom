import flet as ft
from core.theme import ThemeColors, JetBrainsTheme
from components.status_badge import status_badge
from components.stats_card import stats_card
from components.timeline import asset_timeline
from services.movement_service import list_movements, get_movement_stats, get_asset_history

def movement_view(page: ft.Page, navigate):
    # =========================
    # ESTADO Y VARIABLES
    # =========================
    movements_data = []
    stats_data = {}
    
    # Filtros
    search_tf = ft.TextField(
        hint_text="Código, nombre o serie...",
        prefix_icon=ft.icons.SEARCH,
        expand=True,
        on_submit=lambda e: apply_filters(),
        **JetBrainsTheme.input_style()
    )
    
    tipo_dd = ft.Dropdown(
        label="Tipo de Movimiento",
        width=210,
        options=[
            ft.dropdown.Option("TODOS"),
            ft.dropdown.Option("ENTRADA"),
            ft.dropdown.Option("SALIDA"),
            ft.dropdown.Option("AJUSTE"),
            ft.dropdown.Option("TRANSFERENCIA"),
            ft.dropdown.Option("BAJA"),
            ft.dropdown.Option("RESERVA"),
            ft.dropdown.Option("INSTALACION"),
            ft.dropdown.Option("RETORNO"),
        ],
        **JetBrainsTheme.input_style()
    )
    
    ot_tf = ft.TextField(
        label="Orden de Trabajo (OT)",
        width=180,
        **JetBrainsTheme.input_style()
    )

    # =========================
    # COMPONENTES DE UI
    # =========================
    table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("ACTIVO")),
            ft.DataColumn(ft.Text("TIPO")),
            ft.DataColumn(ft.Text("FLUJO")),
            ft.DataColumn(ft.Text("RESPONSABLE")),
            ft.DataColumn(ft.Text("FECHA")),
            ft.DataColumn(ft.Text("ACCIONES")),
        ],
        rows=[],
        heading_row_color=ft.colors.with_opacity(0.05, ft.colors.WHITE),
        expand=True,
    )

    stats_row = ft.Row(spacing=20, scroll="auto")
    
    # Loader
    loading = ft.ProgressBar(visible=False, color=ThemeColors.ACCENT_BLUE)

    # =========================
    # ACCIONES
    # =========================
    def load_stats():
        nonlocal stats_data
        try:
            stats_data = get_movement_stats()
            stats_row.controls = [
                stats_card("Activos Totales", str(stats_data.get("total_items", 0)), ft.icons.INVENTORY),
                stats_card("En Stock", str(stats_data.get("stats_by_state", {}).get("STOCK", 0)), ft.icons.WAREHOUSE, ThemeColors.STATE_STOCK),
                stats_card("Reservados", str(stats_data.get("stats_by_state", {}).get("RESERVADO", 0)), ft.icons.VPN_KEY, ThemeColors.STATE_RESERVED),
                stats_card("Movimientos Hoy", str(stats_data.get("movements_today", 0)), ft.icons.SYNC, ThemeColors.ACCENT_MAGENTA),
            ]
            page.update()
        except:
            pass

    def apply_filters(e=None):
        loading.visible = True
        page.update()
        
        params = {"page_size": 100}
        if search_tf.value: params["search"] = search_tf.value
        if tipo_dd.value and tipo_dd.value != "TODOS": params["tipo_movimiento"] = tipo_dd.value
        if ot_tf.value: params["ot_id"] = ot_tf.value
        if fecha_desde.value: params["fecha_desde"] = fecha_desde.value
        if fecha_hasta.value: params["fecha_hasta"] = fecha_hasta.value
        
        try:
            data = list_movements(params)
            # El backend devuelve { success: True, data: { results: [], pagination: {} } }
            # El APIClient ya desempaqueta el primer 'data', por lo que aquí recibimos
            # directamente { results: [], pagination: {} }
            results = []
            if isinstance(data, dict):
                results = data.get("results", [])
            elif isinstance(data, list):
                results = data # Fallback
            
            table.rows.clear()
            
            if not results:
                table.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text("No se encontraron movimientos", italic=True, color=ThemeColors.TEXT_SECONDARY))] + [ft.DataCell(ft.Text(""))]*5))
            
            for m in results:
                # Resolver nombres
                item = m.get("item", {})
                item_name = item.get("nombre", "Desconocido")
                item_code = item.get("codigo", "---")
                
                # Estados
                prev = m.get("origen", {}).get("estado", "INICIO")
                new = m.get("destino", {}).get("estado", "---")
                
                table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Column([
                                ft.Text(item_name, size=14, weight="bold", color=ThemeColors.TEXT_PRIMARY),
                                ft.Text(item_code, size=11, color=ThemeColors.TEXT_SECONDARY),
                            ], spacing=2, alignment="center")),
                            ft.DataCell(ft.Text(m.get("tipo_movimiento"), size=12)),
                            ft.DataCell(ft.Row([
                                ft.Text(prev, size=10, color=ThemeColors.TEXT_SECONDARY),
                                ft.Icon(ft.icons.ARROW_FORWARD, size=12, color=ThemeColors.TEXT_SECONDARY),
                                status_badge(new)
                            ], spacing=8)),
                            ft.DataCell(ft.Text(m.get("responsable", {}).get("username", "---"))),
                            ft.DataCell(ft.Text(m.get("fecha")[:16].replace("T", " "))),
                            ft.DataCell(ft.IconButton(
                                icon=ft.icons.TIMELINE,
                                icon_color=ThemeColors.ACCENT_BLUE,
                                tooltip="Ver Trazabilidad Completa",
                                on_click=lambda e, it=item: navigate("item_traceability", item_id=it["id"], item_data=it)
                            ))
                        ]
                    )
                )
        except Exception as ex:
            print(f"Error: {ex}")
            
        loading.visible = False
        page.update()

    # =========================
    # LAYOUT
    # =========================
    
    def reset_filters(e):
        search_tf.value = ""
        tipo_dd.value = "TODOS"
        ot_tf.value = ""
        fecha_desde.value = ""
        fecha_hasta.value = ""
        apply_filters()

    # Date Pickers
    def on_date_from_change(e):
        fecha_desde.value = date_picker_from.value.strftime("%Y-%m-%d")
        page.update()
    
    def on_date_to_change(e):
        fecha_hasta.value = date_picker_to.value.strftime("%Y-%m-%d")
        page.update()

    date_picker_from = ft.DatePicker(on_change=on_date_from_change)
    date_picker_to = ft.DatePicker(on_change=on_date_to_change)

    if date_picker_from not in page.overlay: page.overlay.extend([date_picker_from, date_picker_to])

    fecha_desde = ft.TextField(label="Desde", width=120, read_only=True, **JetBrainsTheme.input_style())
    btn_desde = ft.IconButton(icon=ft.icons.CALENDAR_MONTH, icon_color=ThemeColors.ACCENT_BLUE, on_click=lambda e: date_picker_from.pick_date())
    row_desde = ft.Row([fecha_desde, btn_desde], spacing=2)

    fecha_hasta = ft.TextField(label="Hasta", width=120, read_only=True, **JetBrainsTheme.input_style())
    btn_hasta = ft.IconButton(icon=ft.icons.CALENDAR_MONTH, icon_color=ThemeColors.ACCENT_BLUE, on_click=lambda e: date_picker_to.pick_date())
    row_hasta = ft.Row([fecha_hasta, btn_hasta], spacing=2)

    # Barra de filtros
    filter_bar = ft.Container(
        **JetBrainsTheme.card_style(),
        content=ft.Row([
            search_tf,
            tipo_dd,
            ot_tf,
            row_desde,
            row_hasta,
            ft.ElevatedButton(
                "Buscar",
                icon=ft.icons.SEARCH,
                style=JetBrainsTheme.primary_button_style(),
                on_click=apply_filters,
                height=45
            ),
            ft.IconButton(
                ft.icons.FILTER_ALT_OFF,
                tooltip="Limpiar filtros",
                on_click=reset_filters
            )
        ], spacing=15)
    )

    # Inicialización
    import threading
    threading.Timer(0.1, load_stats).start()
    threading.Timer(0.2, apply_filters).start()

    return ft.Column([
        stats_row,
        ft.Container(height=10),
        filter_bar,
        loading,
        ft.Container(
            **JetBrainsTheme.card_style(),
            expand=True,
            content=ft.Column([
                ft.Row([
                    ft.Text("Movimientos Recientes", size=18, weight="bold"),
                    ft.Text("Página 1", size=12, color=ThemeColors.TEXT_SECONDARY),
                ], alignment="justify"),
                ft.Divider(height=10, color=ft.colors.with_opacity(0.05, ft.colors.WHITE)),
                ft.Column([table], scroll="auto", expand=True)
            ], expand=True)
        )
    ], expand=True, spacing=10)
