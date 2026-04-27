"""
Vista de detalle por categoría de activos.
Navega a esta vista al dar clic en una tarjeta de categoría en item_view.
Lee page.session["category_group"] para saber qué categoría mostrar.
"""
import flet as ft
import threading

from core.session import Session
from core.api_client import APIClient
from core.permissions import can_access
from core.theme import ThemeColors, JetBrainsTheme
from components.status_badge import status_badge
from services.item_service import list_items, transition_item
from services.facility_service import search_facilities
from services.category_service import list_categories
from services.subcategory_service import list_subcategories
from services.store_service import list_stores


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
    # Materiales
    "PARCIALMENTE_USADO": ["STOCK"],
}
TERMINAL_STATES = {"DEVOLUCION_PROVEEDOR", "OBSOLETO", "ACTIVO_EN_CAMPO", "OBSOLETA", "CONSUMIDO"}

_ESTADOS_EQUIPO      = ["STOCK", "RESERVADO", "SALIDA_INSTALACION", "INSTALADO_CLIENTE",
                        "REINGRESO_BODEGA", "ACTIVO_EN_CAMPO", "DEVOLUCION_PROVEEDOR", "OBSOLETO"]
_ESTADOS_HERRAMIENTA = ["STOCK", "RESERVADA", "EN_USO", "EN_MANTENIMIENTO", "OBSOLETA"]
_ESTADOS_MATERIAL    = ["STOCK", "RESERVADO", "CONSUMIDO", "PARCIALMENTE_USADO", "OBSOLETO"]

_ESTADOS_POR_GRUPO = {
    "HERRAMIENTAS":     _ESTADOS_HERRAMIENTA,
    "MATERIALES":       _ESTADOS_MATERIAL,
    "ACTIVOS DE OFICINA": _ESTADOS_EQUIPO,
    "EQUIPOS":          _ESTADOS_EQUIPO,
}

_STATE_LABEL = {
    "STOCK": "EN STOCK", "RESERVADO": "RESERVADO", "RESERVADA": "RESERVADA",
    "SALIDA_INSTALACION": "SALIDA INSTALACIÓN", "INSTALADO_CLIENTE": "INSTALADO CLIENTE",
    "REINGRESO_BODEGA": "REINGRESO BODEGA", "ACTIVO_EN_CAMPO": "ACTIVO EN CAMPO",
    "DEVOLUCION_PROVEEDOR": "DEVOLUCIÓN PROVEEDOR", "OBSOLETO": "DADO DE BAJA",
    "OBSOLETA": "OBSOLETA", "EN_USO": "EN USO", "EN_MANTENIMIENTO": "EN MANTENIMIENTO",
    "CONSUMIDO": "CONSUMIDO", "PARCIALMENTE_USADO": "PARCIALMENTE USADO",
}

GROUPS = [
    {"name": "ACTIVOS DE OFICINA", "icon": ft.icons.COMPUTER,                   "color": "#4fc3f7",
     "keywords": ["oficina","computadora","monitor","escritorio","silla","impresora","telefono",
                  "teléfono","laptop","pc","teclado","mouse","scanner","escaner","proyector"]},
    {"name": "HERRAMIENTAS",       "icon": ft.icons.BUILD,                       "color": "#ffb74d",
     "keywords": ["herramienta","taladro","llave","crimpadora","escalera","alicate","destornillador",
                  "pinza","sierra","martillo","nivel","corta","ponchadora","medicion","multimetro",
                  "certificador","tester","pelacable","crimp"]},
    {"name": "MATERIALES",         "icon": ft.icons.INVENTORY_2,                 "color": "#81c784",
     "keywords": ["material","cable","conector","papel","tinta","consumible","canaleta","patch",
                  "utp","fibra","ducto","tornillo","etiqueta","brida","cinta","jack","keystone",
                  "bandeja","conector"]},
    {"name": "EQUIPOS",            "icon": ft.icons.SETTINGS_INPUT_COMPONENT,    "color": "#ce93d8",
     "keywords": ["equipo","servidor","switch","router","ap","firewall","ups","radio","camara",
                  "cámara","access","ntc","olt","ont","mikrotik","ubiquiti","nas","nvr","dvr",
                  "rack","pdu","gabinete"]},
]


def show_snack(page, msg, is_error=False):
    page.snack_bar = ft.SnackBar(
        ft.Text(msg, color=ft.colors.WHITE, weight="bold"),
        bgcolor=ft.colors.RED_700 if is_error else ft.colors.GREEN_700,
        duration=3000,
    )
    page.snack_bar.open = True
    page.update()


