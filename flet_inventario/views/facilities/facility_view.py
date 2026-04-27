"""
Vista de Instalaciones — DATALIVE v4.0

Sección 3 (Herramientas) y Sección 4 (Materiales) ahora seleccionan
desde stock real.  El cierre usa el endpoint /close/ con retorno
obligatorio de herramientas y liquidación de materiales.
"""
import flet as ft
import threading
import webbrowser
from core.api_client import APIClient
from core.session import Session
from core.permissions import can_access
from core.theme import ThemeColors, JetBrainsTheme
from components.status_badge import status_badge
from services.facility_service import (
    start_facility, cancel_facility, close_facility,
)


# ─── SNACKBAR ────────────────────────────────────────────────────────────────
def show_snack(page, msg, is_error=False):
    page.snack_bar = ft.SnackBar(
        ft.Text(msg, color=ft.colors.WHITE, weight="bold"),
        bgcolor=ft.colors.RED_700 if is_error else ft.colors.GREEN_700,
        duration=3000,
    )
    page.snack_bar.open = True
    page.update()


# ─── VISTA LISTA ─────────────────────────────────────────────────────────────
def facility_view(page: ft.Page, navigate):
    rol = Session.user.get("rol", "tecnico") if Session.user else "tecnico"

    W = {"cod": 90, "cli": 220, "tec": 150, "est": 150, "fec": 110, "act": 110}

    estado_dd = ft.Dropdown(
        label="Filtrar por Estado",
        width=220,
        options=[
            ft.dropdown.Option("TODOS"),
            ft.dropdown.Option("planificada", text="PLANIFICADA"),
            ft.dropdown.Option("en_proceso",  text="EN PROCESO"),
            ft.dropdown.Option("finalizada",  text="FINALIZADA"),
            ft.dropdown.Option("cancelada",   text="CANCELADA"),
        ],
        **JetBrainsTheme.input_style()
    )

    rows_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
    loading  = ft.ProgressBar(visible=False, color=ThemeColors.ACCENT_BLUE)

    def _hdr(txt, w):
        return ft.Container(
            width=w,
            content=ft.Text(txt, size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY),
        )

    header = ft.Container(
        bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
        padding=ft.padding.symmetric(horizontal=16, vertical=10),
        content=ft.Row([
            _hdr("CÓDIGO",      W["cod"]),
            _hdr("CLIENTE",     W["cli"]),
            _hdr("TÉCNICO",     W["tec"]),
            _hdr("ESTADO",      W["est"]),
            _hdr("FECHA PROG.", W["fec"]),
            _hdr("ACCIONES",    W["act"]),
        ], spacing=8),
    )

    def open_detail(fac):
        try:
            fac_id = fac.get("id") or fac.get("_id")
            if not fac_id:
                raise ValueError("La instalación no tiene un ID válido.")
            page.session.set("facility_detail_id", fac_id)
            navigate("facility_detail")
        except Exception as e:
            show_snack(page, f"Error al abrir detalle: {e}", True)

    def confirm_delete(fac):
        def do_delete(e):
            try:
                fac_id = fac.get("id") or fac.get("_id")
                APIClient.delete(f"inventory/facilities/{fac_id}/")
                page.dialog.open = False
                page.update()
                load_facilities()
                show_snack(page, "Instalación eliminada exitosamente.")
            except Exception as ex:
                show_snack(page, f"Error al eliminar: {ex}", True)

        page.dialog = ft.AlertDialog(
            title=ft.Text("Confirmar Baja", weight="bold"),
            content=ft.Text(
                f"¿Eliminar instalación {fac.get('codigo_instalacion', '')}? "
                "Esta acción no se puede deshacer."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Eliminar", bgcolor=ft.colors.RED_600, color=ft.colors.WHITE, on_click=do_delete),
            ],
        )
        page.dialog.open = True
        page.update()

    def make_row(fac):
        est   = fac.get("estado", "planificada")
        fecha = (fac.get("fecha_programada") or "")[:10]
        cli_txt = (fac.get("cliente", {}).get("nombre_cliente", "---")
                   if isinstance(fac.get("cliente"), dict) else "---")
        tec_txt = (fac.get("tecnico", {}).get("username", "---")
                   if isinstance(fac.get("tecnico"), dict) else "---")

        btn_ver = ft.ElevatedButton(
            icon=ft.icons.VISIBILITY_ROUNDED, text="Ver",
            style=ft.ButtonStyle(
                color=ft.colors.WHITE, bgcolor=ThemeColors.ACCENT_BLUE,
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                shape=ft.RoundedRectangleBorder(radius=6),
            ),
            height=34, on_click=lambda e, f=fac: open_detail(f),
        )

        action_controls = [btn_ver]
        if est == "planificada" and can_access(rol, "facility:delete"):
            action_controls.append(ft.IconButton(
                icon=ft.icons.DELETE_SWEEP_ROUNDED, icon_color=ft.colors.RED_400,
                icon_size=20, tooltip="Eliminar",
                on_click=lambda e, f=fac: confirm_delete(f),
            ))

        return ft.Container(
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.colors.with_opacity(0.06, ft.colors.WHITE))),
            on_hover=lambda e: setattr(
                e.control, "bgcolor",
                ft.colors.with_opacity(0.04, ft.colors.WHITE) if e.data == "true"
                else ft.colors.TRANSPARENT
            ) or page.update(),
            content=ft.Row([
                ft.Container(width=W["cod"], content=ft.Text(fac.get("codigo_instalacion", "---"), weight="bold", size=13)),
                ft.Container(width=W["cli"], content=ft.Text(cli_txt, size=12, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=W["tec"], content=ft.Text(tec_txt, size=12, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=W["est"], content=status_badge(est)),
                ft.Container(width=W["fec"], content=ft.Text(fecha or "---", size=12, color=ThemeColors.TEXT_SECONDARY)),
                ft.Container(width=W["act"], content=ft.Row(action_controls, spacing=4)),
            ], spacing=8),
        )

    def load_facilities():
        loading.visible = True
        page.update()
        try:
            params = {}
            if estado_dd.value and estado_dd.value != "TODOS":
                params["estado"] = estado_dd.value
            data = APIClient.get("inventory/facilities/", params=params) or []
            rows_col.controls.clear()
            if not data:
                rows_col.controls.append(ft.Container(
                    padding=ft.padding.all(24),
                    content=ft.Text("No hay instalaciones registradas.", italic=True, color=ThemeColors.TEXT_SECONDARY),
                ))
            else:
                for f in data:
                    rows_col.controls.append(make_row(f))
        except Exception as e:
            show_snack(page, f"Error al cargar instalaciones: {e}", True)
        loading.visible = False
        page.update()

    estado_dd.on_change = lambda e: load_facilities()
    threading.Timer(0.1, load_facilities).start()

    return ft.Column([
        ft.Row([
            ft.Text("Gestión de Instalaciones", size=24, weight="bold", color=ThemeColors.TEXT_PRIMARY),
            ft.ElevatedButton(
                "Nueva Instalación", icon=ft.icons.ADD_ROUNDED,
                style=JetBrainsTheme.primary_button_style(),
                on_click=lambda e: (page.session.set("facility_to_edit", None) or navigate("create_facility")),
                visible=can_access(rol, "facility:create"),
            ),
        ], alignment="spaceBetween"),
        ft.Container(
            **JetBrainsTheme.card_style(),
            content=ft.Row([
                estado_dd,
                ft.ElevatedButton("Actualizar", icon=ft.icons.REFRESH_ROUNDED,
                                  style=JetBrainsTheme.primary_button_style(),
                                  on_click=lambda e: load_facilities(), height=45),
            ], spacing=15),
        ),
        loading,
        ft.Container(
            **JetBrainsTheme.card_style(),
            expand=True,
            content=ft.Column([
                header,
                ft.Divider(height=1, color=ft.colors.with_opacity(0.08, ft.colors.WHITE)),
                rows_col,
            ], expand=True, spacing=0),
        ),
    ], expand=True, spacing=15)


# ─── FORMULARIO EN 4 SECCIONES ───────────────────────────────────────────────
def facility_form_view(page: ft.Page, navigate):
    try:
        facility  = page.session.get("facility_to_edit")
        is_new    = facility is None
        estado    = facility.get("estado", "planificada") if facility else "planificada"
        is_final  = estado == "finalizada"
        is_locked = is_final or estado == "cancelada"

        # ── Estado local ──────────────────────────────────────────────────────
        items_planificados = []   # [{item_id, nombre, codigo, serial, categoria, destino}]
        herramientas_list  = []   # [{item_id, nombre, codigo, cantidad, observaciones}]
        consumibles_list   = []   # [{item_id, nombre, codigo, unidad, cantidad_reservada, obs}]

        if facility:
            for it in facility.get("items_planificados", []):
                item_data = it.get("item", it)
                items_planificados.append({
                    "item_id":   str(it.get("item_id") or item_data.get("id", "")),
                    "nombre":    item_data.get("nombre", "Item"),
                    "codigo":    item_data.get("codigo", "---"),
                    "serial":    item_data.get("serial", "---"),
                    "categoria": "Activos",
                    "destino":   it.get("destino_final", "cliente"),
                })
            for h in facility.get("herramientas", []) or []:
                herramientas_list.append({
                    "item_id":      h.get("item_id", ""),
                    "nombre":       h.get("nombre", ""),
                    "codigo":       h.get("codigo", ""),
                    "cantidad":     h.get("cantidad", 1),
                    "observaciones": h.get("observaciones", ""),
                })
            for c in facility.get("consumibles", []) or []:
                consumibles_list.append({
                    "item_id":          c.get("item_id", ""),
                    "nombre":           c.get("nombre", ""),
                    "codigo":           c.get("codigo", ""),
                    "unidad":           c.get("unidad", "unidad"),
                    "cantidad_reservada": c.get("cantidad_reservada", c.get("cantidad", 1)),
                    "stock_disponible":  c.get("stock_disponible", 0),
                    "observaciones":    c.get("observaciones", ""),
                })

        # ── Catálogos cargados ────────────────────────────────────────────────
        all_items_data       = {}   # item_id → item dict (equipos)
        all_herr_data        = {}   # item_id → item dict (herramientas)
        all_cons_data        = {}   # item_id → item dict (materiales)

        # ── SECCIÓN 1 — GENERAL ───────────────────────────────────────────────
        codigo_tf  = ft.TextField(
            label="Código / OT",
            value=facility.get("codigo_instalacion", "") if facility else "",
            height=55,
            disabled=not is_new, **JetBrainsTheme.input_style()
        )
        dir_tf = ft.TextField(
            label="Dirección de Instalación",
            value=facility.get("direccion_instalacion", "") if facility else "",
            height=55,
            disabled=is_locked, **JetBrainsTheme.input_style()
        )
        obs_tf = ft.TextField(
            label="Observaciones Generales",
            multiline=True, min_lines=2,
            value=facility.get("observaciones", "") if facility else "",
            height=85,
            disabled=is_locked, **JetBrainsTheme.input_style()
        )
        cliente_dd  = ft.Dropdown(label="Cliente",             disabled=is_locked, height=55, **JetBrainsTheme.input_style(), expand=True)
        tecnico_dd  = ft.Dropdown(label="Técnico Responsable", disabled=is_locked, height=55, **JetBrainsTheme.input_style(), expand=True)
        vehiculo_dd = ft.Dropdown(label="Vehículo Asignado",   disabled=is_locked, height=55, **JetBrainsTheme.input_style(), expand=True)

        date_picker = ft.DatePicker()
        if date_picker not in page.overlay:
            page.overlay.append(date_picker)

        fecha_tf = ft.TextField(
            label="Fecha Programada", read_only=True,
            value=(facility.get("fecha_programada") or "")[:10] if facility else "",
            disabled=is_locked, **JetBrainsTheme.input_style(), width=200, height=55
        )
        fecha_btn = ft.IconButton(
            icon=ft.icons.CALENDAR_MONTH_ROUNDED, icon_color=ThemeColors.ACCENT_BLUE,
            on_click=lambda e: date_picker.pick_date(), disabled=is_locked, tooltip="Seleccionar Fecha"
        )

        def on_date_change(e):
            if date_picker.value:
                fecha_tf.value = date_picker.value.strftime("%Y-%m-%d")
                page.update()

        date_picker.on_change = on_date_change

        # ── SECCIÓN 2 — EQUIPOS (patrón original sin cambios) ─────────────────
        summary_col = ft.Column(spacing=5)
        items_col   = ft.Column(spacing=8, scroll="auto")
        item_dd     = ft.Dropdown(label="Seleccionar Activo en STOCK", **JetBrainsTheme.input_style(), expand=True)

        def update_summary():
            total = len(items_planificados) + len(herramientas_list) + len(consumibles_list)
            summary_col.controls = [
                ft.Text("Resumen de Recursos", size=12, weight="bold", color=ThemeColors.TEXT_SECONDARY),
                ft.Container(content=ft.Row([
                    ft.Text("Equipos", size=12, expand=True),
                    ft.Container(content=ft.Text(str(len(items_planificados)), size=11, color=ft.colors.WHITE, weight="bold"),
                                 bgcolor=ThemeColors.ACCENT_BLUE, padding=ft.padding.symmetric(horizontal=8, vertical=2), border_radius=10)
                ]), padding=ft.padding.symmetric(vertical=3)),
                ft.Container(content=ft.Row([
                    ft.Text("Herramientas", size=12, expand=True),
                    ft.Container(content=ft.Text(str(len(herramientas_list)), size=11, color=ft.colors.WHITE, weight="bold"),
                                 bgcolor="#FF8F00", padding=ft.padding.symmetric(horizontal=8, vertical=2), border_radius=10)
                ]), padding=ft.padding.symmetric(vertical=3)),
                ft.Container(content=ft.Row([
                    ft.Text("Materiales", size=12, expand=True),
                    ft.Container(content=ft.Text(str(len(consumibles_list)), size=11, color=ft.colors.WHITE, weight="bold"),
                                 bgcolor=ThemeColors.STATE_STOCK, padding=ft.padding.symmetric(horizontal=8, vertical=2), border_radius=10)
                ]), padding=ft.padding.symmetric(vertical=3)),
            ]
            if total > 0:
                summary_col.controls.append(ft.Divider(height=8))
                summary_col.controls.append(
                    ft.Text(f"Total recursos: {total}", size=13, weight="bold", color=ThemeColors.ACCENT_BLUE)
                )

        def render_items():
            items_col.controls = []
            for i, it in enumerate(items_planificados):
                items_col.controls.append(ft.Container(
                    bgcolor=ft.colors.with_opacity(0.04, ft.colors.WHITE),
                    padding=12, border_radius=8,
                    border=ft.border.all(1, ft.colors.with_opacity(0.08, ft.colors.WHITE)),
                    content=ft.Row([
                        ft.Column([
                            ft.Text(it["nombre"], weight="bold", size=13),
                            ft.Text(f"SKU: {it['codigo']} | SN: {it.get('serial', '---')}", size=11, color=ThemeColors.TEXT_SECONDARY),
                        ], expand=True),
                        ft.IconButton(
                            ft.icons.REMOVE_CIRCLE_OUTLINE, icon_color=ft.colors.RED_400,
                            on_click=lambda e, idx=i: (_remove_item(idx)),
                            visible=not is_locked and estado in ("planificada", ""),
                        ),
                    ], vertical_alignment="center")
                ))
            update_summary()
            try: page.update()
            except: pass

        def _remove_item(idx):
            if idx < len(items_planificados):
                items_planificados.pop(idx)
                render_items()

        def add_item(e):
            if not item_dd.value or item_dd.value == "null":
                show_snack(page, "Selecciona un activo", True); return
            if any(it["item_id"] == item_dd.value for it in items_planificados):
                show_snack(page, "Este activo ya está en la lista", True); return
            it_full = all_items_data.get(item_dd.value, {})
            items_planificados.append({
                "item_id": item_dd.value,
                "nombre":  it_full.get("nombre", "Item"),
                "codigo":  it_full.get("codigo", "---"),
                "serial":  it_full.get("serial", "---"),
                "categoria": "Activos",
                "destino": "cliente",
            })
            render_items()

        # ── SECCIÓN 3 — HERRAMIENTAS (selector desde stock) ───────────────────
        herr_col = ft.Column(spacing=6)
        herr_dd  = ft.Dropdown(
            label="Seleccionar Herramienta en STOCK",
            **JetBrainsTheme.input_style(), expand=True,
            visible=not is_locked,
        )

        def render_herr():
            herr_col.controls = []
            for i, h in enumerate(herramientas_list):
                cant_tf = ft.TextField(
                    value=str(h.get("cantidad", 1)),
                    width=70, height=35, text_size=12,
                    keyboard_type=ft.KeyboardType.NUMBER,
                    **JetBrainsTheme.input_style(),
                    disabled=is_locked,
                    on_change=lambda e, idx=i: _update_herr_qty(idx, e.control.value),
                )
                herr_col.controls.append(ft.Container(
                    bgcolor=ft.colors.with_opacity(0.04, ft.colors.WHITE),
                    padding=10, border_radius=8,
                    border=ft.border.all(1, ft.colors.with_opacity(0.1, ft.colors.WHITE)),
                    content=ft.Row([
                        ft.Icon(ft.icons.BUILD, size=16, color="#FF8F00"),
                        ft.Column([
                            ft.Text(h["nombre"], weight="bold", size=13),
                            ft.Text(f"SKU: {h['codigo']}", size=11, color=ThemeColors.TEXT_SECONDARY),
                        ], expand=True, spacing=1),
                        ft.Text("Cant:", size=11, color=ThemeColors.TEXT_SECONDARY),
                        cant_tf,
                        ft.IconButton(
                            ft.icons.REMOVE_CIRCLE_OUTLINE, icon_color=ft.colors.RED_400,
                            on_click=lambda e, idx=i: _remove_herr(idx),
                            visible=not is_locked,
                        ),
                    ], spacing=8, vertical_alignment="center")
                ))
            update_summary()
            try: page.update()
            except: pass

        def _update_herr_qty(idx, val):
            try:
                herramientas_list[idx]["cantidad"] = max(1, int(val))
            except (ValueError, IndexError):
                pass

        def _remove_herr(idx):
            if idx < len(herramientas_list):
                herramientas_list.pop(idx)
                render_herr()

        def add_herr(_):
            if not herr_dd.value or herr_dd.value == "null":
                show_snack(page, "Selecciona una herramienta", True); return
            if any(h["item_id"] == herr_dd.value for h in herramientas_list):
                show_snack(page, "Esta herramienta ya está en la lista", True); return
            it = all_herr_data.get(herr_dd.value, {})
            herramientas_list.append({
                "item_id":       herr_dd.value,
                "nombre":        it.get("nombre", "—"),
                "codigo":        it.get("codigo", "—"),
                "cantidad":      1,
                "observaciones": "",
            })
            render_herr()

        # ── SECCIÓN 4 — MATERIALES / CONSUMIBLES (selector desde stock) ───────
        cons_col = ft.Column(spacing=6)
        cons_dd  = ft.Dropdown(
            label="Seleccionar Material / Consumible en STOCK",
            **JetBrainsTheme.input_style(), expand=True,
            visible=not is_locked,
        )

        def render_cons():
            cons_col.controls = []
            for i, c in enumerate(consumibles_list):
                stock_disp = c.get("stock_disponible", 0)
                cant_tf = ft.TextField(
                    value=str(c.get("cantidad_reservada", 1)),
                    width=90, height=35, text_size=12,
                    keyboard_type=ft.KeyboardType.NUMBER,
                    **JetBrainsTheme.input_style(),
                    disabled=is_locked,
                    on_change=lambda e, idx=i: _update_cons_qty(idx, e.control.value),
                )
                cons_col.controls.append(ft.Container(
                    bgcolor=ft.colors.with_opacity(0.04, ft.colors.WHITE),
                    padding=10, border_radius=8,
                    border=ft.border.all(1, ft.colors.with_opacity(0.1, ft.colors.WHITE)),
                    content=ft.Row([
                        ft.Icon(ft.icons.INVENTORY_2, size=16, color=ThemeColors.STATE_STOCK),
                        ft.Column([
                            ft.Text(c["nombre"], weight="bold", size=13),
                            ft.Text(
                                f"SKU: {c['codigo']} | Unidad: {c.get('unidad','—')} | Stock: {stock_disp}",
                                size=11, color=ThemeColors.TEXT_SECONDARY
                            ),
                        ], expand=True, spacing=1),
                        ft.Text("Cant:", size=11, color=ThemeColors.TEXT_SECONDARY),
                        cant_tf,
                        ft.IconButton(
                            ft.icons.REMOVE_CIRCLE_OUTLINE, icon_color=ft.colors.RED_400,
                            on_click=lambda e, idx=i: _remove_cons(idx),
                            visible=not is_locked,
                        ),
                    ], spacing=8, vertical_alignment="center")
                ))
            update_summary()
            try: page.update()
            except: pass

        def _update_cons_qty(idx, val):
            try:
                stock = consumibles_list[idx].get("stock_disponible", 9999)
                qty   = max(1, min(int(val), stock))
                consumibles_list[idx]["cantidad_reservada"] = qty
            except (ValueError, IndexError):
                pass

        def _remove_cons(idx):
            if idx < len(consumibles_list):
                consumibles_list.pop(idx)
                render_cons()

        def add_cons(_):
            if not cons_dd.value or cons_dd.value == "null":
                show_snack(page, "Selecciona un material", True); return
            if any(c["item_id"] == cons_dd.value for c in consumibles_list):
                show_snack(page, "Este material ya está en la lista", True); return
            it = all_cons_data.get(cons_dd.value, {})
            consumibles_list.append({
                "item_id":            cons_dd.value,
                "nombre":             it.get("nombre", "—"),
                "codigo":             it.get("codigo", "—"),
                "unidad":             it.get("unidad", "unidad"),
                "cantidad_reservada": 1,
                "stock_disponible":   it.get("cantidad", 0),
                "observaciones":      "",
            })
            render_cons()

        # ── CARGA DE DATOS ────────────────────────────────────────────────────
        def load_data():
            try:
                from services.customer_service import list_customers
                from services.user_service    import list_users
                from services.item_service    import list_items

                customers = list_customers()
                users     = list_users()
                items     = list_items({"estado": "STOCK"})
                vehicles  = APIClient.get("inventory/vehicles/")

                cliente_dd.options = [
                    ft.dropdown.Option(key=str(c.get("id", c.get("_id"))), text=c.get("nombre_cliente", "---"))
                    for c in (customers or [])
                ]
                tecnicos_activos = [u for u in (users or []) if u.get("rol") in ("tecnico", "admin")]
                tecnico_dd.options = [
                    ft.dropdown.Option(key=str(u.get("id", u.get("_id"))), text=u.get("username", "---"))
                    for u in tecnicos_activos
                ]

                veh_options = [ft.dropdown.Option(key="", text="Sin vehículo")]
                if vehicles and isinstance(vehicles, list):
                    for v in vehicles:
                        veh_options.append(ft.dropdown.Option(
                            key=str(v.get("id", v.get("_id"))),
                            text=f"{v.get('marca','')} {v.get('modelo','')} | {v.get('placa','')}".strip()
                        ))
                vehiculo_dd.options = veh_options

                # Clasificador con keyword-fallback para ítems con tipo_item="general"/null
                _HERR_KWS = {"herramienta","taladro","llave","crimpadora","escalera","alicate",
                              "destornillador","pinza","sierra","martillo","nivel","ponchadora",
                              "multimetro","certificador","tester","pelacable","crimp","medicion"}
                _MAT_KWS  = {"material","cable","conector","papel","tinta","consumible","canaleta",
                              "patch","utp","fibra","ducto","tornillo","etiqueta","brida","cinta",
                              "jack","keystone","bandeja"}

                def _tipo(i):
                    t = i.get("tipo_item")
                    if t in ("herramienta", "material", "equipo"):
                        return t
                    sub = i.get("subcategoria") or {}
                    cat = ((sub.get("categoria") or {}).get("nombre_categoria") or "").lower() if isinstance(sub, dict) else ""
                    snm = (sub.get("nombre") or "").lower() if isinstance(sub, dict) else str(sub).lower()
                    txt = f"{cat} {snm} {i.get('nombre','').lower()}"
                    for kw in _HERR_KWS:
                        if kw in txt: return "herramienta"
                    for kw in _MAT_KWS:
                        if kw in txt: return "material"
                    return "equipo"

                equipo_items = [i for i in (items or []) if _tipo(i) == "equipo"]
                herr_items   = [i for i in (items or []) if _tipo(i) == "herramienta"]
                cons_items   = [i for i in (items or []) if _tipo(i) == "material"]

                if equipo_items:
                    item_dd.options = [
                        ft.dropdown.Option(
                            key=str(i.get("id", i.get("_id"))),
                            text=f"{i.get('codigo','---')} — {i.get('nombre','---')}"
                        ) for i in equipo_items
                    ]
                    for i in equipo_items:
                        all_items_data[str(i.get("id", i.get("_id")))] = i
                else:
                    item_dd.options = [ft.dropdown.Option(key="null", text="Sin activos en STOCK")]

                if herr_items:
                    herr_dd.options = [
                        ft.dropdown.Option(
                            key=str(i.get("id", i.get("_id"))),
                            text=f"{i.get('codigo','---')} — {i.get('nombre','---')}"
                        ) for i in herr_items
                    ]
                    for i in herr_items:
                        all_herr_data[str(i.get("id", i.get("_id")))] = i
                else:
                    herr_dd.options = [ft.dropdown.Option(key="null", text="Sin herramientas en STOCK")]

                if cons_items:
                    cons_dd.options = [
                        ft.dropdown.Option(
                            key=str(i.get("id", i.get("_id"))),
                            text=f"{i.get('codigo','---')} — {i.get('nombre','---')} (Stock: {i.get('cantidad',0)})"
                        ) for i in cons_items
                    ]
                    for i in cons_items:
                        all_cons_data[str(i.get("id", i.get("_id")))] = i
                else:
                    cons_dd.options = [ft.dropdown.Option(key="null", text="Sin materiales en STOCK")]

                if facility:
                    c_id = facility.get("cliente", {})
                    t_id = facility.get("tecnico", {})
                    v_id = facility.get("vehiculo_id", "")
                    if isinstance(c_id, dict): cliente_dd.value = str(c_id.get("id", ""))
                    elif c_id: cliente_dd.value = str(c_id)
                    if isinstance(t_id, dict): tecnico_dd.value = str(t_id.get("id", ""))
                    elif t_id: tecnico_dd.value = str(t_id)
                    vehiculo_dd.value = str(v_id) if v_id else ""

                page.update()
            except Exception as e:
                show_snack(page, f"Error al cargar catálogos: {e}", True)

        # ── GUARDAR ───────────────────────────────────────────────────────────
        def save(e):
            if not codigo_tf.value:
                show_snack(page, "El código/OT es obligatorio", True); return
            if not cliente_dd.value:
                show_snack(page, "Selecciona un cliente", True); return
            if not tecnico_dd.value:
                show_snack(page, "Selecciona un técnico", True); return

            payload = {
                "codigo_instalacion":   codigo_tf.value.strip(),
                "cliente_id":           cliente_dd.value,
                "tecnico_id":           tecnico_dd.value,
                "vehiculo_id":          vehiculo_dd.value or "",
                "direccion_instalacion": dir_tf.value.strip(),
                "observaciones":        obs_tf.value.strip(),
                "fecha_programada":     fecha_tf.value + "T00:00:00Z" if fecha_tf.value else None,
                "items_planificados":   [{"item_id": i["item_id"]} for i in items_planificados],
                "herramientas": [
                    {
                        "item_id":      h["item_id"],
                        "nombre":       h["nombre"],
                        "codigo":       h["codigo"],
                        "cantidad":     h.get("cantidad", 1),
                        "observaciones": h.get("observaciones", ""),
                    }
                    for h in herramientas_list
                ],
                "consumibles": [
                    {
                        "item_id":          c["item_id"],
                        "nombre":           c["nombre"],
                        "codigo":           c["codigo"],
                        "unidad":           c.get("unidad", "unidad"),
                        "cantidad_reservada": c.get("cantidad_reservada", 1),
                        "observaciones":    c.get("observaciones", ""),
                    }
                    for c in consumibles_list
                ],
            }
            try:
                if is_new:
                    APIClient.post("inventory/facilities/", json=payload)
                    show_snack(page, "Instalación creada. Recursos reservados.")
                else:
                    APIClient.put(f"inventory/facilities/{facility['id']}/", json=payload)
                    show_snack(page, "Instalación actualizada.")
                navigate("facilities")
            except Exception as ex:
                show_snack(page, f"Error: {str(ex)}", True)

        # ── INICIAR ───────────────────────────────────────────────────────────
        def start_installation(e):
            try:
                start_facility(facility["id"])
                show_snack(page, "Instalación en proceso.")
                navigate("facilities")
            except Exception as ex:
                show_snack(page, f"Error: {str(ex)}", True)

        # ── MODAL CIERRE CON RETORNO OBLIGATORIO ──────────────────────────────
        def finish_installation(e):
            """
            Modal de cierre de instalación:
            - Sección A: Retorno de herramientas
            - Sección B: Liquidación de materiales
            - Sección C: Destino de equipos
            """
            # Estado local para el cierre
            herr_cierre = {
                h["item_id"]: {
                    "item_id":      h["item_id"],
                    "retorno":      True,
                    "estado_retorno": "STOCK",
                    "observaciones": "",
                }
                for h in herramientas_list
            }
            cons_cierre = {
                c["item_id"]: {
                    "item_id":      c["item_id"],
                    "cantidad_usada": c.get("cantidad_reservada", 1),
                }
                for c in consumibles_list
            }
            equipo_destinos = {it["item_id"]: "cliente" for it in items_planificados}

            # ── Sección A: Herramientas ───────────────────────────────────────
            herr_controls = []
            if not herramientas_list:
                herr_controls.append(ft.Text("Sin herramientas asignadas.", italic=True, size=12, color=ThemeColors.TEXT_SECONDARY))
            else:
                for h in herramientas_list:
                    iid = h["item_id"]

                    def make_herr_row(herr, hid):
                        retorno_cb = ft.Checkbox(value=True, label="Retornó a bodega")
                        estado_dd  = ft.Dropdown(
                            value="STOCK",
                            options=[
                                ft.dropdown.Option("STOCK",            "EN STOCK (normal)"),
                                ft.dropdown.Option("EN_MANTENIMIENTO", "EN MANTENIMIENTO (con daño)"),
                            ],
                            width=220, height=38, text_size=11,
                            **JetBrainsTheme.input_style(),
                        )
                        obs_tf_h = ft.TextField(
                            label="Observaciones", width=200, height=38, text_size=11,
                            **JetBrainsTheme.input_style(),
                        )

                        def on_retorno(e, _hid=hid):
                            herr_cierre[_hid]["retorno"] = e.control.value
                            estado_dd.disabled = not e.control.value
                            page.update()

                        def on_estado(e, _hid=hid):
                            herr_cierre[_hid]["estado_retorno"] = e.control.value

                        def on_obs(e, _hid=hid):
                            herr_cierre[_hid]["observaciones"] = e.control.value

                        retorno_cb.on_change = on_retorno
                        estado_dd.on_change  = on_estado
                        obs_tf_h.on_change   = on_obs

                        return ft.Container(
                            bgcolor=ft.colors.with_opacity(0.04, ft.colors.WHITE),
                            padding=10, border_radius=8, margin=ft.margin.only(bottom=6),
                            content=ft.Row([
                                ft.Icon(ft.icons.BUILD, size=14, color="#FF8F00"),
                                ft.Column([
                                    ft.Text(herr.get("nombre", "—"), weight="bold", size=12),
                                    ft.Text(f"SKU: {herr.get('codigo','—')}", size=10, color=ThemeColors.TEXT_SECONDARY),
                                ], spacing=1, width=140),
                                retorno_cb,
                                estado_dd,
                                obs_tf_h,
                            ], spacing=8, wrap=True)
                        )

                    herr_controls.append(make_herr_row(h, iid))

            # ── Sección B: Materiales ─────────────────────────────────────────
            cons_controls = []
            if not consumibles_list:
                cons_controls.append(ft.Text("Sin materiales asignados.", italic=True, size=12, color=ThemeColors.TEXT_SECONDARY))
            else:
                for c in consumibles_list:
                    iid        = c["item_id"]
                    reservado  = c.get("cantidad_reservada", 1)

                    retorno_text = ft.Text(f"Retorno: {reservado}", size=11, color=ThemeColors.STATE_STOCK)
                    usado_tf = ft.TextField(
                        value=str(reservado), width=80, height=38, text_size=12,
                        keyboard_type=ft.KeyboardType.NUMBER,
                        label="Usado", **JetBrainsTheme.input_style(),
                    )

                    def on_usado(e, _iid=iid, _res=reservado, _rt=retorno_text):
                        try:
                            usado = max(0, min(int(e.control.value or 0), _res))
                            ret   = _res - usado
                            cons_cierre[_iid]["cantidad_usada"] = usado
                            _rt.value = f"Retorno: {ret}"
                            page.update()
                        except (ValueError, TypeError):
                            pass

                    usado_tf.on_change = on_usado

                    cons_controls.append(ft.Container(
                        bgcolor=ft.colors.with_opacity(0.04, ft.colors.WHITE),
                        padding=10, border_radius=8, margin=ft.margin.only(bottom=6),
                        content=ft.Row([
                            ft.Icon(ft.icons.INVENTORY_2, size=14, color=ThemeColors.STATE_STOCK),
                            ft.Column([
                                ft.Text(c.get("nombre", "—"), weight="bold", size=12),
                                ft.Text(
                                    f"SKU: {c.get('codigo','—')} | "
                                    f"Reservado: {reservado} {c.get('unidad','u')}",
                                    size=10, color=ThemeColors.TEXT_SECONDARY
                                ),
                            ], spacing=1, width=180),
                            usado_tf,
                            retorno_text,
                        ], spacing=10, wrap=True)
                    ))

            # ── Sección C: Equipos ────────────────────────────────────────────
            equipo_controls = []
            if not items_planificados:
                equipo_controls.append(ft.Text("Sin equipos asignados.", italic=True, size=12, color=ThemeColors.TEXT_SECONDARY))
            else:
                for it in items_planificados:
                    iid = it["item_id"]

                    def make_equipo_row(item, eid):
                        seg = ft.SegmentedButton(
                            segments=[
                                ft.Segment(value="cliente", label=ft.Text("Cliente", size=11), icon=ft.Icon(ft.icons.PERSON_PIN)),
                                ft.Segment(value="bodega",  label=ft.Text("Bodega",  size=11), icon=ft.Icon(ft.icons.WAREHOUSE)),
                            ],
                            selected={"cliente"},
                            allow_multiple_selection=False,
                            on_change=lambda e, _eid=eid: equipo_destinos.update({_eid: list(e.control.selected)[0]}),
                        )
                        return ft.Row([
                            ft.Column([
                                ft.Text(item.get("nombre", "—"), weight="bold", size=12),
                                ft.Text(f"SN: {item.get('serial','—')}", size=10, color=ThemeColors.TEXT_SECONDARY),
                            ], expand=True),
                            seg,
                        ], spacing=10, vertical_alignment="center")

                    equipo_controls.append(make_equipo_row(it, iid))
                    if it != items_planificados[-1]:
                        equipo_controls.append(ft.Divider(height=1, color=ft.colors.with_opacity(0.05, ft.colors.WHITE)))

            def do_close(ev):
                page.dialog.open = False
                page.update()
                try:
                    items_dest = [{"item_id": k, "destino": v} for k, v in equipo_destinos.items()]
                    herr_list  = list(herr_cierre.values())
                    cons_list  = list(cons_cierre.values())
                    close_facility(facility["id"], items_dest, herr_list, cons_list)
                    show_snack(page, "Instalación cerrada exitosamente.")
                    navigate("facilities")
                except Exception as ex:
                    show_snack(page, f"Error al cerrar: {str(ex)}", True)

            modal_content = ft.Column([
                # Sección A
                ft.Container(
                    bgcolor=ft.colors.with_opacity(0.06, ft.colors.WHITE),
                    padding=12, border_radius=10,
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.icons.BUILD, color="#FF8F00", size=16), ft.Text("A — Retorno de Herramientas", weight="bold", size=13)], spacing=8),
                        ft.Column(herr_controls, spacing=0),
                    ], spacing=8)
                ),
                ft.Container(height=8),
                # Sección B
                ft.Container(
                    bgcolor=ft.colors.with_opacity(0.06, ft.colors.WHITE),
                    padding=12, border_radius=10,
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.icons.INVENTORY_2, color=ThemeColors.STATE_STOCK, size=16), ft.Text("B — Liquidación de Materiales", weight="bold", size=13)], spacing=8),
                        ft.Column(cons_controls, spacing=0),
                    ], spacing=8)
                ),
                ft.Container(height=8),
                # Sección C
                ft.Container(
                    bgcolor=ft.colors.with_opacity(0.06, ft.colors.WHITE),
                    padding=12, border_radius=10,
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.icons.DEVICES_OTHER_ROUNDED, color=ThemeColors.ACCENT_BLUE, size=16), ft.Text("C — Destino de Equipos", weight="bold", size=13)], spacing=8),
                        ft.Column(equipo_controls, spacing=6),
                    ], spacing=8)
                ),
            ], spacing=0, scroll=ft.ScrollMode.AUTO)

            page.dialog = ft.AlertDialog(
                modal=True,
                title=ft.Row([
                    ft.Icon(ft.icons.LOCK_CLOCK, color=ThemeColors.STATE_INSTALLED),
                    ft.Text("Cierre de Instalación", weight="bold"),
                ], spacing=10),
                content=ft.Container(width=680, height=520, content=modal_content),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                    ft.ElevatedButton(
                        "CERRAR INSTALACIÓN",
                        bgcolor=ThemeColors.STATE_INSTALLED, color=ft.colors.WHITE,
                        on_click=do_close,
                        icon=ft.icons.CHECK_CIRCLE,
                    ),
                ],
            )
            page.dialog.open = True
            page.update()

        # ── CANCELAR ─────────────────────────────────────────────────────────
        def cancel_installation(e):
            def do_cancel(ev):
                page.dialog.open = False
                page.update()
                try:
                    cancel_facility(facility["id"])
                    show_snack(page, "Instalación cancelada. Recursos devueltos a STOCK.")
                    navigate("facilities")
                except Exception as ex:
                    show_snack(page, f"Error: {str(ex)}", True)

            page.dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Cancelar Instalación", weight="bold"),
                content=ft.Text("¿Seguro? Los recursos regresarán a STOCK."),
                actions=[
                    ft.TextButton("No, volver", on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                    ft.ElevatedButton("Sí, cancelar", bgcolor=ft.colors.RED_700, color=ft.colors.WHITE, on_click=do_cancel),
                ],
            )
            page.dialog.open = True
            page.update()

        # ── PDF ───────────────────────────────────────────────────────────────
        def download_pdf(e):
            if not facility:
                return
            url = f"http://localhost:8000/api/inventory/facilities/{facility['id']}/report/"
            show_snack(page, "Generando reporte PDF...")
            webbrowser.open(url)

        # ── HELPER SECCIÓN CARD ───────────────────────────────────────────────
        def section_card(number, title, icon, content, badge_text=""):
            badge = ft.Container(
                content=ft.Text(badge_text, size=11, color=ft.colors.WHITE, weight="bold"),
                bgcolor=ThemeColors.ACCENT_BLUE,
                padding=ft.padding.symmetric(horizontal=8, vertical=2),
                border_radius=10, visible=bool(badge_text)
            ) if badge_text else ft.Container()

            return ft.Container(
                **JetBrainsTheme.card_style(),
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Text(number, size=12, weight="bold", color=ft.colors.WHITE),
                            bgcolor=ThemeColors.ACCENT_BLUE,
                            width=28, height=28, border_radius=14, alignment=ft.alignment.center
                        ),
                        ft.Icon(icon, color=ThemeColors.ACCENT_BLUE, size=20),
                        ft.Text(title, size=15, weight="bold", color=ThemeColors.TEXT_PRIMARY),
                        badge,
                    ], spacing=10),
                    ft.Divider(height=1, color=ft.colors.with_opacity(0.08, ft.colors.WHITE)),
                    content,
                ], spacing=12)
            )

        # ── BOTONES DE ACCIÓN ─────────────────────────────────────────────────
        action_buttons = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        if is_new:
            action_buttons.controls = [
                ft.ElevatedButton(
                    "Confirmar Instalación", icon=ft.icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                    style=JetBrainsTheme.primary_button_style(), on_click=save,
                ),
            ]
        elif estado == "planificada":
            action_buttons.controls = [
                ft.ElevatedButton("Guardar Cambios", style=JetBrainsTheme.primary_button_style(), on_click=save),
                ft.ElevatedButton("▶ Iniciar Instalación", bgcolor=ThemeColors.STATE_INSTALLED,
                                  color=ft.colors.WHITE, on_click=start_installation),
                ft.OutlinedButton("Cancelar Instalación", icon=ft.icons.CANCEL_OUTLINED, on_click=cancel_installation),
            ]
        elif estado == "en_proceso":
            action_buttons.controls = [
                ft.ElevatedButton("Guardar Destinos", style=JetBrainsTheme.primary_button_style(), on_click=save),
                ft.ElevatedButton("Cerrar Instalación", bgcolor=ThemeColors.ACCENT_BLUE,
                                  color=ft.colors.WHITE, on_click=finish_installation,
                                  icon=ft.icons.LOCK_CLOCK),
                ft.OutlinedButton("Cancelar Instalación", icon=ft.icons.CANCEL_OUTLINED, on_click=cancel_installation),
            ]
        elif estado == "finalizada":
            action_buttons.controls = [
                ft.ElevatedButton("Descargar Reporte PDF", icon=ft.icons.PICTURE_AS_PDF_ROUNDED,
                                  bgcolor=ft.colors.RED_700, color=ft.colors.WHITE, on_click=download_pdf),
            ]

        action_buttons.controls.append(
            ft.TextButton("← Volver al listado", on_click=lambda e: navigate("facilities"))
        )

        # ── TÍTULO ────────────────────────────────────────────────────────────
        page_title = "Nueva Instalación" if is_new else f"Instalación — {facility.get('codigo_instalacion', '')}"
        page_title_row = ft.Row([
            ft.IconButton(ft.icons.ARROW_BACK_ROUNDED, on_click=lambda e: navigate("facilities")),
            ft.Text(page_title, size=22, weight="bold"),
            status_badge(estado) if not is_new else ft.Container(),
        ], spacing=10)

        # ── RENDER INICIAL ────────────────────────────────────────────────────
        render_items()
        render_herr()
        render_cons()
        threading.Timer(0.2, load_data).start()

        # ── LAYOUT FINAL ──────────────────────────────────────────────────────
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Información General",
                    icon=ft.icons.INFO_OUTLINE_ROUNDED,
                    content=ft.Container(
                        padding=30,
                        content=ft.Column([
                            ft.Row([
                                ft.Container(codigo_tf, expand=38),
                                ft.Container(ft.Row([fecha_tf, fecha_btn], spacing=5), expand=62),
                            ], spacing=20),
                            ft.Row([cliente_dd], spacing=20),
                            ft.Row([
                                ft.Container(tecnico_dd, expand=62),
                                ft.Container(vehiculo_dd, expand=38),
                            ], spacing=20),
                            dir_tf,
                            obs_tf,
                        ], spacing=20, scroll="auto")
                    )
                ),
                ft.Tab(
                    text="Equipos (STOCK)",
                    icon=ft.icons.DEVICES_OTHER_ROUNDED,
                    content=ft.Container(
                        padding=20,
                        content=ft.Column([
                            ft.Row([
                                item_dd,
                                ft.IconButton(ft.icons.ADD_BOX_ROUNDED, icon_color=ThemeColors.ACCENT_BLUE,
                                              on_click=add_item, visible=not is_locked),
                            ], spacing=10),
                            ft.Container(content=items_col, expand=True),
                        ], spacing=15)
                    )
                ),
                ft.Tab(
                    text="Herramientas",
                    icon=ft.icons.HANDYMAN_ROUNDED,
                    content=ft.Container(
                        padding=20,
                        content=ft.Column([
                            ft.Row([
                                herr_dd,
                                ft.IconButton(ft.icons.ADD_BOX_ROUNDED, icon_color="#FF8F00",
                                              on_click=add_herr, visible=not is_locked),
                            ], spacing=10),
                            ft.Divider(height=1, color=ft.colors.with_opacity(0.06, ft.colors.WHITE)),
                            ft.Text("Herramientas seleccionadas:", size=11, weight="bold",
                                    color=ThemeColors.TEXT_SECONDARY),
                            ft.Container(content=herr_col, expand=True),
                        ], spacing=15)
                    )
                ),
                ft.Tab(
                    text="Materiales / Consumibles",
                    icon=ft.icons.INVENTORY_2_ROUNDED,
                    content=ft.Container(
                        padding=20,
                        content=ft.Column([
                            ft.Row([
                                cons_dd,
                                ft.IconButton(ft.icons.ADD_BOX_ROUNDED, icon_color=ThemeColors.STATE_STOCK,
                                              on_click=add_cons, visible=not is_locked),
                            ], spacing=10),
                            ft.Divider(height=1, color=ft.colors.with_opacity(0.06, ft.colors.WHITE)),
                            ft.Text("Materiales seleccionados:", size=11, weight="bold",
                                    color=ThemeColors.TEXT_SECONDARY),
                            ft.Container(content=cons_col, expand=True),
                        ], spacing=15)
                    )
                ),
            ],
            expand=True,
        )

        return ft.Column([
            page_title_row,
            ft.Row([
                ft.Column([
                    ft.Container(**JetBrainsTheme.card_style(), content=tabs, height=720)
                ], expand=162, spacing=15),
                ft.Column([
                    ft.Container(
                        **JetBrainsTheme.card_style(),
                        content=ft.Column([
                            ft.Text("Resumen y Acciones", size=18, weight="bold"),
                            ft.Divider(height=1, color=ft.colors.with_opacity(0.08, ft.colors.WHITE)),
                            ft.Container(summary_col, padding=ft.padding.only(top=10, bottom=10)),
                            ft.Container(height=15),
                            action_buttons,
                        ], spacing=15)
                    )
                ], expand=100, spacing=15),
            ], spacing=25, vertical_alignment=ft.CrossAxisAlignment.START),
        ], expand=True, spacing=15, scroll="auto")

    except Exception as ex:
        import traceback
        traceback.print_exc()
        return ft.Column([
            ft.Text("Error crítico al cargar el formulario", size=20, weight="bold", color=ft.colors.RED_700),
            ft.Text(str(ex), color=ThemeColors.TEXT_SECONDARY),
            ft.ElevatedButton("Volver al Listado", on_click=lambda e: navigate("facilities")),
        ], expand=True, alignment="center", horizontal_alignment="center")
