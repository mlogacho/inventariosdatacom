import flet as ft
import threading
from datetime import datetime, timedelta

from core.session import Session
from core.api_client import APIClient
from core.permissions import can_access
from core.theme import ThemeColors, JetBrainsTheme
from components.status_badge import status_badge
from services.item_service import list_items, create_item, transition_item
from services.facility_service import search_facilities
from services.category_service import list_categories
from services.subcategory_service import list_subcategories
from services.store_service import list_stores
from services.user_service import list_users
from services.customer_service import list_customers


def show_snack(page, msg, is_error=False):
    page.snack_bar = ft.SnackBar(
        ft.Text(msg, color=ft.colors.WHITE, weight="bold"),
        bgcolor=ft.colors.RED_700 if is_error else ft.colors.GREEN_700,
        duration=3000,
    )
    page.snack_bar.open = True
    page.update()


# Transiciones permitidas (frontend — el backend las revalida)
TRANSITIONS = {
    # Equipos / Activos de oficina
    "STOCK":              ["RESERVADO", "DEVOLUCION_PROVEEDOR", "OBSOLETO"],
    "RESERVADO":          ["SALIDA_INSTALACION", "STOCK"],
    "SALIDA_INSTALACION": ["INSTALADO_CLIENTE", "REINGRESO_BODEGA"],
    "INSTALADO_CLIENTE":  ["REINGRESO_BODEGA", "ACTIVO_EN_CAMPO"],
    "REINGRESO_BODEGA":   ["STOCK"],
    # Herramientas
    "RESERVADA":          ["EN_USO", "STOCK"],
    "EN_USO":             ["STOCK", "EN_MANTENIMIENTO"],
    "EN_MANTENIMIENTO":   ["STOCK"],
    # Materiales (cierre de instalación genera estos vía API; aquí solo retorno parcial)
    "PARCIALMENTE_USADO": ["STOCK"],
}
TERMINAL_STATES = {"DEVOLUCION_PROVEEDOR", "OBSOLETO", "ACTIVO_EN_CAMPO", "OBSOLETA", "CONSUMIDO"}

# Estado options por tipo de ítem (para filtro dinámico)
_ESTADOS_EQUIPO      = ["STOCK", "RESERVADO", "SALIDA_INSTALACION", "INSTALADO_CLIENTE",
                        "REINGRESO_BODEGA", "ACTIVO_EN_CAMPO", "DEVOLUCION_PROVEEDOR", "OBSOLETO"]
_ESTADOS_HERRAMIENTA = ["STOCK", "RESERVADA", "EN_USO", "EN_MANTENIMIENTO", "OBSOLETA"]
_ESTADOS_MATERIAL    = ["STOCK", "RESERVADO", "CONSUMIDO", "PARCIALMENTE_USADO", "OBSOLETO"]
_ESTADOS_ALL         = sorted(set(_ESTADOS_EQUIPO + _ESTADOS_HERRAMIENTA + _ESTADOS_MATERIAL))

_STATE_LABEL = {
    "STOCK": "EN STOCK", "RESERVADO": "RESERVADO", "RESERVADA": "RESERVADA",
    "SALIDA_INSTALACION": "SALIDA INSTALACIÓN", "INSTALADO_CLIENTE": "INSTALADO CLIENTE",
    "REINGRESO_BODEGA": "REINGRESO BODEGA", "ACTIVO_EN_CAMPO": "ACTIVO EN CAMPO",
    "DEVOLUCION_PROVEEDOR": "DEVOLUCIÓN PROVEEDOR", "OBSOLETO": "DADO DE BAJA",
    "OBSOLETA": "OBSOLETA", "EN_USO": "EN USO", "EN_MANTENIMIENTO": "EN MANTENIMIENTO",
    "CONSUMIDO": "CONSUMIDO", "PARCIALMENTE_USADO": "PARCIALMENTE USADO",
}


