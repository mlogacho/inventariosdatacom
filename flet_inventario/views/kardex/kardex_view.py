import threading
import webbrowser

import flet as ft

from core.api_client import APIClient
from core.session import Session
from core.theme import ThemeColors, JetBrainsTheme
from services.kardex_service import get_kardex_dashboard
from services.movement_service import download_acta_entrega_recepcion

ASSET_TABLE_WIDTH = 1370
MOV_TABLE_WIDTH = 1315

ASSET_TABLE_COLUMNS = [
	("CÓDIGO", 120),
	("ACTIVO", 260),
	("ESTADO", 120),
	("UBICACIÓN", 340),
	("RESPONSABLE", 180),
	("CALIDAD", 120),
	("ACCIONES", 74),
]

MOV_TABLE_COLUMNS = [
	("FECHA", 150),
	("CÓDIGO", 120),
	("ACTIVO", 230),
	("TIPO", 145),
	("ORIGEN", 220),
	("DESTINO", 220),
	("OT", 120),
	("ACTA", 48),
]


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


def _missing_flags(item: dict) -> tuple[bool, bool, bool]:
	missing_bodega = not bool(item.get("ubicacion_actual_id"))
	missing_responsable = not bool(str(item.get("responsable_nombre") or "").strip())
	missing_cliente = not bool(str(item.get("cliente_nombre") or "").strip())
	return missing_bodega, missing_responsable, missing_cliente


def _priority_label(item: dict) -> tuple[str, str, int]:
	missing_bodega, missing_responsable, missing_cliente = _missing_flags(item)
	score = int(missing_bodega) + int(missing_responsable) + int(missing_cliente)
	if score >= 2:
		return "CRITICO", ft.colors.RED_300, score
	if score == 1:
		return "PENDIENTE", ft.colors.AMBER_300, score
	return "OK", ft.colors.GREEN_300, score


def _customer_label(customer: dict) -> str:
	code = str(customer.get("codigo_cliente") or customer.get("id") or "").strip()
	name = str(customer.get("nombre_cliente") or "Cliente").strip()
	return " · ".join(part for part in [code, name] if part)


def _store_label(store: dict) -> str:
	return str(store.get("nombre_bodega") or "Bodega").strip() or "Bodega"


def _filter_customer_options(customers: list[dict], query: str = "") -> list[tuple[str, str]]:
	normalized_query = (query or "").strip().lower()
	options = []
	for customer in customers:
		key = str(customer.get("key") or "")
		if not key:
			continue
		label = _customer_label(customer)
		haystack = f"{key} {label} {customer.get('nombre_cliente') or ''} {customer.get('codigo_cliente') or customer.get('id') or ''}".lower()
		if normalized_query and normalized_query not in haystack:
			continue
		options.append((key, label))
	return options


def _location_options(stores: list[dict], customers: list[dict]) -> list[tuple[str, str]]:
	options = []
	for store in stores:
		store_id = str(store.get("id") or "").strip()
		if not store_id:
			continue
		options.append((f"store:{store_id}", _store_label(store)))
	for customer in customers:
		key = str(customer.get("key") or "").strip()
		if not key:
			continue
		options.append((key, _customer_label(customer)))
	return options


def _table_header(columns: list[tuple[str, int]], width: int) -> ft.Container:
	return ft.Container(
		width=width,
		bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
		padding=ft.padding.symmetric(horizontal=14, vertical=8),
		content=ft.Row(
			[
				ft.Container(
					width=col_width,
					content=ft.Text(label, size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY),
				)
				for label, col_width in columns
			],
			spacing=10,
		),
	)


def _location_label(item: dict) -> str:
	if _location_type(item) == "CLIENTE":
		return str(item.get("cliente_nombre") or "Cliente sin registrar").strip() or "Cliente sin registrar"
	return str(item.get("ubicacion_nombre") or "Sin bodega registrada").strip() or "Sin bodega registrada"