def category_item_view(page: ft.Page, navigate):
    rol        = (Session.user or {}).get("rol", "tecnico")
    group_name = page.session.get("category_group") or "EQUIPOS"
    group      = next((g for g in GROUPS if g["name"] == group_name), GROUPS[-1])
    color      = group["color"]

    all_items      = []
    filtered_items = []

    # ── Controles UI ─────────────────────────────────────────────────────────
    loading      = ft.ProgressBar(visible=False, color=ThemeColors.ACCENT_BLUE)
    results_text = ft.Text("", size=12, color=ThemeColors.TEXT_SECONDARY)

    # Resumen
    stat_total  = ft.Text("0", size=28, weight="bold", color=ft.colors.WHITE)
    stat_stock  = ft.Text("0", size=28, weight="bold", color=color)

    rows_col = ft.Column(spacing=0)

    search_tf = ft.TextField(
        hint_text="Nombre, SKU o serie...",
        prefix_icon=ft.icons.SEARCH,
        width=280, height=44,
        on_change=lambda _: apply_filters(),
        **JetBrainsTheme.input_style(),
    )
    _estados_grupo = _ESTADOS_POR_GRUPO.get(group_name, _ESTADOS_EQUIPO)
    estado_dd = ft.Dropdown(
        label="Estado",
        width=200,
        options=[ft.dropdown.Option("TODOS")] + [
            ft.dropdown.Option(s, _STATE_LABEL.get(s, s)) for s in _estados_grupo
        ],
        value="TODOS",
        on_change=lambda _: apply_filters(),
        **JetBrainsTheme.input_style(),
    )

    # ── Clasificador ──────────────────────────────────────────────────────────
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
            
        return "EQUIPOS"

    # ── Filtrado ──────────────────────────────────────────────────────────────
    def apply_filters(e=None):
        search = (search_tf.value or "").lower().strip()
        # Normalizar filtro de estado
        estado_filtro = str(estado_dd.value or "TODOS").strip().upper()
        
        result = []
        target_group = group_name.strip().upper()
        
        for item in all_items:
            # Filtro por categoría
            if classify(item).strip().upper() != target_group:
                continue
                
            if search:
                hay = " ".join([item.get("nombre",""), item.get("codigo",""), item.get("serial","")]).lower()
                if search not in hay:
                    continue
            
            # Filtro por estado: Solo si NO es "TODOS"
            if estado_filtro != "TODOS" and estado_filtro != "":
                item_estado = str(item.get("estado") or "").strip().upper()
                if item_estado != estado_filtro:
                    continue
                    
            result.append(item)
        filtered_items.clear()
        filtered_items.extend(result)
        refresh_table()
        refresh_summary()
        results_text.value = f"{len(filtered_items)} ítems"
        page.update()

    def clear_filters(e=None):
        search_tf.value = ""
        estado_dd.value = "TODOS"
        apply_filters()

    # ── Resumen ───────────────────────────────────────────────────────────────
    def refresh_summary():
        grp_items = [i for i in filtered_items if classify(i) == group_name]
        in_stock  = [i for i in grp_items if i.get("estado") == "STOCK"]
        stat_total.value = str(len(grp_items))
        stat_stock.value = str(len(in_stock))

    # ── Columnas tabla ────────────────────────────────────────────────────────
    COL = {"cod": 95, "nom": 230, "est": 145, "ub": 120, "sn": 140}

    header_row = ft.Container(
        bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
        content=ft.Row([
            ft.Container(width=COL["cod"], content=ft.Text("CÓDIGO",    size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["nom"], content=ft.Text("ACTIVO",    size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["est"], content=ft.Text("ESTADO",    size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["ub"],  content=ft.Text("UBICACIÓN", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["sn"],  content=ft.Text("SERIE",     size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
        ], spacing=8),
    )

    def _make_row(item):
        estado      = item.get("estado", "STOCK")
        marcmod     = f"{item.get('marca', '')} {item.get('modelo', '')}".strip() or "—"
        ub_val      = item.get("ubicacion_nombre") or "—"
        serial_val  = item.get("serial") or "—"

        return ft.Container(
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.colors.with_opacity(0.05, ft.colors.WHITE))),
            ink=True,
            on_click=lambda e, it=item: open_detail(it),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        ft.colors.with_opacity(0.04, ft.colors.WHITE) if e.data == "true"
                        else ft.colors.TRANSPARENT) or page.update()
            ),
            content=ft.Row([
                ft.Container(width=COL["cod"],
                             content=ft.Text(item.get("codigo", "—"), size=12, weight="bold",
                                            color=ThemeColors.ACCENT_BLUE, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=COL["nom"],
                             content=ft.Column([
                                 ft.Text(item.get("nombre", "—"), size=13, weight="bold", overflow=ft.TextOverflow.ELLIPSIS),
                                 ft.Text(marcmod, size=11, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS),
                             ], spacing=0, tight=True)),
                ft.Container(width=COL["est"],  content=status_badge(estado)),
                ft.Container(width=COL["ub"],   content=ft.Text(ub_val, size=11, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=COL["sn"],   content=ft.Text(serial_val, size=11, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
            ], spacing=8),
        )

    def refresh_table():
        rows_col.controls.clear()
        if not filtered_items:
            rows_col.controls.append(ft.Container(
                padding=ft.padding.all(30),
                content=ft.Text("No hay ítems en esta categoría con los filtros actuales.",
                               italic=True, color=ThemeColors.TEXT_SECONDARY),
            ))
        else:
            for item in filtered_items:
                rows_col.controls.append(_make_row(item))

    # ── Carga ─────────────────────────────────────────────────────────────────
    def load_data():
        loading.visible = True
        page.update()
        try:
            data = list_items({}) or []
            print(f"[DEBUG] load_data: group={group_name}, items_from_api={len(data)}")
            all_items.clear()
            all_items.extend(data)
            # Muestra cuántos items coinciden con este grupo
            matched = [i for i in data if classify(i) == group_name]
            print(f"[DEBUG] load_data: items que coinciden con '{group_name}': {len(matched)}")
            if matched:
                sample = matched[0]
                print(f"[DEBUG] sample: nombre={sample.get('nombre')}, tipo_item={sample.get('tipo_item')}, sub={sample.get('subcategoria')}")
            apply_filters()
            print(f"[DEBUG] apply_filters done: filtered_items={len(filtered_items)}, stat_total={stat_total.value}")
        except Exception as ex:
            import traceback
            print(f"[DEBUG] load_data EXCEPTION: {ex}")
            traceback.print_exc()
            show_snack(page, f"Error al cargar: {ex}", True)
        finally:
            loading.visible = False
            page.update()

    def reload():
        threading.Thread(target=load_data, daemon=True).start()

    # ── CRUD: Detalle al hacer clic ───────────────────────────────────────────
    def open_detail(item):
        estado      = item.get("estado", "STOCK")
        is_terminal = estado in TERMINAL_STATES
        sub         = item.get("subcategoria") or {}
        cat_lbl     = ((sub.get("categoria") or {}).get("nombre_categoria") or sub.get("nombre") or "—") if isinstance(sub, dict) else "—"

        def info(label, value, icon):
            return ft.Row([
                ft.Icon(icon, size=14, color=ThemeColors.ACCENT_BLUE),
                ft.Text(label, size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY, width=80),
                ft.Text(str(value) if value else "—", size=13),
            ], spacing=8)

        def close_then(fn):
            def _h(_e):
                page.dialog.open = False
                page.update()
                fn()
            return _h

        btns = [ft.TextButton("Cerrar", on_click=lambda e: setattr(page.dialog, "open", False) or page.update())]

        if not is_terminal and can_access(rol, "item:update"):
            btns.insert(0, ft.ElevatedButton("Ciclo de Vida", icon=ft.icons.RECYCLING,
                                              style=JetBrainsTheme.primary_button_style(),
                                              on_click=close_then(lambda: open_transition(item))))
        if can_access(rol, "item:update"):
            btns.insert(1 if not is_terminal else 0,
                        ft.ElevatedButton("Editar", icon=ft.icons.EDIT_ROUNDED,
                                          style=JetBrainsTheme.primary_button_style(),
                                          on_click=close_then(lambda: open_edit(item))))
        if can_access(rol, "item:delete"):
            btns.append(ft.ElevatedButton("Eliminar", icon=ft.icons.DELETE_ROUNDED,
                                          bgcolor=ft.colors.RED_700, color=ft.colors.WHITE,
                                          on_click=close_then(lambda: confirm_delete(item))))

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(group["icon"], color=color, size=26),
                ft.Column([
                    ft.Text(item.get("nombre", "—"), weight="bold", size=15),
                    ft.Text(f"{item.get('codigo','—')}  ·  {cat_lbl}", size=11, color=ThemeColors.TEXT_SECONDARY),
                ], spacing=1, tight=True),
            ], spacing=12),
            content=ft.Container(width=420, content=ft.Column([
                info("Estado",    estado,                     ft.icons.CIRCLE),
                info("Categoría", cat_lbl,                    ft.icons.CATEGORY),
                info("Marca",     item.get("marca"),          ft.icons.BUSINESS),
                info("Modelo",    item.get("modelo"),         ft.icons.SETTINGS),
                info("Serie",     item.get("serial"),         ft.icons.QR_CODE),
                info("Ubicación", item.get("ubicacion_nombre"), ft.icons.WAREHOUSE),
                info("Criticidad",item.get("criticidad"),     ft.icons.WARNING),
            ], tight=True, spacing=10)),
            actions=btns,
        )
        page.dialog.open = True
        page.update()

    # ── Transición de estado ──────────────────────────────────────────────────
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
                        on_click=lambda e, f=f: _pick(f), dense=True,
                    ) for f in facs
                ]
                page.update()
            except Exception:
                pass

        def _pick(fac):
            ot_id[0]       = fac["codigo_instalacion"]
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
        notes_tf = ft.TextField(label="Observaciones", multiline=True, min_lines=2, **JetBrainsTheme.input_style())

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
            title=ft.Row([ft.Icon(ft.icons.RECYCLING, color=ThemeColors.ACCENT_BLUE),
                          ft.Text(f"Ciclo de Vida: {item.get('codigo')}", weight="bold")], spacing=10),
            content=ft.Container(width=480, content=ft.Column([
                ft.Row([ft.Text("Estado actual:", size=12, color=ThemeColors.TEXT_SECONDARY), status_badge(current)], spacing=8),
                next_dd, ot_col, notes_tf,
            ], tight=True, spacing=15)),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Ejecutar", style=JetBrainsTheme.primary_button_style(), on_click=do_transition),
            ],
        )
        page.dialog.open = True
        page.update()

    # ── Editar activo ─────────────────────────────────────────────────────────
    def open_edit(item):
        nombre_tf = ft.TextField(label="Nombre", value=item.get("nombre", ""), expand=True, **JetBrainsTheme.input_style())
        marca_tf  = ft.TextField(label="Marca",  value=item.get("marca",  ""), expand=True, **JetBrainsTheme.input_style())
        modelo_tf = ft.TextField(label="Modelo", value=item.get("modelo", ""), expand=True, **JetBrainsTheme.input_style())
        serial_tf = ft.TextField(label="Serie",  value=item.get("serial", ""), expand=True, **JetBrainsTheme.input_style())
        crit_dd   = ft.Dropdown(label="Criticidad", value=item.get("criticidad", "media"),
                                options=[ft.dropdown.Option("alta","Alta"), ft.dropdown.Option("media","Media"), ft.dropdown.Option("baja","Baja")],
                                **JetBrainsTheme.input_style())

        def save(e):
            if not nombre_tf.value.strip():
                show_snack(page, "El nombre es obligatorio", True)
                return
            try:
                APIClient.put(f"inventory/items/{item['id']}/", json={
                    "nombre": nombre_tf.value.strip(), "marca": marca_tf.value.strip(),
                    "modelo": modelo_tf.value.strip(), "serial": serial_tf.value.strip(),
                    "criticidad": crit_dd.value or "media",
                })
                page.dialog.open = False
                page.update()
                show_snack(page, f"Activo '{item.get('codigo')}' actualizado")
                reload()
            except Exception as ex:
                show_snack(page, f"Error: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.icons.EDIT_ROUNDED, color=ThemeColors.ACCENT_BLUE),
                          ft.Text(f"Editar: {item.get('codigo')}", weight="bold")], spacing=10),
            content=ft.Container(width=480, content=ft.Column([
                nombre_tf, ft.Row([marca_tf, modelo_tf], spacing=12), serial_tf, crit_dd,
            ], tight=True, spacing=12)),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Guardar", style=JetBrainsTheme.primary_button_style(), on_click=save),
            ],
        )
        page.dialog.open = True
        page.update()

    # ── Eliminar activo ───────────────────────────────────────────────────────
    def confirm_delete(item):
        def do_delete(e):
            try:
                APIClient.delete(f"inventory/items/{item['id']}/")
                page.dialog.open = False
                page.update()
                show_snack(page, f"Activo '{item.get('codigo')}' eliminado")
                reload()
            except Exception as ex:
                show_snack(page, f"Error: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.icons.WARNING_ROUNDED, color=ft.colors.RED_400),
                          ft.Text("Eliminar Activo", weight="bold")], spacing=10),
            content=ft.Text(f"¿Eliminar '{item.get('codigo')} — {item.get('nombre')}'?\nEsta acción es irreversible.", size=14),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Sí, eliminar", bgcolor=ft.colors.RED_700, color=ft.colors.WHITE, on_click=do_delete),
            ],
        )
        page.dialog.open = True
        page.update()

    # ── Crear nuevo activo (formulario por categoría) ─────────────────────────
    _FORM_CFG = {
        "HERRAMIENTAS": {
            "marca_label":  "Fabricante",
            "modelo_label": "Referencia / Modelo",
            "serial_label": "N° Inventario *",
            "serial_req":   True,
            "cat_keywords": ["herramienta"],
        },
        "MATERIALES": {
            "marca_label":  "Fabricante / Proveedor",
            "modelo_label": "Referencia",
            "serial_label": "Lote / Referencia (opcional)",
            "serial_req":   False,
            "cat_keywords": ["material", "consumible"],
        },
        "ACTIVOS DE OFICINA": {
            "marca_label":  "Fabricante",
            "modelo_label": "Modelo",
            "serial_label": "N° Serie / Inventario *",
            "serial_req":   True,
            "cat_keywords": ["oficina"],
        },
        "EQUIPOS": {
            "marca_label":  "Fabricante",
            "modelo_label": "Modelo",
            "serial_label": "N° Serie *",
            "serial_req":   True,
            "cat_keywords": [],
        },
    }

    def open_create(e=None):
        cfg = _FORM_CFG.get(group_name, _FORM_CFG["EQUIPOS"])

        codigo_tf = ft.TextField(label="Código SKU *",      expand=True, **JetBrainsTheme.input_style())
        nombre_tf = ft.TextField(label="Nombre *",          expand=True, **JetBrainsTheme.input_style())
        marca_tf  = ft.TextField(label=cfg["marca_label"],  expand=True, **JetBrainsTheme.input_style())
        modelo_tf = ft.TextField(label=cfg["modelo_label"], expand=True, **JetBrainsTheme.input_style())
        serial_tf = ft.TextField(label=cfg["serial_label"], expand=True, **JetBrainsTheme.input_style())
        cat_dd = ft.Dropdown(hint_text="Categoría *",    expand=True, **JetBrainsTheme.input_style())
        sub_dd = ft.Dropdown(hint_text="Subcategoría *", expand=True, disabled=True, **JetBrainsTheme.input_style())
        bod_dd = ft.Dropdown(hint_text="Bodega *",       expand=True, **JetBrainsTheme.input_style())

        def _load_form():
            try:
                cats   = list_categories() or []
                stores = list_stores() or []
                kws    = cfg["cat_keywords"]
                relevant = (
                    [c for c in cats if any(kw in (c.get("nombre_categoria") or "").lower() for kw in kws)]
                    if kws else cats
                ) or cats
                cat_dd.options = [ft.dropdown.Option(key=c["id"], text=c["nombre_categoria"]) for c in relevant]
                bod_dd.options = [ft.dropdown.Option(key=s["id"], text=s["nombre_bodega"]) for s in stores]
                if relevant:
                    cat_dd.value = relevant[0]["id"]
                    subs = list_subcategories({"category_id": relevant[0]["id"]}) or []
                    sub_dd.options  = [ft.dropdown.Option(key=s["id"], text=s["nombre"]) for s in subs]
                    sub_dd.disabled = False
                page.update()
            except Exception:
                pass

        def on_cat(_e):
            sub_dd.value    = None
            sub_dd.options  = []
            sub_dd.disabled = True
            page.update()
            if cat_dd.value:
                try:
                    subs = list_subcategories({"category_id": cat_dd.value}) or []
                    sub_dd.options  = [ft.dropdown.Option(key=s["id"], text=s["nombre"]) for s in subs]
                    sub_dd.disabled = False
                    page.update()
                except Exception:
                    pass

        cat_dd.on_change = on_cat
        threading.Timer(0.1, _load_form).start()

        def save(_e):
            serial_ok = serial_tf.value.strip() if cfg["serial_req"] else True
            if not codigo_tf.value or not nombre_tf.value or not sub_dd.value or not bod_dd.value or not serial_ok:
                show_snack(page, "Completa los campos obligatorios (*)", True)
                return
            try:
                APIClient.post("inventory/items/", json={
                    "codigo":              codigo_tf.value.strip(),
                    "nombre":              nombre_tf.value.strip(),
                    "marca":               marca_tf.value.strip(),
                    "modelo":              modelo_tf.value.strip(),
                    "serial":              serial_tf.value.strip(),
                    "criticidad":          "media",
                    "subcategoria_id":     sub_dd.value,
                    "ubicacion_actual_id": bod_dd.value,
                })
                page.dialog.open = False
                page.update()
                show_snack(page, f"'{codigo_tf.value.strip()}' creado")
                reload()
            except Exception as ex:
                show_snack(page, f"Error: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(group["icon"], color=color),
                ft.Text(f"Nuevo — {group_name.title()}", weight="bold"),
            ], spacing=10),
            content=ft.Container(width=520, content=ft.Column([
                codigo_tf,
                nombre_tf,
                ft.Row([marca_tf, modelo_tf], spacing=12),
                serial_tf,
                ft.Divider(height=8, color=ft.colors.with_opacity(0.06, ft.colors.WHITE)),
                ft.Row([cat_dd, sub_dd], spacing=12),
                bod_dd,
            ], tight=True, spacing=12)),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Crear", style=JetBrainsTheme.primary_button_style(), on_click=save),
            ],
        )
        page.dialog.open = True
        page.update()

    # ── Inicio ────────────────────────────────────────────────────────────────
    threading.Timer(0.1, load_data).start()

    # ── Layout ────────────────────────────────────────────────────────────────
    summary_card = ft.Container(
        bgcolor=ft.colors.with_opacity(0.08, ft.colors.WHITE),
        padding=20, border_radius=16,
        border=ft.border.all(1, ft.colors.with_opacity(0.12, ft.colors.WHITE)),
        content=ft.Row([
            ft.Column([ft.Text("TOTAL", size=10, weight="bold", color=ThemeColors.TEXT_SECONDARY), stat_total], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(width=1, height=40, bgcolor=ft.colors.with_opacity(0.12, ft.colors.WHITE)),
            ft.Column([ft.Text("STOCK", size=10, weight="bold", color=ThemeColors.TEXT_SECONDARY), stat_stock], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=24, alignment=ft.MainAxisAlignment.SPACE_EVENLY),
    )

    return ft.Column([
        # Cabecera
        ft.Row([
            ft.IconButton(ft.icons.ARROW_BACK_ROUNDED,
                          on_click=lambda e: navigate("items"),
                          icon_color=ThemeColors.TEXT_SECONDARY, tooltip="Volver al inventario"),
            ft.Icon(group["icon"], color=color, size=26),
            ft.Text(group["name"], size=22, weight="bold", color=ft.colors.WHITE),
            ft.Container(expand=True),
            ft.ElevatedButton("Nuevo Activo", icon=ft.icons.ADD_ROUNDED,
                              style=JetBrainsTheme.primary_button_style(),
                              on_click=open_create, height=42,
                              visible=can_access(rol, "item:create")),
            ft.ElevatedButton("Actualizar", icon=ft.icons.REFRESH_ROUNDED,
                              style=JetBrainsTheme.primary_button_style(),
                              on_click=lambda e: reload(), height=42),
        ], spacing=10),

        # Resumen
        summary_card,

        # Filtros
        ft.Container(
            **JetBrainsTheme.card_style(),
            content=ft.Row([
                search_tf,
                estado_dd,
                ft.ElevatedButton("Limpiar", icon=ft.icons.CLEAR_ROUNDED,
                                  on_click=clear_filters, height=42,
                                  style=ft.ButtonStyle(
                                      color=ft.colors.WHITE,
                                      bgcolor=ft.colors.with_opacity(0.1, ft.colors.WHITE),
                                  )),
                ft.Container(expand=True),
                results_text,
            ], spacing=10),
        ),

        loading,

        # Tabla
        ft.Container(
            **JetBrainsTheme.card_style(),
            content=ft.Column([
                header_row,
                ft.Divider(height=1, color=ft.colors.with_opacity(0.06, ft.colors.WHITE)),
                rows_col,
            ], spacing=0),
        ),
    ], expand=True, spacing=15, scroll=ft.ScrollMode.AUTO)