# ─── VISTA LISTA ─────────────────────────────────────────────────────────────
def item_view(page: ft.Page, navigate):
    rol = (Session.user or {}).get("rol", "tecnico")

    # ── Definición de los 4 grupos de categorías ──────────────────────────────
    GROUPS = [
        {
            "name": "ACTIVOS DE OFICINA",
            "icon": ft.icons.COMPUTER,
            "color": "#4fc3f7",
            "keywords": [
                "oficina", "computadora", "monitor", "escritorio", "silla",
                "impresora", "telefono", "teléfono", "laptop", "pc", "teclado",
                "mouse", "scanner", "escaner", "proyector",
            ],
        },
        {
            "name": "HERRAMIENTAS",
            "icon": ft.icons.BUILD,
            "color": "#ffb74d",
            "keywords": [
                "herramienta", "taladro", "llave", "crimpadora", "escalera",
                "alicate", "destornillador", "pinza", "sierra", "martillo",
                "nivel", "corta", "ponchadora",
            ],
        },
        {
            "name": "MATERIALES",
            "icon": ft.icons.INVENTORY_2,
            "color": "#81c784",
            "keywords": [
                "material", "cable", "conector", "papel", "tinta", "consumible",
                "canaleta", "patch", "utp", "fibra", "ducto", "tornillo",
                "etiqueta", "brida", "cinta",
            ],
        },
        {
            "name": "EQUIPOS",
            "icon": ft.icons.SETTINGS_INPUT_COMPONENT,
            "color": "#ce93d8",
            "keywords": [
                "equipo", "servidor", "switch", "router", "ap", "firewall",
                "ups", "radio", "camara", "cámara", "access", "ntc", "olt",
                "ont", "mikrotik", "ubiquiti",
            ],
        },
    ]

    def classify(item):
        sub = item.get("subcategoria") or {}
        if isinstance(sub, dict):
            cat_name = ((sub.get("categoria") or {}).get("nombre_categoria") or "").lower()
            sub_name = (sub.get("nombre") or "").lower()
        else:
            cat_name, sub_name = "", str(sub).lower()
        text = f"{cat_name} {sub_name} {(item.get('nombre') or '').lower()}".strip()
        
        # 1. Prioridad: Búsqueda por palabras clave
        for g in GROUPS:
            for kw in g["keywords"]:
                if kw.lower() in text:
                    return g["name"].strip().upper()
                    
        # 2. Fallback: Tipos de ítem explícitos del backend
        tipo = str(item.get("tipo_item") or "").lower().strip()
        if tipo == "herramienta":
            return "HERRAMIENTAS"
        if tipo == "material":
            return "MATERIALES"
        if tipo == "equipo":
            return "EQUIPOS"
            
        return "EQUIPOS"

    # ── Estado de la aplicación ───────────────────────────────────────────────
    all_items      = []
    filtered_items = []
    adv_open       = [False]

    # ── Controles de UI ───────────────────────────────────────────────────────
    loading         = ft.ProgressBar(visible=False, color=ThemeColors.ACCENT_BLUE)
    results_text    = ft.Text("", size=12, color=ThemeColors.TEXT_SECONDARY)
    results_text2   = ft.Text("", size=12, color=ThemeColors.TEXT_SECONDARY)
    cards_row       = ft.Column(spacing=12)
    rows_col        = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)

    # Filtros básicos
    search_tf = ft.TextField(
        hint_text="Nombre, SKU o serie...",
        prefix_icon=ft.icons.SEARCH,
        width=295, height=44,
        on_change=lambda _: apply_filters(),
        **JetBrainsTheme.input_style(),
    )

    def _build_estado_opts(states):
        return [ft.dropdown.Option("TODOS")] + [
            ft.dropdown.Option(s, _STATE_LABEL.get(s, s)) for s in states
        ]

    estado_dd = ft.Dropdown(
        label="Estado",
        width=200,
        options=_build_estado_opts(_ESTADOS_ALL),
        value="TODOS",
        on_change=lambda _: apply_filters(),
        **JetBrainsTheme.input_style(),
    )

    # Checkboxes de categoría
    cat_checks = {
        g["name"]: ft.Checkbox(label=g["name"], value=False, on_change=lambda _: _on_cat_filter())
        for g in GROUPS
    }

    def _update_estado_options():
        sel = {n for n, c in cat_checks.items() if c.value}
        if len(sel) == 1:
            name = next(iter(sel))
            if name == "HERRAMIENTAS":
                states = _ESTADOS_HERRAMIENTA
            elif name == "MATERIALES":
                states = _ESTADOS_MATERIAL
            else:
                states = _ESTADOS_EQUIPO
        else:
            states = _ESTADOS_ALL
        estado_dd.options = _build_estado_opts(states)
        valid_keys = {s for s in states}
        if estado_dd.value and estado_dd.value != "TODOS" and estado_dd.value not in valid_keys:
            estado_dd.value = "TODOS"
        estado_dd.update()

    def _on_cat_filter():
        _update_estado_options()
        apply_filters()

    # Date pickers
    dp_from = ft.DatePicker()
    dp_to   = ft.DatePicker()
    if dp_from not in page.overlay:
        page.overlay.extend([dp_from, dp_to])

    desde_tf = ft.TextField(label="Desde", width=112, read_only=True, **JetBrainsTheme.input_style())
    hasta_tf = ft.TextField(label="Hasta", width=112, read_only=True, **JetBrainsTheme.input_style())

    def _on_from(e):
        if dp_from.value:
            desde_tf.value = dp_from.value.strftime("%Y-%m-%d")
            apply_filters()

    def _on_to(e):
        if dp_to.value:
            hasta_tf.value = dp_to.value.strftime("%Y-%m-%d")
            apply_filters()

    dp_from.on_change = _on_from
    dp_to.on_change   = _on_to

    # Filtros avanzados
    adv_sku_tf   = ft.TextField(label="SKU / Código exacto", width=200, on_change=lambda _: apply_filters(), **JetBrainsTheme.input_style())
    adv_critical = ft.Checkbox(label="Solo stock crítico (≤ 1 unidad por SKU)", value=False, on_change=lambda _: apply_filters())
    adv_no_mov   = ft.Checkbox(label="Sin movimiento > 30 días", value=False, on_change=lambda _: apply_filters())

    adv_panel = ft.Container(
        visible=False,
        padding=ft.padding.only(top=6),
        content=ft.Column([
            ft.Divider(height=6, color=ft.colors.with_opacity(0.06, ft.colors.WHITE)),
            ft.Text("FILTROS AVANZADOS", size=10, weight="bold", color=ThemeColors.TEXT_SECONDARY),
            ft.Row([adv_sku_tf, adv_critical, adv_no_mov], spacing=20, wrap=True),
        ], spacing=8),
    )

    toggle_adv_btn = ft.TextButton(
        "▼  Filtros avanzados",
        style=ft.ButtonStyle(color=ThemeColors.ACCENT_BLUE),
    )

    def toggle_adv(e):
        adv_open[0] = not adv_open[0]
        adv_panel.visible = adv_open[0]
        toggle_adv_btn.text = (
            "▲  Ocultar filtros avanzados" if adv_open[0] else "▼  Filtros avanzados"
        )
        page.update()

    toggle_adv_btn.on_click = toggle_adv

    def _shortcut(days):
        today = datetime.now()
        desde_tf.value = (today - timedelta(days=days)).strftime("%Y-%m-%d") if days > 0 else today.strftime("%Y-%m-%d")
        hasta_tf.value = today.strftime("%Y-%m-%d")
        apply_filters()

    # ── Lógica de filtrado en memoria ─────────────────────────────────────────
    def apply_filters(e=None):
        search      = (search_tf.value or "").lower().strip()
        # Normalizar filtro de estado
        estado_filtro = str(estado_dd.value or "TODOS").strip().upper()
        
        sel_cats    = {n.strip().upper() for n, c in cat_checks.items() if c.value}
        sku_exact   = (adv_sku_tf.value or "").strip().lower()
        only_crit   = adv_critical.value
        only_no_mov = adv_no_mov.value
        date_from   = desde_tf.value or ""
        date_to     = hasta_tf.value or ""
        cutoff_30d  = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        # Precalcular stock por SKU para filtro crítico
        stock_by_sku = {}
        for item in all_items:
            if item.get("estado") == "STOCK":
                k = item.get("codigo", "")
                stock_by_sku[k] = stock_by_sku.get(k, 0) + 1

        result = []
        for item in all_items:
            item_class = classify(item).strip().upper()
            
            if search:
                hay = " ".join([
                    item.get("nombre", ""), item.get("codigo", ""),
                    item.get("serial", ""), item.get("marca", ""),
                ]).lower()
                if search not in hay:
                    continue

            # Filtro por estado: Solo si NO es "TODOS"
            if estado_filtro != "TODOS" and estado_filtro != "":
                item_estado = str(item.get("estado") or "").strip().upper()
                if item_estado != estado_filtro:
                    continue

            if sel_cats and item_class not in sel_cats:
                continue
            if sku_exact and item.get("codigo", "").lower() != sku_exact:
                continue
            item_date = (item.get("fecha_creacion") or item.get("created_at") or "")[:10]
            if date_from and item_date and item_date < date_from:
                continue
            if date_to and item_date and item_date > date_to:
                continue
            if only_crit:
                if item.get("estado") != "STOCK":
                    continue
                if stock_by_sku.get(item.get("codigo", ""), 0) > 1:
                    continue
            if only_no_mov:
                last_upd = (item.get("updated_at") or item.get("fecha_actualizacion") or "")[:10]
                if last_upd and last_upd >= cutoff_30d:
                    continue
            result.append(item)

        filtered_items.clear()
        filtered_items.extend(result)
        refresh_cards()
        refresh_table()
        count_str = f"{len(filtered_items)} / {len(all_items)} ítems"
        results_text.value  = count_str
        results_text2.value = count_str
        page.update()

    def clear_filters(e=None):
        search_tf.value    = ""
        estado_dd.value    = "TODOS"
        desde_tf.value     = ""
        hasta_tf.value     = ""
        adv_sku_tf.value   = ""
        adv_critical.value = False
        adv_no_mov.value   = False
        for chk in cat_checks.values():
            chk.value = False
        apply_filters()

    # ── Tarjetas de resumen ───────────────────────────────────────────────────
    def build_card(group):
        name  = group["name"]
        color = group["color"]
        icon  = group["icon"]

        items_g  = [i for i in filtered_items if classify(i) == name]
        in_stock = [i for i in items_g if i.get("estado") == "STOCK"]

        by_nombre = {}
        for i in in_stock:
            k = i.get("nombre") or i.get("codigo") or "—"
            by_nombre[k] = by_nombre.get(k, 0) + 1

        top5    = sorted(by_nombre.items(), key=lambda x: x[1], reverse=True)[:5]
        max_val = top5[0][1] if top5 else 1

        bars = []
        for bname, cnt in top5:
            bw = max(5, int(108 * cnt / max_val))
            label = (bname[:12] + "…") if len(bname) > 12 else bname
            bars.append(ft.Row([
                ft.Container(
                    width=90,
                    content=ft.Text(label, size=9, color=ThemeColors.TEXT_SECONDARY,
                                   overflow=ft.TextOverflow.ELLIPSIS),
                ),
                ft.Container(height=10, width=bw, bgcolor=color, border_radius=3),
                ft.Text(str(cnt), size=9, color=ThemeColors.TEXT_SECONDARY),
            ], spacing=4))

        return ft.Container(
            bgcolor=ft.colors.with_opacity(0.08, ft.colors.WHITE),
            padding=16,
            border_radius=14,
            ink=True,
            border=ft.border.all(1, ft.colors.with_opacity(0.12, ft.colors.WHITE)),
            on_click=lambda e, gn=name: _open_category(gn),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        ft.colors.with_opacity(0.13, ft.colors.WHITE) if e.data == "true"
                        else ft.colors.with_opacity(0.08, ft.colors.WHITE)) or page.update()
            ),
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, color=color, size=18),
                    ft.Text(name, size=11, weight="bold", color=ft.colors.WHITE),
                ], spacing=8),
                ft.Divider(height=6, color=ft.colors.with_opacity(0.06, ft.colors.WHITE)),
                ft.Row([
                    ft.Column([
                        ft.Text("TOTAL",  size=9, weight="bold", color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(str(len(items_g)), size=20, weight="bold", color=ft.colors.WHITE),
                    ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(width=1, height=36, bgcolor=ft.colors.with_opacity(0.12, ft.colors.WHITE)),
                    ft.Column([
                        ft.Text("STOCK",  size=9, weight="bold", color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(str(len(in_stock)), size=20, weight="bold", color=color),
                    ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ], spacing=10, alignment=ft.MainAxisAlignment.SPACE_EVENLY),
                ft.Divider(height=6, color=ft.colors.with_opacity(0.06, ft.colors.WHITE)),
                ft.Text("TOP 5 EN STOCK", size=9, weight="bold", color=ThemeColors.TEXT_SECONDARY),
                ft.Column(
                    bars if bars else [
                        ft.Text("Sin unidades en stock", size=10, italic=True,
                               color=ThemeColors.TEXT_SECONDARY)
                    ],
                    spacing=3,
                ),
            ], spacing=6),
        )

    def _open_category(group_name):
        page.session.set("category_group", group_name)
        navigate("category_items")

    def refresh_cards():
        cards_row.controls = [build_card(g) for g in GROUPS]

    # ── Tabla detallada ───────────────────────────────────────────────────────
    COL = {"cod": 95, "cat": 115, "nom": 210, "est": 145, "ub": 120, "ot": 90, "acc": 110}

    header_row = ft.Container(
        bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
        content=ft.Row([
            ft.Container(width=COL["cod"],  content=ft.Text("CÓDIGO",    size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["cat"],  content=ft.Text("CATEGORÍA", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["nom"],  content=ft.Text("ACTIVO",    size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["est"],  content=ft.Text("ESTADO",    size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["ub"],   content=ft.Text("UBICACIÓN", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["ot"],   content=ft.Text("OT",        size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["acc"],  content=ft.Text("ACCIONES",  size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
        ], spacing=8),
    )

    def _make_row(item):
        estado      = item.get("estado", "STOCK")
        is_terminal = estado in TERMINAL_STATES
        grp         = next((g for g in GROUPS if g["name"] == classify(item)), GROUPS[-1])

        sub     = item.get("subcategoria") or {}
        cat_obj = (sub.get("categoria") or {}) if isinstance(sub, dict) else {}
        cat_lbl = cat_obj.get("nombre_categoria") or (sub.get("nombre") if isinstance(sub, dict) else "") or grp["name"]
        marcmod = f"{item.get('marca', '')} {item.get('modelo', '')}".strip() or "—"
        ub_val  = item.get("ubicacion_nombre") or "—"
        ot_val  = item.get("ot_id") or "—"

        actions = []
        actions.append(ft.IconButton(
            icon=ft.icons.TIMELINE,
            icon_color=ThemeColors.ACCENT_BLUE,
            icon_size=18,
            tooltip="Ver Trazabilidad",
            on_click=lambda e, it=item: navigate("item_traceability", item_id=it["id"], item_data=it),
        ))
        if not is_terminal and can_access(rol, "item:update"):
            actions.append(ft.IconButton(
                icon=ft.icons.RECYCLING,
                icon_color=ThemeColors.ACCENT_BLUE,
                icon_size=18,
                tooltip="Ciclo de Vida",
                on_click=lambda e, it=item: open_transition(it),
            ))
        if can_access(rol, "item:update"):
            actions.append(ft.IconButton(
                icon=ft.icons.EDIT_NOTE_ROUNDED,
                icon_color=ThemeColors.TEXT_SECONDARY,
                icon_size=18,
                tooltip="Editar Activo",
                on_click=lambda e, it=item: open_edit(it),
            ))
        if can_access(rol, "item:delete"):
            actions.append(ft.IconButton(
                icon=ft.icons.DELETE_SWEEP_ROUNDED,
                icon_color=ft.colors.RED_400,
                icon_size=18,
                tooltip="Eliminar Activo",
                on_click=lambda e, it=item: confirm_delete(it),
            ))

        return ft.Container(
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.colors.with_opacity(0.05, ft.colors.WHITE))),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        ft.colors.with_opacity(0.04, ft.colors.WHITE) if e.data == "true"
                        else ft.colors.TRANSPARENT)
                or page.update()
            ),
            content=ft.Row([
                ft.Container(width=COL["cod"],
                             content=ft.Text(item.get("codigo", "—"), size=12, weight="bold",
                                            color=ThemeColors.ACCENT_BLUE,
                                            overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=COL["cat"],
                             content=ft.Row([
                                 ft.Icon(grp["icon"], size=12, color=grp["color"]),
                                 ft.Text(str(cat_lbl)[:13], size=11, color=grp["color"],
                                        overflow=ft.TextOverflow.ELLIPSIS),
                             ], spacing=4)),
                ft.Container(width=COL["nom"],
                             content=ft.Column([
                                 ft.Text(item.get("nombre", "—"), size=13, weight="bold",
                                        overflow=ft.TextOverflow.ELLIPSIS),
                                 ft.Text(marcmod, size=11, color=ThemeColors.TEXT_SECONDARY,
                                        overflow=ft.TextOverflow.ELLIPSIS),
                             ], spacing=0, tight=True)),
                ft.Container(width=COL["est"],  content=status_badge(estado)),
                ft.Container(width=COL["ub"],
                             content=ft.Text(ub_val, size=11, color=ThemeColors.TEXT_SECONDARY,
                                            overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=COL["ot"],
                             content=ft.Text(ot_val, size=11,
                                            color=ThemeColors.ACCENT_BLUE if item.get("ot_id") else ThemeColors.TEXT_SECONDARY,
                                            overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=COL["acc"], content=ft.Row(actions, spacing=2)),
            ], spacing=8),
        )

    def refresh_table():
        rows_col.controls.clear()
        if not filtered_items:
            rows_col.controls.append(ft.Container(
                padding=ft.padding.all(30),
                content=ft.Text("No hay ítems que coincidan con los filtros.",
                               italic=True, color=ThemeColors.TEXT_SECONDARY),
            ))
        else:
            for item in filtered_items:
                rows_col.controls.append(_make_row(item))

    # ── Carga de datos ────────────────────────────────────────────────────────
    def load_data():
        loading.visible = True
        page.update()
        try:
            data = list_items({}) or []
            all_items.clear()
            all_items.extend(data)
            filtered_items.clear()
            filtered_items.extend(data)
            refresh_cards()
            refresh_table()
            count_str = f"{len(data)} ítems en total"
            results_text.value  = count_str
            results_text2.value = count_str
        except Exception as ex:
            show_snack(page, f"Error al cargar activos: {ex}", True)
        finally:
            loading.visible = False
            page.update()

    def reload():
        threading.Thread(target=load_data, daemon=True).start()

    # ── Transición de estados (lógica original preservada) ────────────────────
    def open_transition(item):
        current = item.get("estado", "STOCK")
        allowed = TRANSITIONS.get(current, [])
        if not allowed:
            show_snack(page, "El activo está en un estado terminal.", True)
            return

        next_dd  = ft.Dropdown(label="Siguiente Estado",
                               options=[ft.dropdown.Option(s) for s in allowed],
                               **JetBrainsTheme.input_style(), expand=True)
        ot_col   = ft.Column(visible=False, spacing=8)
        ot_tf    = ft.TextField(label="Buscar OT por código", **JetBrainsTheme.input_style())
        ot_list  = ft.Column(spacing=4)
        ot_label = ft.Text("Sin OT seleccionada", size=12, color=ThemeColors.TEXT_SECONDARY)
        ot_id    = [None]

        def _search_ot(e):
            q = e.control.value
            if len(q) < 2:
                return
            try:
                facs = search_facilities(q) or []
                ot_list.controls = [
                    ft.ListTile(
                        title=ft.Text(f["codigo_instalacion"]),
                        subtitle=ft.Text((f.get("cliente") or {}).get("nombre_cliente", "---")),
                        on_click=lambda e, f=f: _pick(f),
                        dense=True,
                    ) for f in facs
                ]
                page.update()
            except Exception:
                pass

        def _pick(fac):
            ot_id[0]      = fac["codigo_instalacion"]
            ot_label.value = f"OT: {ot_id[0]}"
            ot_label.color = ThemeColors.ACCENT_BLUE
            ot_list.controls.clear()
            page.update()

        def on_state(e):
            ot_col.visible = (e.control.value == "RESERVADO")
            page.update()

        ot_tf.on_change   = _search_ot
        next_dd.on_change = on_state
        ot_col.controls   = [ot_tf, ot_label, ot_list]
        notes_tf = ft.TextField(label="Observaciones", multiline=True, min_lines=2,
                                **JetBrainsTheme.input_style())

        def do_transition(e):
            if not next_dd.value:
                show_snack(page, "Selecciona el siguiente estado", True)
                return
            if next_dd.value == "RESERVADO" and not ot_id[0]:
                show_snack(page, "La OT es obligatoria para RESERVAR", True)
                return
            try:
                transition_item(item["id"], next_dd.value, ot_id=ot_id[0], notes=notes_tf.value)
                page.dialog.open = False
                page.update()
                show_snack(page, "Transición ejecutada")
                reload()
            except Exception as ex:
                show_snack(page, str(ex), True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.RECYCLING, color=ThemeColors.ACCENT_BLUE),
                ft.Text(f"Ciclo de Vida: {item.get('codigo')}", weight="bold"),
            ], spacing=10),
            content=ft.Container(width=480, content=ft.Column([
                ft.Row([ft.Text("Estado actual:", size=12, color=ThemeColors.TEXT_SECONDARY),
                        status_badge(current)], spacing=8),
                next_dd,
                ot_col,
                notes_tf,
            ], tight=True, spacing=15)),
            actions=[
                ft.TextButton("Cancelar",
                              on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Ejecutar", style=JetBrainsTheme.primary_button_style(),
                                  on_click=do_transition),
            ],
        )
        page.dialog.open = True
        page.update()

    # ── Editar activo (lógica original preservada) ────────────────────────────
    def open_edit(item):
        nombre_tf = ft.TextField(label="Nombre del Activo", value=item.get("nombre", ""),
                                 expand=True, **JetBrainsTheme.input_style())
        marca_tf  = ft.TextField(label="Marca",  value=item.get("marca",  ""),
                                 expand=True, **JetBrainsTheme.input_style())
        modelo_tf = ft.TextField(label="Modelo", value=item.get("modelo", ""),
                                 expand=True, **JetBrainsTheme.input_style())
        serial_tf = ft.TextField(label="Número de Serie", value=item.get("serial", ""),
                                 expand=True, **JetBrainsTheme.input_style())
        crit_dd   = ft.Dropdown(
            label="Criticidad",
            value=item.get("criticidad", "media"),
            options=[
                ft.dropdown.Option("alta",  text="Alta"),
                ft.dropdown.Option("media", text="Media"),
                ft.dropdown.Option("baja",  text="Baja"),
            ],
            **JetBrainsTheme.input_style(),
        )
        cat_dd = ft.Dropdown(label="Categoría", expand=True, **JetBrainsTheme.input_style())
        sub_dd = ft.Dropdown(label="Subcategoría", expand=True, disabled=True,
                             **JetBrainsTheme.input_style())

        def _load_cats():
            try:
                cats = list_categories() or []
                cat_dd.options = [ft.dropdown.Option(key=c["id"], text=c["nombre_categoria"]) for c in cats]
                cur_sub = item.get("subcategoria") or {}
                cur_cat = (cur_sub.get("categoria") or {}).get("id")
                if cur_cat:
                    cat_dd.value = cur_cat
                    _load_subs(cur_cat, pre=cur_sub.get("id"))
                else:
                    page.update()
            except Exception:
                pass

        def _load_subs(cat_id, pre=None):
            try:
                subs = list_subcategories({"category_id": cat_id}) or []
                sub_dd.options  = [ft.dropdown.Option(key=s["id"], text=s["nombre"]) for s in subs]
                sub_dd.disabled = False
                if pre:
                    sub_dd.value = pre
                page.update()
            except Exception:
                pass

        def on_cat(e):
            sub_dd.value    = None
            sub_dd.options  = []
            sub_dd.disabled = True
            page.update()
            if cat_dd.value:
                threading.Thread(target=_load_subs, args=(cat_dd.value,), daemon=True).start()

        cat_dd.on_change = on_cat
        threading.Timer(0.15, _load_cats).start()

        def save(e):
            if not nombre_tf.value.strip():
                show_snack(page, "El nombre es obligatorio", True)
                return
            payload = {
                "nombre":     nombre_tf.value.strip(),
                "marca":      marca_tf.value.strip(),
                "modelo":     modelo_tf.value.strip(),
                "serial":     serial_tf.value.strip(),
                "criticidad": crit_dd.value or "media",
            }
            if sub_dd.value:
                payload["subcategoria_id"] = sub_dd.value
            try:
                APIClient.put(f"inventory/items/{item['id']}/", json=payload)
                page.dialog.open = False
                page.update()
                show_snack(page, f"Activo '{item.get('codigo')}' actualizado")
                reload()
            except Exception as ex:
                show_snack(page, f"Error al actualizar: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.EDIT_ROUNDED, color=ThemeColors.ACCENT_BLUE),
                ft.Text(f"Editar: {item.get('codigo')}", weight="bold"),
            ], spacing=10),
            content=ft.Container(width=540, content=ft.Column([
                nombre_tf,
                ft.Row([marca_tf, modelo_tf], spacing=12),
                serial_tf,
                crit_dd,
                ft.Divider(height=6, color=ft.colors.with_opacity(0.06, ft.colors.WHITE)),
                ft.Text("Cambiar categoría (opcional)", size=11,
                        color=ThemeColors.TEXT_SECONDARY, italic=True),
                ft.Row([cat_dd, sub_dd], spacing=12),
            ], tight=True, spacing=12, scroll=ft.ScrollMode.AUTO)),
            actions=[
                ft.TextButton("Cancelar",
                              on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Guardar Cambios", style=JetBrainsTheme.primary_button_style(),
                                  on_click=save),
            ],
        )
        page.dialog.open = True
        page.update()

    # ── Eliminar activo (lógica original preservada) ──────────────────────────
    def confirm_delete(item):
        def do_delete(e):
            try:
                APIClient.delete(f"inventory/items/{item['id']}/")
                page.dialog.open = False
                page.update()
                show_snack(page, f"Activo '{item.get('codigo')}' eliminado")
                reload()
            except Exception as ex:
                show_snack(page, f"Error al eliminar: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.WARNING_ROUNDED, color=ft.colors.RED_400),
                ft.Text("Eliminar Activo", weight="bold"),
            ], spacing=10),
            content=ft.Text(
                f"¿Eliminar el activo '{item.get('codigo')} — {item.get('nombre')}'?\n"
                "El activo pasará a inactivo permanentemente.",
                size=14,
            ),
            actions=[
                ft.TextButton("Cancelar",
                              on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Sí, eliminar", bgcolor=ft.colors.RED_700,
                                  color=ft.colors.WHITE, on_click=do_delete),
            ],
        )
        page.dialog.open = True
        page.update()

    # ── Inicio ────────────────────────────────────────────────────────────────
    threading.Timer(0.1, load_data).start()

    # ── Layout ────────────────────────────────────────────────────────────────
    return ft.Column([
        # Cabecera
        ft.Row([
            ft.Text("Inventario — Stock en Tiempo Real", size=22, weight="bold",
                    color=ThemeColors.TEXT_PRIMARY),
            ft.Row([
                ft.ElevatedButton(
                    "Actualizar", icon=ft.icons.REFRESH_ROUNDED,
                    style=JetBrainsTheme.primary_button_style(),
                    on_click=lambda e: reload(), height=42,
                ),
                ft.ElevatedButton(
                    "Nuevo Activo", icon=ft.icons.ADD_ROUNDED,
                    style=JetBrainsTheme.primary_button_style(),
                    on_click=lambda e: navigate("create_item"),
                    visible=can_access(rol, "item:create"), height=42,
                ),
            ], spacing=10),
        ], alignment="spaceBetween"),

        # Panel de filtros
        ft.Container(
            **JetBrainsTheme.card_style(),
            content=ft.Column([
                # Fila 1: búsqueda + estado + fechas + botón limpiar + contador
                ft.Row([
                    search_tf,
                    estado_dd,
                    ft.Row([
                        ft.IconButton(ft.icons.CALENDAR_MONTH, icon_color=ThemeColors.ACCENT_BLUE,
                                     on_click=lambda _: dp_from.pick_date(), tooltip="Fecha desde"),
                        desde_tf,
                        ft.Text("→", color=ThemeColors.TEXT_SECONDARY, size=14),
                        hasta_tf,
                        ft.IconButton(ft.icons.CALENDAR_MONTH, icon_color=ThemeColors.ACCENT_BLUE,
                                     on_click=lambda _: dp_to.pick_date(), tooltip="Fecha hasta"),
                    ], spacing=4),
                    ft.ElevatedButton(
                        "Limpiar todo", icon=ft.icons.CLEAR_ROUNDED,
                        on_click=clear_filters, height=40,
                        style=ft.ButtonStyle(
                            color=ft.colors.WHITE,
                            bgcolor=ft.colors.with_opacity(0.1, ft.colors.WHITE),
                        ),
                    ),
                    results_text,
                ], spacing=10, wrap=True),
                # Fila 2: filtro por categoría
                ft.Row([
                    ft.Text("Categoría:", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY),
                ] + list(cat_checks.values()), spacing=12, wrap=True),
                # Fila 3: atajos de fecha
                ft.Row([
                    ft.Text("Período:", size=11, color=ThemeColors.TEXT_SECONDARY),
                    ft.TextButton("Hoy",      on_click=lambda _: _shortcut(0),
                                 style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY)),
                    ft.TextButton("7 días",   on_click=lambda _: _shortcut(7),
                                 style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY)),
                    ft.TextButton("30 días",  on_click=lambda _: _shortcut(30),
                                 style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY)),
                    ft.TextButton("Este año", on_click=lambda _: _shortcut(365),
                                 style=ft.ButtonStyle(color=ThemeColors.TEXT_SECONDARY)),
                ], spacing=2),
                # Toggle filtros avanzados
                ft.Row([toggle_adv_btn]),
                adv_panel,
            ], spacing=10),
        ),

        loading,

        # 4 tarjetas de resumen
        cards_row,

        # Tabla detallada
        ft.Container(
            **JetBrainsTheme.card_style(),
            expand=True,
            content=ft.Column([
                ft.Row([
                    ft.Text("INVENTARIO DETALLADO", size=13, weight="bold",
                            color=ThemeColors.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    results_text2,
                ]),
                ft.Divider(height=1, color=ft.colors.with_opacity(0.08, ft.colors.WHITE)),
                header_row,
                ft.Divider(height=1, color=ft.colors.with_opacity(0.06, ft.colors.WHITE)),
                rows_col,
            ], expand=True, spacing=0),
        ),
    ], expand=True, spacing=15, scroll=ft.ScrollMode.AUTO)


# ─── CREAR ACTIVO ─────────────────────────────────────────────────────────────
def create_item_view(page: ft.Page, navigate, **kwargs):
    tipo_item_default = (kwargs.get("tipo_item_default") or "equipo").strip().lower()
    if tipo_item_default not in {"equipo", "herramienta", "material", "general"}:
        tipo_item_default = "equipo"

    codigo      = ft.TextField(label="Código SKU *", **JetBrainsTheme.input_style())
    nombre      = ft.TextField(label="Nombre del Activo *", **JetBrainsTheme.input_style())
    marca       = ft.TextField(label="Marca", **JetBrainsTheme.input_style())
    modelo      = ft.TextField(label="Modelo", **JetBrainsTheme.input_style())
    serial      = ft.TextField(label="Número de Serie", **JetBrainsTheme.input_style())
    numero_factura = ft.TextField(label="Número de Factura", **JetBrainsTheme.input_style())
    responsable_dd = ft.Dropdown(label="Responsable *", **JetBrainsTheme.input_style())
    cliente_dd = ft.Dropdown(label="Cliente *", **JetBrainsTheme.input_style())
    crit_dd     = ft.Dropdown(
        label="Criticidad",
        value="media",
        options=[
            ft.dropdown.Option("alta",  text="Alta"),
            ft.dropdown.Option("media", text="Media"),
            ft.dropdown.Option("baja",  text="Baja"),
        ],
        **JetBrainsTheme.input_style(),
    )
    tipo_item_dd = ft.Dropdown(
        label="Tipo de Ítem *",
        value=tipo_item_default,
        options=[
            ft.dropdown.Option("equipo",      text="Equipo"),
            ft.dropdown.Option("herramienta", text="Herramienta"),
            ft.dropdown.Option("material",    text="Material / Consumible"),
            ft.dropdown.Option("general",     text="General"),
        ],
        **JetBrainsTheme.input_style(),
    )
    cantidad_tf = ft.TextField(
        label="Cantidad en Stock *",
        value="1",
        keyboard_type=ft.KeyboardType.NUMBER,
        visible=False,
        **JetBrainsTheme.input_style(),
    )
    categoria_dd    = ft.Dropdown(label="Categoría *", **JetBrainsTheme.input_style())
    subcategoria_dd = ft.Dropdown(label="Subcategoría *", disabled=True, **JetBrainsTheme.input_style())
    bodega_dd       = ft.Dropdown(label="Bodega de Ingreso *", **JetBrainsTheme.input_style())

    users_map = {}
    customers_map = {}

    cantidad_row = ft.Column([cantidad_tf], visible=False)

    def on_tipo_change(_):
        is_material = tipo_item_dd.value == "material"
        cantidad_row.visible = is_material
        cantidad_tf.visible  = is_material
        page.update()

    tipo_item_dd.on_change = on_tipo_change
    on_tipo_change(None)

    def load_data():
        try:
            cats   = list_categories() or []
            stores = list_stores() or []
            users  = list_users() or []
            customers = list_customers() or []
            categoria_dd.options = [ft.dropdown.Option(key=c["id"], text=c["nombre_categoria"]) for c in cats]
            bodega_dd.options    = [ft.dropdown.Option(key=s["id"], text=s["nombre_bodega"]) for s in stores]
            users_map.clear()
            for u in users:
                users_map[u["id"]] = u
            responsable_dd.options = [
                ft.dropdown.Option(
                    key=u["id"],
                    text=f"{u.get('username', 'Usuario')} ({str(u.get('rol', '')).upper()})",
                )
                for u in users
            ]

            customers_map.clear()
            for c in customers:
                customers_map[c["id"]] = c
            cliente_dd.options = [
                ft.dropdown.Option(
                    key=c["id"],
                    text=(c.get("nombre_cliente") or "Cliente"),
                )
                for c in customers
            ]
            page.update()
        except Exception as ex:
            show_snack(page, f"Error al cargar catálogos: {ex}", True)

    def on_cat_change(e):
        subcategoria_dd.value    = None
        subcategoria_dd.options  = []
        subcategoria_dd.disabled = True
        page.update()
        if not categoria_dd.value:
            return
        try:
            subs = list_subcategories({"category_id": categoria_dd.value}) or []
            subcategoria_dd.options  = [ft.dropdown.Option(key=s["id"], text=s["nombre"]) for s in subs]
            subcategoria_dd.disabled = False
            page.update()
        except Exception as ex:
            show_snack(page, f"Error al cargar subcategorías: {ex}", True)

    categoria_dd.on_change = on_cat_change

    def save(e):
        if not codigo.value or not nombre.value or not subcategoria_dd.value or not bodega_dd.value:
            show_snack(page, "Completa los campos obligatorios (*)", True)
            return
        if not responsable_dd.value:
            show_snack(page, "Selecciona un responsable", True)
            return
        if not cliente_dd.value:
            show_snack(page, "Selecciona un cliente", True)
            return
        if tipo_item_dd.value == "material":
            try:
                qty = int(cantidad_tf.value or 0)
                if qty < 1:
                    raise ValueError
            except ValueError:
                show_snack(page, "La cantidad debe ser un número entero mayor a 0", True)
                return
        else:
            qty = 1

        payload = {
            "codigo":              codigo.value.strip(),
            "nombre":              nombre.value.strip(),
            "marca":               marca.value.strip(),
            "modelo":              modelo.value.strip(),
            "serial":              serial.value.strip(),
            "numero_factura":      numero_factura.value.strip(),
            "responsable_id":      responsable_dd.value,
            "responsable_nombre":  (users_map.get(responsable_dd.value) or {}).get("username", ""),
            "cliente_id":          cliente_dd.value,
            "cliente_nombre":      (customers_map.get(cliente_dd.value) or {}).get("nombre_cliente", ""),
            "criticidad":          crit_dd.value or "media",
            "tipo_item":           tipo_item_dd.value or "equipo",
            "cantidad":            qty,
            "subcategoria_id":     subcategoria_dd.value,
            "ubicacion_actual_id": bodega_dd.value,
        }
        try:
            create_item(payload)
            show_snack(page, f"Activo '{codigo.value}' creado exitosamente")
            navigate("items")
        except Exception as ex:
            show_snack(page, f"Error: {ex}", True)

    threading.Timer(0.1, load_data).start()

    return ft.Column([
        ft.Row([
            ft.IconButton(ft.icons.ARROW_BACK_ROUNDED, on_click=lambda e: navigate("items"),
                          tooltip="Volver al listado"),
            ft.Text("Nuevo Activo de Inventario", size=22, weight="bold",
                    color=ThemeColors.TEXT_PRIMARY),
        ], spacing=10),
        ft.Container(
            **JetBrainsTheme.card_style(),
            content=ft.Column([
                ft.ResponsiveRow([
                    ft.Column([codigo],           col={"xs": 12, "md": 6}),
                    ft.Column([nombre],           col={"xs": 12, "md": 6}),
                    ft.Column([marca],            col={"xs": 12, "md": 4}),
                    ft.Column([modelo],           col={"xs": 12, "md": 4}),
                    ft.Column([serial],           col={"xs": 12, "md": 4}),
                    ft.Column([numero_factura],   col={"xs": 12, "md": 6}),
                    ft.Column([responsable_dd],   col={"xs": 12, "md": 3}),
                    ft.Column([cliente_dd],       col={"xs": 12, "md": 3}),
                    ft.Column([tipo_item_dd],     col={"xs": 12, "md": 4}),
                    ft.Column([crit_dd],          col={"xs": 12, "md": 4}),
                    ft.Column([cantidad_row],     col={"xs": 12, "md": 4}),
                    ft.Column([categoria_dd],     col={"xs": 12, "md": 4}),
                    ft.Column([subcategoria_dd],  col={"xs": 12, "md": 4}),
                    ft.Column([bodega_dd],        col={"xs": 12, "md": 12}),
                ], spacing=20),
                ft.Divider(height=30, color=ft.colors.with_opacity(0.08, ft.colors.WHITE)),
                ft.Row([
                    ft.ElevatedButton(
                        "Registrar Activo",
                        icon=ft.icons.SAVE_ROUNDED,
                        style=JetBrainsTheme.primary_button_style(),
                        on_click=save, height=48, width=200,
                    ),
                    ft.TextButton("Cancelar", on_click=lambda e: navigate("items"), height=48),
                ], spacing=15, alignment="end"),
            ], spacing=20),
        ),
    ], expand=True, spacing=20, scroll=ft.ScrollMode.AUTO)