def kardex_view(page: ft.Page, navigate, **kwargs):
	items_all = []
	movements_recent = []
	users_all = []
	customers_all = []
	stores_all = []
	responsible_options = []
	customer_options = []
	page_state = {"page": 1, "page_size": 50, "total_pages": 1, "total": 0}

	pending_state = {
		"missing_bodega": False,
		"missing_responsable": False,
		"missing_cliente": False,
	}

	loading = ft.ProgressBar(visible=False, color=ThemeColors.ACCENT_BLUE)
	stats_total = ft.Text("0", size=22, weight="bold", color=ft.colors.WHITE)
	stats_bodega = ft.Text("0", size=22, weight="bold", color=ThemeColors.ACCENT_BLUE)
	stats_cliente = ft.Text("0", size=22, weight="bold", color=ThemeColors.ACCENT_MAGENTA)
	stats_sin_bodega = ft.Text("0", size=20, weight="bold", color=ft.colors.AMBER_300)
	stats_sin_responsable = ft.Text("0", size=20, weight="bold", color=ft.colors.ORANGE_300)
	stats_sin_cliente = ft.Text("0", size=20, weight="bold", color=ft.colors.RED_300)
	pagination_txt = ft.Text("Página 1/1", size=11, color=ThemeColors.TEXT_SECONDARY)

	rows_assets = ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO)
	rows_kardex = ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO)

	search_tf = ft.TextField(
		hint_text="Buscar por código, nombre o serie...",
		prefix_icon=ft.icons.SEARCH,
		width=360,
		on_submit=lambda e: apply_filters(),
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
	cliente_search_tf = ft.TextField(
		hint_text="Buscar cliente por código o nombre...",
		prefix_icon=ft.icons.SEARCH,
		width=360,
		on_change=lambda e: _refresh_customer_options(cliente_search_tf.value or ""),
		**JetBrainsTheme.input_style(),
	)
	prioritize_pending_sw = ft.Switch(label="Priorizar pendientes", value=True)

	pending_bodega_btn = ft.TextButton("Ver pendientes")
	pending_responsable_btn = ft.TextButton("Ver pendientes")
	pending_cliente_btn = ft.TextButton("Ver pendientes")
	clear_pending_btn = ft.TextButton("Limpiar filtros de pendientes", visible=False)

	pending_bodega_card = ft.Container(expand=True)
	pending_responsable_card = ft.Container(expand=True)
	pending_cliente_card = ft.Container(expand=True)

	page.dialog = None

	def _safe_page_update() -> bool:
		try:
			page.update()
			return True
		except Exception as ex:
			if "Control must be added to the page first" in str(ex):
				return False
			raise

	def show_snack(msg: str, is_error: bool = False):
		page.snack_bar = ft.SnackBar(
			content=ft.Text(msg, color=ft.colors.WHITE, weight="bold"),
			bgcolor=ft.colors.RED_700 if is_error else ft.colors.GREEN_700,
			duration=3500,
		)
		page.snack_bar.open = True
		_safe_page_update()

	def _schedule_load(delay: float = 0.2):
		threading.Timer(delay, lambda: load_data(False)).start()

	def _pending_card(title: str, value_ctrl: ft.Text, button: ft.TextButton, active: bool):
		return ft.Container(
			expand=True,
			border_radius=12,
			padding=ft.padding.all(14),
			bgcolor=(
				ft.colors.with_opacity(0.18, ThemeColors.ACCENT_BLUE)
				if active else ft.colors.with_opacity(0.06, ft.colors.WHITE)
			),
			border=ft.border.all(
				1,
				ft.colors.with_opacity(0.32, ThemeColors.ACCENT_BLUE)
				if active else ft.colors.with_opacity(0.12, ft.colors.WHITE),
			),
			content=ft.Column(
				[
					ft.Text(title, size=11, color=ThemeColors.TEXT_SECONDARY, weight="bold"),
					value_ctrl,
					button,
				],
				spacing=4,
			),
		)

	def _refresh_customer_options(query: str = ""):
		customer_options.clear()
		customer_options.extend(_filter_customer_options(customers_all, query))
		cliente_dd.options = [ft.dropdown.Option("TODOS")] + [
			ft.dropdown.Option(key=k, text=t)
			for k, t in customer_options
		]
		if not any(opt.key == cliente_dd.value for opt in cliente_dd.options):
			cliente_dd.value = "TODOS"
		_safe_page_update()

	def _refresh_responsible_options():
		responsable_dd.options = [ft.dropdown.Option("TODOS")] + [
			ft.dropdown.Option(key=k, text=t)
			for k, t in responsible_options
		]
		if not any(opt.key == responsable_dd.value for opt in responsable_dd.options):
			responsable_dd.value = "TODOS"

	def _apply_catalogs(catalogs: dict):
		users_all.clear()
		users_all.extend(catalogs.get("responsables") or [])
		responsible_options.clear()
		responsible_options.extend(
			[
				(
					str(u.get("key") or ""),
					u.get("full_name") or u.get("username") or "Usuario",
				)
				for u in users_all
				if str(u.get("key") or "")
			]
		)

		customers_all.clear()
		customers_all.extend(catalogs.get("clientes") or [])
		stores_all.clear()
		stores_all.extend(catalogs.get("bodegas") or [])

		_refresh_responsible_options()
		_refresh_customer_options(cliente_search_tf.value or "")

	def _ensure_catalogs_for_edit() -> bool:
		if responsible_options and customers_all and stores_all:
			return True
		try:
			payload = get_kardex_dashboard({"page": 1, "page_size": 1, "mov_limit": 1}) or {}
			catalogs = payload.get("catalogs") or {}
			_apply_catalogs(catalogs)
			return True
		except Exception as ex:
			show_snack(f"No se pudieron cargar catálogos CRM: {ex}", is_error=True)
			return False

	def _resolve_responsible_value(item: dict) -> str | None:
		rid = str(item.get("responsable_id") or "").strip()
		if rid and any(k == f"crmuser:{rid}" for k, _ in responsible_options):
			return f"crmuser:{rid}"
		if rid and any(k == f"user:{rid}" for k, _ in responsible_options):
			return f"user:{rid}"
		return None

	def _resolve_customer_value(item: dict) -> str | None:
		cid = str(item.get("cliente_id") or "").strip()
		if not cid:
			return None
		if any(str(c.get("id")) == cid and str(c.get("key") or "").startswith("customer:") for c in customers_all):
			return f"customer:{cid}"
		if any(str(c.get("id")) == cid and str(c.get("key") or "").startswith("crm:") for c in customers_all):
			return f"crm:{cid}"
		return None

	def _resolve_location_value(item: dict) -> str | None:
		store_id = str(item.get("ubicacion_actual_id") or "").strip()
		if store_id and any(str(s.get("id") or "") == store_id for s in stores_all):
			return f"store:{store_id}"
		customer_key = _resolve_customer_value(item)
		if customer_key:
			return customer_key
		return None

	def _build_edit_dialog(item: dict):
		if not _ensure_catalogs_for_edit():
			return

		name_tf = ft.TextField(label="Nombre del activo", value=item.get("nombre") or "", width=740, **JetBrainsTheme.input_style())
		factura_tf = ft.TextField(label="Numero de Factura", value=item.get("numero_factura") or "", width=740, **JetBrainsTheme.input_style())
		marca_tf = ft.TextField(label="Marca", value=item.get("marca") or "", width=365, **JetBrainsTheme.input_style())
		modelo_tf = ft.TextField(label="Modelo", value=item.get("modelo") or "", width=365, **JetBrainsTheme.input_style())
		serial_tf = ft.TextField(label="Serie", value=item.get("serial") or "", width=740, **JetBrainsTheme.input_style())
		mac_tf = ft.TextField(label="MAC", value=item.get("mac") or "", width=740, **JetBrainsTheme.input_style())

		responsible_edit_dd = ft.Dropdown(
			label="Responsable",
			options=[ft.dropdown.Option(key=k, text=t) for k, t in responsible_options],
			value=_resolve_responsible_value(item),
			width=365,
			**JetBrainsTheme.input_style(),
		)

		customer_edit_search_tf = ft.TextField(
			label="Buscar cliente",
			value="",
			prefix_icon=ft.icons.SEARCH,
			width=365,
			**JetBrainsTheme.input_style(),
		)

		customer_edit_dd = ft.Dropdown(
			label="Cliente",
			options=[ft.dropdown.Option(key=k, text=t) for k, t in customer_options],
			value=_resolve_customer_value(item),
			width=365,
			**JetBrainsTheme.input_style(),
		)

		location_options = _location_options(stores_all, customers_all)
		location_dd = ft.Dropdown(
			label="Ubicación",
			options=[ft.dropdown.Option(key=k, text=t) for k, t in location_options],
			value=_resolve_location_value(item),
			width=365,
			**JetBrainsTheme.input_style(),
		)

		def _refresh_customer_edit_options(query: str = ""):
			filtered = _filter_customer_options(customers_all, query)
			customer_edit_dd.options = [ft.dropdown.Option(key=k, text=t) for k, t in filtered]
			if not any(opt.key == customer_edit_dd.value for opt in customer_edit_dd.options):
				customer_edit_dd.value = None
			location_options = _location_options(stores_all, customers_all)
			location_dd.options = [ft.dropdown.Option(key=k, text=t) for k, t in location_options]
			if not any(opt.key == location_dd.value for opt in location_dd.options):
				location_dd.value = None
			_safe_page_update()

		def do_save(e):
			selected_responsible = str(responsible_edit_dd.value or "")
			selected_customer = str(customer_edit_dd.value or "")
			selected_location = str(location_dd.value or "")

			responsable_id = ""
			responsable_nombre = ""
			if selected_responsible.startswith("crmuser:") or selected_responsible.startswith("user:"):
				responsable_id = selected_responsible.split(":", 1)[1]
				responsible_data = next((u for u in users_all if str(u.get("id")) == responsable_id), None)
				if not responsible_data:
					show_snack("Responsable inválido. Selecciona un usuario activo.", is_error=True)
					return
				responsable_nombre = responsible_data.get("full_name") or responsible_data.get("username") or ""
			elif selected_responsible:
				show_snack("Responsable inválido. Selecciona un usuario activo.", is_error=True)
				return

			cliente_id = ""
			cliente_nombre = ""
			if selected_customer.startswith("customer:") or selected_customer.startswith("crm:"):
				cliente_id = selected_customer.split(":", 1)[1]
				customer_data = next(
					(c for c in customers_all if str(c.get("id")) == cliente_id and str(c.get("key") or "") == selected_customer),
					None,
				)
				if not customer_data:
					customer_data = next((c for c in customers_all if str(c.get("id")) == cliente_id), None)
				if not customer_data:
					show_snack("Cliente inválido. Selecciona un cliente activo.", is_error=True)
					return
				cliente_nombre = customer_data.get("nombre_cliente") or ""
			elif selected_customer:
				show_snack("Cliente inválido. Selecciona un cliente activo.", is_error=True)
				return

			ubicacion_actual_id = None
			if selected_location.startswith("store:"):
				ubicacion_actual_id = selected_location.split(":", 1)[1]
			elif selected_location.startswith("customer:") or selected_location.startswith("crm:"):
				cliente_id = selected_location.split(":", 1)[1]
				customer_data = next((c for c in customers_all if str(c.get("id")) == cliente_id), None)
				if not customer_data:
					show_snack("Ubicación inválida. Selecciona una bodega o un cliente activo.", is_error=True)
					return
				cliente_nombre = customer_data.get("nombre_cliente") or cliente_nombre
			elif selected_location:
				show_snack("Ubicación inválida. Selecciona una bodega o un cliente activo.", is_error=True)
				return

			payload = {
				"nombre": (name_tf.value or "").strip(),
				"numero_factura": (factura_tf.value or "").strip(),
				"marca": (marca_tf.value or "").strip(),
				"modelo": (modelo_tf.value or "").strip(),
				"serial": (serial_tf.value or "").strip(),
				"mac": (mac_tf.value or "").strip(),
				"responsable_id": responsable_id,
				"responsable_nombre": responsable_nombre,
				"cliente_id": cliente_id,
				"cliente_nombre": cliente_nombre,
				"ubicacion_actual_id": ubicacion_actual_id,
			}

			try:
				APIClient.put(f"inventory/items/{item.get('id')}/", json=payload)
				page.dialog.open = False
				_safe_page_update()
				show_snack("Registro actualizado correctamente")
				_schedule_load(0.05)
			except Exception as ex:
				show_snack(f"No se pudo actualizar: {ex}", is_error=True)

		customer_edit_search_tf.on_change = lambda e: _refresh_customer_edit_options(customer_edit_search_tf.value or "")

		page.dialog = ft.AlertDialog(
			modal=True,
			title=ft.Row(
				[
					ft.Icon(ft.icons.EDIT_ROUNDED, color=ThemeColors.ACCENT_BLUE, size=24),
					ft.Text(f"Editar registro: {item.get('codigo') or 'Activo'}", weight="bold"),
				],
				spacing=10,
			),
			content=ft.Container(
				width=760,
				height=560,
				padding=20,
				border_radius=18,
				bgcolor=ft.colors.with_opacity(0.03, ft.colors.WHITE),
				content=ft.Column(
					[
						ft.Text("Identificación del activo", size=12, weight="bold", color=ThemeColors.TEXT_SECONDARY),
						ft.Row([name_tf, factura_tf], spacing=10, wrap=True),
						ft.Divider(height=1, color=ft.colors.with_opacity(0.10, ft.colors.WHITE)),
						ft.Text("Características", size=12, weight="bold", color=ThemeColors.TEXT_SECONDARY),
						ft.Row([marca_tf, modelo_tf], spacing=10, wrap=True),
						serial_tf,
						mac_tf,
						ft.Divider(height=1, color=ft.colors.with_opacity(0.10, ft.colors.WHITE)),
						ft.Text("Asignación y ubicación", size=12, weight="bold", color=ThemeColors.TEXT_SECONDARY),
						ft.Row([location_dd, responsible_edit_dd], spacing=10, wrap=True),
						ft.Divider(height=1, color=ft.colors.with_opacity(0.10, ft.colors.WHITE)),
						ft.Text("Cliente relacionado", size=12, weight="bold", color=ThemeColors.TEXT_SECONDARY),
						ft.Row([customer_edit_search_tf, customer_edit_dd], spacing=10, wrap=True),
					],
					spacing=10,
					scroll=ft.ScrollMode.AUTO,
				),
			),
			actions=[
				ft.TextButton("Cancelar", on_click=lambda e: setattr(page.dialog, "open", False) or _safe_page_update()),
				ft.ElevatedButton("Guardar", style=JetBrainsTheme.primary_button_style(), on_click=do_save),
			],
		)
		page.dialog.open = True
		_safe_page_update()

	def _open_acta_dialog(item_id: str | None = None):
		if not _ensure_catalogs_for_edit():
			return

		current_username = ""
		if Session.user and isinstance(Session.user, dict):
			current_username = str(Session.user.get("username") or "").strip()

		recibe_candidates = [
			u for u in users_all
			if str(u.get("id") or "").strip() and str(u.get("username") or "").strip() != current_username
		]

		if not recibe_candidates:
			show_snack("No hay usuarios CRM disponibles para seleccionar 'Recibe'.", is_error=True)
			return

		selectable_items = [it for it in items_all if str(it.get("id") or "").strip()]
		if not selectable_items:
			show_snack("No hay items disponibles para generar el acta. Ajusta filtros e intenta nuevamente.", is_error=True)
			return

		selected_item_ids = set()
		if item_id:
			selected_item_ids.add(str(item_id))
		elif selectable_items:
			selected_item_ids.add(str(selectable_items[0].get("id")))

		recibe_dd = ft.Dropdown(
			label="Recibe (CRM)",
			width=500,
			options=[
				ft.dropdown.Option(
					key=str(u.get("id")),
					text=f"{u.get('full_name') or u.get('username') or 'Usuario'} | {u.get('rol') or 'Cargo no registrado'}",
				)
				for u in recibe_candidates
			],
			value=str(recibe_candidates[0].get("id")),
			**JetBrainsTheme.input_style(),
		)

		obs_tf = ft.TextField(
			label="Observacion",
			hint_text="Detalle adicional de entrega/recepcion",
			multiline=True,
			min_lines=3,
			max_lines=5,
			width=500,
			**JetBrainsTheme.input_style(),
		)

		selected_count_txt = ft.Text("", color=ThemeColors.TEXT_SECONDARY)

		def _item_label(it: dict) -> str:
			codigo = str(it.get("codigo") or "---")
			nombre = str(it.get("nombre") or "Activo")
			serial = str(it.get("serial") or "---")
			return f"{codigo} | {nombre} | Serie: {serial}"

		items_check_column = ft.Column(spacing=6, height=220, scroll=ft.ScrollMode.AUTO)

		def _refresh_selected_count():
			selected_count_txt.value = f"Items seleccionados: {len(selected_item_ids)}"

		def _render_item_checkboxes():
			items_check_column.controls.clear()
			for it in selectable_items:
				iid = str(it.get("id"))
				chk = ft.Checkbox(
					label=_item_label(it),
					value=(iid in selected_item_ids),
				)

				def _on_change(e, current_id=iid):
					if e.control.value:
						selected_item_ids.add(current_id)
					else:
						selected_item_ids.discard(current_id)
					_refresh_selected_count()
					_safe_page_update()

				chk.on_change = _on_change
				items_check_column.controls.append(chk)
			_refresh_selected_count()

		def _select_all_items(_):
			selected_item_ids.clear()
			for it in selectable_items:
				selected_item_ids.add(str(it.get("id")))
			_render_item_checkboxes()
			_safe_page_update()

		def _clear_selected_items(_):
			selected_item_ids.clear()
			_render_item_checkboxes()
			_safe_page_update()

		_render_item_checkboxes()

		def _generate(_):
			recibe_id = str(recibe_dd.value or "").strip()
			if not recibe_id:
				show_snack("Debes seleccionar el usuario que recibe.", is_error=True)
				return
			if not selected_item_ids:
				show_snack("Debes seleccionar al menos un item para generar el acta.", is_error=True)
				return

			payload = {
				"recibe_user_id": recibe_id,
				"observacion": (obs_tf.value or "").strip(),
				"item_ids": list(selected_item_ids),
			}
			if item_id:
				payload["item_id"] = item_id

			def _download_worker():
				try:
					show_snack("Generando ACTA DE ENTREGA - RECEPCION...")
					pdf_path = download_acta_entrega_recepcion(payload)
					webbrowser.open(f"file://{pdf_path}")
					show_snack("ACTA generada correctamente")
				except Exception as ex:
					show_snack(f"Error al generar acta: {ex}", is_error=True)

			page.dialog.open = False
			_safe_page_update()
			threading.Thread(target=_download_worker, daemon=True).start()

		page.dialog = ft.AlertDialog(
			modal=True,
			title=ft.Text("Generar ACTA DE ENTREGA - RECEPCION", weight="bold"),
			content=ft.Container(
				width=720,
				content=ft.Column(
					[
						ft.Text("Selecciona item o items a entregar", color=ThemeColors.TEXT_SECONDARY),
						ft.Row(
							[
								ft.TextButton("Seleccionar todos", on_click=_select_all_items),
								ft.TextButton("Limpiar seleccion", on_click=_clear_selected_items),
								selected_count_txt,
							],
							alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
						),
						ft.Container(
							height=240,
							padding=8,
							border=ft.border.all(1, ft.colors.with_opacity(0.12, ft.colors.WHITE)),
							border_radius=10,
							content=items_check_column,
						),
						ft.Divider(height=1, color=ft.colors.with_opacity(0.10, ft.colors.WHITE)),
						ft.Text("Entrega: usuario logueado (CRM)", color=ThemeColors.TEXT_SECONDARY),
						recibe_dd,
						obs_tf,
					],
					spacing=10,
				),
			),
			actions=[
				ft.TextButton("Cancelar", on_click=lambda e: setattr(page.dialog, "open", False) or _safe_page_update()),
				ft.ElevatedButton("Generar PDF", style=JetBrainsTheme.primary_button_style(), on_click=_generate),
			],
		)
		page.dialog.open = True
		_safe_page_update()

	def _asset_row(item: dict) -> ft.Control:
		loc_type = _location_type(item)
		loc_color = ThemeColors.ACCENT_BLUE if loc_type == "BODEGA" else ThemeColors.ACCENT_MAGENTA
		responsable = item.get("responsable_nombre") or "---"
		priority_text, priority_color, priority_score = _priority_label(item)

		row_bg = ft.colors.with_opacity(0.02, ft.colors.WHITE)
		if priority_score >= 2:
			row_bg = ft.colors.with_opacity(0.10, ft.colors.RED_900)
		elif priority_score == 1:
			row_bg = ft.colors.with_opacity(0.08, ft.colors.AMBER_900)

		actions = ft.Row(
			[
				ft.IconButton(
					icon=ft.icons.EDIT_NOTE_ROUNDED,
					tooltip="Editar registro",
					icon_size=18,
					icon_color=ThemeColors.ACCENT_BLUE,
					on_click=lambda e, it=item: _build_edit_dialog(it),
				),
				ft.IconButton(
					icon=ft.icons.TIMELINE,
					tooltip="Ver historial del activo",
					icon_size=18,
					icon_color=ThemeColors.ACCENT_BLUE,
					on_click=lambda e, it=item: navigate("item_traceability", item_id=it.get("id"), item_data=it),
				),
			],
			spacing=0,
		)

		return ft.Container(
			width=ASSET_TABLE_WIDTH,
			padding=ft.padding.symmetric(horizontal=14, vertical=8),
			bgcolor=row_bg,
			border=ft.border.only(bottom=ft.BorderSide(1, ft.colors.with_opacity(0.05, ft.colors.WHITE))),
			content=ft.Row(
				[
					ft.Container(width=120, content=ft.Text(item.get("codigo", "---"), size=12, weight="bold", overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(width=260, content=ft.Text(item.get("nombre", "---"), size=12, overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(width=120, content=ft.Text(item.get("estado", "---"), size=11, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(width=340, content=ft.Text(_location_label(item), size=11, weight="bold", color=loc_color, overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(width=180, content=ft.Text(responsable, size=11, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(width=120, content=ft.Text(priority_text, size=11, weight="bold", color=priority_color, overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(width=74, content=actions),
				],
				spacing=10,
			),
		)

	def _movement_row(mov: dict) -> ft.Control:
		item = mov.get("item") or {}
		tipo = mov.get("tipo_movimiento") or mov.get("tipo") or "---"
		fecha = str(mov.get("fecha") or "---")[:19].replace("T", " ")
		item_id = item.get("id")
		return ft.Container(
			width=MOV_TABLE_WIDTH,
			padding=ft.padding.symmetric(horizontal=14, vertical=8),
			border=ft.border.only(bottom=ft.BorderSide(1, ft.colors.with_opacity(0.05, ft.colors.WHITE))),
			content=ft.Row(
				[
					ft.Container(width=150, content=ft.Text(fecha, size=11, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(width=120, content=ft.Text(item.get("codigo", "---"), size=12, weight="bold", overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(width=230, content=ft.Text(item.get("nombre", "---"), size=11, overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(width=145, content=ft.Text(tipo, size=11, color=ThemeColors.ACCENT_BLUE, overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(width=220, content=ft.Text(_read_target_name(mov.get("origen")), size=10, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(width=220, content=ft.Text(_read_target_name(mov.get("destino")), size=10, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(width=120, content=ft.Text(mov.get("ot_id") or "---", size=11, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
					ft.Container(
						width=48,
						content=ft.IconButton(
							icon=ft.icons.PICTURE_AS_PDF,
							icon_size=16,
							tooltip="Generar acta para este activo",
							on_click=(lambda e, iid=item_id: _open_acta_dialog(iid)) if item_id else None,
						),
					),
				],
				spacing=8,
			),
		)

	def refresh_assets_table():
		rows_assets.controls.clear()
		if not items_all:
			rows_assets.controls.append(
				ft.Container(
					padding=ft.padding.all(20),
					content=ft.Text("No hay activos para el filtro aplicado.", color=ThemeColors.TEXT_SECONDARY, italic=True),
				)
			)
			return
		for item in items_all:
			rows_assets.controls.append(_asset_row(item))

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
		for mov in movements_recent:
			rows_kardex.controls.append(_movement_row(mov))

	def apply_filters(e=None):
		page_state["page"] = 1
		_schedule_load(0.01)

	def _apply_pending_filter(missing_key: str):
		pending_state[missing_key] = not pending_state[missing_key]
		page_state["page"] = 1
		_schedule_load(0.01)

	def _clear_pending_filters(_=None):
		pending_state["missing_bodega"] = False
		pending_state["missing_responsable"] = False
		pending_state["missing_cliente"] = False
		page_state["page"] = 1
		_schedule_load(0.01)

	pending_bodega_btn.on_click = lambda e: _apply_pending_filter("missing_bodega")
	pending_responsable_btn.on_click = lambda e: _apply_pending_filter("missing_responsable")
	pending_cliente_btn.on_click = lambda e: _apply_pending_filter("missing_cliente")
	clear_pending_btn.on_click = _clear_pending_filters

	where_dd.on_change = apply_filters
	responsable_dd.on_change = apply_filters
	cliente_dd.on_change = apply_filters
	prioritize_pending_sw.on_change = apply_filters

	def _go_prev(_):
		if page_state["page"] > 1:
			page_state["page"] -= 1
			_schedule_load(0.01)

	def _go_next(_):
		if page_state["page"] < page_state["total_pages"]:
			page_state["page"] += 1
			_schedule_load(0.01)

	prev_btn = ft.TextButton("◀ Anterior", on_click=_go_prev)
	next_btn = ft.TextButton("Siguiente ▶", on_click=_go_next)

	def load_data(refresh_catalogs: bool = True):
		loading.visible = True
		if not _safe_page_update():
			_schedule_load(0.25)
			return

		try:
			params = {
				"page": page_state["page"],
				"page_size": page_state["page_size"],
				"mov_limit": 25,
				"search": (search_tf.value or "").strip(),
				"where": (where_dd.value or "TODOS").strip().upper(),
				"responsable": (responsable_dd.value or "TODOS").strip(),
				"cliente": (cliente_dd.value or "TODOS").strip(),
				"missing_bodega": 1 if pending_state["missing_bodega"] else 0,
				"missing_responsable": 1 if pending_state["missing_responsable"] else 0,
				"missing_cliente": 1 if pending_state["missing_cliente"] else 0,
			}

			payload = get_kardex_dashboard(params) or {}

			stats = payload.get("stats") or {}
			pagination = payload.get("pagination") or {}
			catalogs = payload.get("catalogs") or {}

			items_all.clear()
			items_all.extend(payload.get("items") or [])
			movements_recent.clear()
			movements_recent.extend(payload.get("movements") or [])

			stats_total.value = str(stats.get("total_items", 0))
			stats_bodega.value = str(stats.get("en_bodega", 0))
			stats_cliente.value = str(stats.get("en_cliente", 0))
			stats_sin_bodega.value = str(stats.get("sin_bodega", 0))
			stats_sin_responsable.value = str(stats.get("sin_responsable", 0))
			stats_sin_cliente.value = str(stats.get("sin_cliente", 0))

			pending_bodega_btn.text = "Quitar filtro" if pending_state["missing_bodega"] else "Ver pendientes"
			pending_responsable_btn.text = "Quitar filtro" if pending_state["missing_responsable"] else "Ver pendientes"
			pending_cliente_btn.text = "Quitar filtro" if pending_state["missing_cliente"] else "Ver pendientes"
			clear_pending_btn.visible = any(pending_state.values())

			pending_bodega_card.content = _pending_card("SIN BODEGA", stats_sin_bodega, pending_bodega_btn, pending_state["missing_bodega"])
			pending_responsable_card.content = _pending_card("SIN RESPONSABLE", stats_sin_responsable, pending_responsable_btn, pending_state["missing_responsable"])
			pending_cliente_card.content = _pending_card("SIN CLIENTE", stats_sin_cliente, pending_cliente_btn, pending_state["missing_cliente"])

			page_state["total"] = int(pagination.get("total", len(items_all)))
			page_state["total_pages"] = max(1, int(pagination.get("total_pages", 1)))
			page_state["page"] = max(1, int(pagination.get("page", page_state["page"])))

			pagination_txt.value = f"Página {page_state['page']}/{page_state['total_pages']} · {page_state['total']} registros"
			prev_btn.disabled = page_state["page"] <= 1
			next_btn.disabled = page_state["page"] >= page_state["total_pages"]

			if refresh_catalogs:
				_apply_catalogs(catalogs)

			if prioritize_pending_sw.value:
				items_all.sort(key=lambda it: (-_priority_label(it)[2], str(it.get("codigo") or "")))

			refresh_assets_table()
			refresh_kardex_table()
		except Exception as ex:
			show_snack(f"Error cargando KARDEX: {ex}", is_error=True)
		finally:
			loading.visible = False
			_safe_page_update()

	_schedule_load(0.2)

	return ft.Column(
		[
			ft.Row(
				[
					ft.Text("KARDEX de Activos", size=22, weight="bold", color=ThemeColors.TEXT_PRIMARY),
					ft.Row(
						[
							ft.ElevatedButton(
								"Nuevo ingreso de equipamiento",
								icon=ft.icons.ADD_BOX_ROUNDED,
								style=JetBrainsTheme.primary_button_style(),
								on_click=lambda e: navigate("create_item", tipo_item_default="equipo"),
							),
							ft.ElevatedButton(
								"Buscar",
								icon=ft.icons.SEARCH,
								style=JetBrainsTheme.primary_button_style(),
								on_click=lambda e: apply_filters(),
							),
							ft.ElevatedButton(
								"Actualizar",
								icon=ft.icons.REFRESH_ROUNDED,
								style=JetBrainsTheme.primary_button_style(),
								on_click=lambda e: load_data(True),
							),
							ft.ElevatedButton(
								"ACTA ENTREGA-RECEPCION",
								icon=ft.icons.PICTURE_AS_PDF,
								style=JetBrainsTheme.primary_button_style(),
								on_click=lambda e: _open_acta_dialog(),
							),
						],
						spacing=10,
					),
				],
				alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
			),
			ft.Row(
				[
					ft.Container(
						**JetBrainsTheme.card_style(),
						content=ft.Column(
							[
								ft.Text("ACTIVOS TOTALES", size=11, color=ThemeColors.TEXT_SECONDARY, weight="bold"),
								stats_total,
							],
							spacing=6,
						),
						expand=True,
					),
					ft.Container(
						**JetBrainsTheme.card_style(),
						content=ft.Column(
							[
								ft.Text("EN BODEGA", size=11, color=ThemeColors.TEXT_SECONDARY, weight="bold"),
								stats_bodega,
							],
							spacing=6,
						),
						expand=True,
					),
					ft.Container(
						**JetBrainsTheme.card_style(),
						content=ft.Column(
							[
								ft.Text("EN CLIENTE", size=11, color=ThemeColors.TEXT_SECONDARY, weight="bold"),
								stats_cliente,
							],
							spacing=6,
						),
						expand=True,
					),
				],
				spacing=12,
			),
			ft.Row(
				[pending_bodega_card, pending_responsable_card, pending_cliente_card],
				spacing=12,
			),
			ft.Container(
				**JetBrainsTheme.card_style(),
				content=ft.Column(
					[
						ft.Row(
							[
								search_tf,
								where_dd,
								responsable_dd,
								cliente_search_tf,
								cliente_dd,
								prioritize_pending_sw,
								clear_pending_btn,
							],
							spacing=12,
							wrap=True,
						),
						loading,
						ft.Divider(height=1, color=ft.colors.with_opacity(0.08, ft.colors.WHITE)),
						ft.Text("Registro de Activos por Ubicación Actual", size=13, weight="bold"),
						ft.Row(
							[
								ft.Container(
									width=ASSET_TABLE_WIDTH,
									content=ft.Column(
										[
											_table_header(ASSET_TABLE_COLUMNS, ASSET_TABLE_WIDTH),
											ft.Container(height=300, content=rows_assets),
										],
										spacing=0,
									),
								)
							],
							scroll=ft.ScrollMode.ALWAYS,
						),
						ft.Row(
							[prev_btn, pagination_txt, next_btn],
							alignment=ft.MainAxisAlignment.END,
						),
					],
					spacing=10,
				),
			),
			ft.Container(
				**JetBrainsTheme.card_style(),
				expand=True,
				content=ft.Column(
					[
						ft.Text("Libro KARDEX - Movimientos Recientes", size=13, weight="bold"),
						ft.Row(
							[
								ft.Container(
									width=MOV_TABLE_WIDTH,
									content=ft.Column(
										[
											_table_header(MOV_TABLE_COLUMNS, MOV_TABLE_WIDTH),
											ft.Container(height=260, content=rows_kardex),
										],
										spacing=0,
									),
								)
							],
							scroll=ft.ScrollMode.ALWAYS,
						),
					],
					spacing=10,
				),
			),
		],
		spacing=12,
		expand=True,
		scroll=ft.ScrollMode.AUTO,
	)
