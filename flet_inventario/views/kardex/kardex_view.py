import flet as ft
import threading

from core.theme import ThemeColors, JetBrainsTheme
from services.item_service import list_items
from services.movement_service import list_movements
from services.user_service import list_users
from services.customer_service import list_customers


def _location_type(item: dict) -> str:
    estado = str(item.get("estado") or "").upper()
    if estado in {"INSTALADO_CLIENTE", "ACTIVO_EN_CAMPO"}:
        return "CLIENTE"
    if item.get("ot_id") and estado in {"RESERVADO", "SALIDA_INSTALACION", "INSTALADO_CLIENTE"}:
        return "CLIENTE"
    return "BODEGA"


def _read_loc_name(item: dict) -> str:
    return item.get("ubicacion_nombre") or "Sin bodega registrada"


def _read_target_name(value) -> str:
    if isinstance(value, dict):
        tipo = str(value.get("tipo") or "").upper()
        nombre = (
            value.get("nombre")
            or value.get("nombre_bodega")
            or value.get("nombre_cliente")
            or value.get("id")
            or "---"
        )
        return f"{tipo}: {nombre}" if tipo else str(nombre)
    if value in (None, ""):
        return "---"
    return str(value)


def kardex_view(page: ft.Page, navigate, **kwargs):
    items_all = []
    items_filtered = []
    movements_recent = []
    users_all = []
    customers_all = []

    loading = ft.ProgressBar(visible=False, color=ThemeColors.ACCENT_BLUE)

    stats_total = ft.Text("0", size=22, weight="bold", color=ft.colors.WHITE)
    stats_bodega = ft.Text("0", size=22, weight="bold", color=ThemeColors.ACCENT_BLUE)
    stats_cliente = ft.Text("0", size=22, weight="bold", color=ThemeColors.ACCENT_MAGENTA)

    search_tf = ft.TextField(
        hint_text="Buscar por código, nombre o serie...",
        prefix_icon=ft.icons.SEARCH,
        width=360,
        **JetBrainsTheme.input_style(),
    )
    where_dd = ft.Dropdown(
        label="Ubicación actual",
        value="TODOS",
        width=200,
        options=[
            ft.dropdown.Option("TODOS"),
            ft.dropdown.Option("BODEGA"),
            ft.dropdown.Option("CLIENTE"),
        ],
        **JetBrainsTheme.input_style(),
    )
    responsable_dd = ft.Dropdown(
        label="Responsable",
        value="TODOS",
        width=240,
        options=[ft.dropdown.Option("TODOS")],
        **JetBrainsTheme.input_style(),
    )
    cliente_dd = ft.Dropdown(
        label="Cliente",
        value="TODOS",
        width=280,
        options=[ft.dropdown.Option("TODOS")],
        **JetBrainsTheme.input_style(),
    )

    rows_assets = ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO)
    rows_kardex = ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO)

    def show_snack(msg: str, is_error: bool = False):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(msg, color=ft.colors.WHITE, weight="bold"),
            bgcolor=ft.colors.RED_700 if is_error else ft.colors.GREEN_700,
            duration=3500,
        )
        page.snack_bar.open = True
        page.update()

    def _count_stats():
        total = len(items_all)
        en_bodega = len([x for x in items_all if _location_type(x) == "BODEGA"])
        en_cliente = len([x for x in items_all if _location_type(x) == "CLIENTE"])

        stats_total.value = str(total)
        stats_bodega.value = str(en_bodega)
        stats_cliente.value = str(en_cliente)

    def _asset_row(item: dict) -> ft.Control:
        loc_type = _location_type(item)
        loc_color = ThemeColors.ACCENT_BLUE if loc_type == "BODEGA" else ThemeColors.ACCENT_MAGENTA
        responsable = item.get("responsable_nombre") or "---"
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.colors.with_opacity(0.05, ft.colors.WHITE))),
            content=ft.Row([
                ft.Container(width=120, content=ft.Text(item.get("codigo", "---"), size=12, weight="bold", overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=260, content=ft.Text(item.get("nombre", "---"), size=12, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=120, content=ft.Text(item.get("estado", "---"), size=11, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=100, content=ft.Text(loc_type, size=11, weight="bold", color=loc_color)),
                ft.Container(width=240, content=ft.Text(_read_loc_name(item), size=11, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=180, content=ft.Text(responsable, size=11, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.IconButton(
                    icon=ft.icons.TIMELINE,
                    tooltip="Ver historial del activo",
                    icon_size=18,
                    icon_color=ThemeColors.ACCENT_BLUE,
                    on_click=lambda e, it=item: navigate("item_traceability", item_id=it.get("id"), item_data=it),
                ),
            ], spacing=10),
        )

    def _kardex_row(mov: dict) -> ft.Control:
        item = mov.get("item") or {}
        tipo = mov.get("tipo_movimiento") or "---"
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.colors.with_opacity(0.05, ft.colors.WHITE))),
            content=ft.Row([
                ft.Container(width=150, content=ft.Text(str(mov.get("fecha") or "---")[:19].replace("T", " "), size=11, color=ThemeColors.TEXT_SECONDARY)),
                ft.Container(width=120, content=ft.Text(item.get("codigo", "---"), size=12, weight="bold", overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=230, content=ft.Text(item.get("nombre", "---"), size=11, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=145, content=ft.Text(tipo, size=11, color=ThemeColors.ACCENT_BLUE, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=220, content=ft.Text(_read_target_name(mov.get("origen")), size=10, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=220, content=ft.Text(_read_target_name(mov.get("destino")), size=10, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=120, content=ft.Text(mov.get("ot_id") or "---", size=11, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
            ], spacing=8),
        )

    def refresh_assets_table():
        rows_assets.controls.clear()
        if not items_filtered:
            rows_assets.controls.append(
                ft.Container(
                    padding=ft.padding.all(20),
                    content=ft.Text("No hay activos para el filtro aplicado.", color=ThemeColors.TEXT_SECONDARY, italic=True),
                )
            )
            return

        for it in items_filtered:
            rows_assets.controls.append(_asset_row(it))

    def refresh_kardex_table():
        rows_kardex.controls.clear()
        if not movements_recent:
            rows_kardex.controls.append(
                ft.Container(
                    padding=ft.padding.all(20),
                    content=ft.Text("No hay movimientos recientes.", color=ThemeColors.TEXT_SECONDARY, italic=True),
                )
            )
            return

        for m in movements_recent:
            rows_kardex.controls.append(_kardex_row(m))

    def apply_filters(e=None):
        search = (search_tf.value or "").strip().lower()
        where = (where_dd.value or "TODOS").strip().upper()
        responsible_id = (responsable_dd.value or "TODOS").strip()
        customer_id = (cliente_dd.value or "TODOS").strip()

        items_filtered.clear()
        for it in items_all:
            if where != "TODOS" and _location_type(it) != where:
                continue
            if responsible_id != "TODOS" and str(it.get("responsable_id") or "") != responsible_id:
                continue
            if customer_id != "TODOS" and str(it.get("cliente_id") or "") != customer_id:
                continue
            if search:
                haystack = " ".join([
                    str(it.get("codigo") or ""),
                    str(it.get("nombre") or ""),
                    str(it.get("serial") or ""),
                ]).lower()
                if search not in haystack:
                    continue
            items_filtered.append(it)

        refresh_assets_table()
        page.update()

    search_tf.on_change = apply_filters
    where_dd.on_change = apply_filters
    responsable_dd.on_change = apply_filters
    cliente_dd.on_change = apply_filters

    def load_data():
        loading.visible = True
        page.update()
        try:
            items = list_items({}) or []
            mov_payload = list_movements({"page": 1, "page_size": 50}) or {}
            users = list_users() or []
            customers = list_customers() or []
            moves = mov_payload.get("results", []) if isinstance(mov_payload, dict) else []

            items_all.clear()
            items_all.extend(items)

            movements_recent.clear()
            movements_recent.extend(moves)

            users_all.clear()
            users_all.extend(users)
            responsable_dd.options = [ft.dropdown.Option("TODOS")] + [
                ft.dropdown.Option(
                    key=u.get("id"),
                    text=f"{u.get('username', 'Usuario')} ({str(u.get('rol', '')).upper()})",
                )
                for u in users_all
            ]
            if not any(opt.key == responsable_dd.value for opt in responsable_dd.options):
                responsable_dd.value = "TODOS"

            customers_all.clear()
            customers_all.extend(customers)
            cliente_dd.options = [ft.dropdown.Option("TODOS")] + [
                ft.dropdown.Option(
                    key=c.get("id"),
                    text=(c.get("nombre_cliente") or "Cliente"),
                )
                for c in customers_all
            ]
            if not any(opt.key == cliente_dd.value for opt in cliente_dd.options):
                cliente_dd.value = "TODOS"

            _count_stats()
            apply_filters()
            refresh_kardex_table()
        except Exception as ex:
            show_snack(f"Error cargando KARDEX: {ex}", is_error=True)
        finally:
            loading.visible = False
            page.update()

    threading.Timer(0.1, lambda: threading.Thread(target=load_data, daemon=True).start()).start()

    return ft.Column([
        ft.Row([
            ft.Text("KARDEX de Activos", size=22, weight="bold", color=ThemeColors.TEXT_PRIMARY),
            ft.Row([
                ft.ElevatedButton(
                    "Nuevo ingreso de equipamiento",
                    icon=ft.icons.ADD_BOX_ROUNDED,
                    style=JetBrainsTheme.primary_button_style(),
                    on_click=lambda e: navigate("create_item", tipo_item_default="equipo"),
                ),
                ft.ElevatedButton(
                    "Actualizar",
                    icon=ft.icons.REFRESH_ROUNDED,
                    style=JetBrainsTheme.primary_button_style(),
                    on_click=lambda e: threading.Thread(target=load_data, daemon=True).start(),
                ),
            ], spacing=10),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

        ft.Row([
            ft.Container(
                **JetBrainsTheme.card_style(),
                content=ft.Column([
                    ft.Text("ACTIVOS TOTALES", size=11, color=ThemeColors.TEXT_SECONDARY, weight="bold"),
                    stats_total,
                ], spacing=6),
                expand=True,
            ),
            ft.Container(
                **JetBrainsTheme.card_style(),
                content=ft.Column([
                    ft.Text("EN BODEGA", size=11, color=ThemeColors.TEXT_SECONDARY, weight="bold"),
                    stats_bodega,
                ], spacing=6),
                expand=True,
            ),
            ft.Container(
                **JetBrainsTheme.card_style(),
                content=ft.Column([
                    ft.Text("EN CLIENTE", size=11, color=ThemeColors.TEXT_SECONDARY, weight="bold"),
                    stats_cliente,
                ], spacing=6),
                expand=True,
            ),
        ], spacing=12),

        ft.Container(
            **JetBrainsTheme.card_style(),
            content=ft.Column([
                ft.Row([
                    search_tf,
                    where_dd,
                    responsable_dd,
                    cliente_dd,
                ], spacing=12, wrap=True),
                loading,
                ft.Divider(height=1, color=ft.colors.with_opacity(0.08, ft.colors.WHITE)),
                ft.Text("Registro de Activos por Ubicación Actual", size=13, weight="bold"),
                ft.Container(
                    bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
                    padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    content=ft.Row([
                        ft.Container(width=120, content=ft.Text("CÓDIGO", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                        ft.Container(width=260, content=ft.Text("ACTIVO", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                        ft.Container(width=120, content=ft.Text("ESTADO", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                        ft.Container(width=100, content=ft.Text("UBICACIÓN", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                        ft.Container(width=240, content=ft.Text("BODEGA", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                        ft.Container(width=180, content=ft.Text("RESPONSABLE", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                        ft.Container(width=32),
                    ], spacing=10),
                ),
                ft.Container(height=260, content=rows_assets),
            ], spacing=10),
        ),

        ft.Container(
            **JetBrainsTheme.card_style(),
            expand=True,
            content=ft.Column([
                ft.Text("Libro KARDEX - Movimientos Recientes", size=13, weight="bold"),
                ft.Container(
                    bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
                    padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    content=ft.Row([
                        ft.Container(width=150, content=ft.Text("FECHA", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                        ft.Container(width=120, content=ft.Text("CÓDIGO", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                        ft.Container(width=230, content=ft.Text("ACTIVO", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                        ft.Container(width=145, content=ft.Text("TIPO", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                        ft.Container(width=220, content=ft.Text("ORIGEN", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                        ft.Container(width=220, content=ft.Text("DESTINO", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                        ft.Container(width=120, content=ft.Text("OT", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
                    ], spacing=8),
                ),
                rows_kardex,
            ], spacing=10, expand=True),
        ),
    ], expand=True, spacing=14, scroll=ft.ScrollMode.ALWAYS)
