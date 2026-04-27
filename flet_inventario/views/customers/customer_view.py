import flet as ft
import threading

from core.api_client import APIClient
from core.session import Session
from core.permissions import can_access
from core.theme import ThemeColors, JetBrainsTheme


def show_snack(page, msg, is_error=False):
    page.snack_bar = ft.SnackBar(
        ft.Text(msg, color=ft.colors.WHITE, weight="bold"),
        bgcolor=ft.colors.RED_700 if is_error else ft.colors.GREEN_700,
        duration=3000,
    )
    page.snack_bar.open = True
    page.update()


def customer_view(page: ft.Page, navigate):
    rol = (Session.user or {}).get("rol", "tecnico")

    search_tf = ft.TextField(
        label="Buscar cliente",
        expand=True,
        on_submit=lambda e: load(),
        **JetBrainsTheme.input_style(),
    )

    loading  = ft.ProgressBar(visible=False, color=ThemeColors.ACCENT_BLUE)
    rows_col = ft.Column(spacing=0)

    COL = {"nom": 280, "suc": 160, "city": 130}

    header_row = ft.Container(
        bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
        content=ft.Row([
            ft.Container(width=COL["nom"],  content=ft.Text("CLIENTE / EMPRESA", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["suc"],  content=ft.Text("SUCURSAL",           size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["city"], content=ft.Text("CIUDAD",             size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(expand=True,       content=ft.Text("DIRECCIÓN",          size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
        ], spacing=8),
    )

    # ── Fila clicable ─────────────────────────────────────────────────────────
    def _make_row(c):
        loc = c.get("ubicacion") or {}
        initial = (c.get("nombre_cliente") or "?")[0].upper()
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.colors.with_opacity(0.05, ft.colors.WHITE))),
            ink=True,
            on_click=lambda e, obj=c: open_detail(obj),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        ft.colors.with_opacity(0.04, ft.colors.WHITE) if e.data == "true"
                        else ft.colors.TRANSPARENT) or page.update()
            ),
            content=ft.Row([
                ft.Container(width=COL["nom"], content=ft.Row([
                    ft.Container(
                        width=30, height=30, border_radius=15,
                        bgcolor=ThemeColors.ACCENT_BLUE,
                        alignment=ft.alignment.center,
                        content=ft.Text(initial, size=12, weight="bold", color=ft.colors.WHITE),
                    ),
                    ft.Column([
                        ft.Text(c.get("nombre_cliente", "—"), weight="bold", size=13,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=0, tight=True),
                ], spacing=8)),
                ft.Container(width=COL["suc"],  content=ft.Text(c.get("sucursal", "Principal"), size=12, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=COL["city"], content=ft.Text(loc.get("ciudad", "—"), size=12, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(expand=True,       content=ft.Text(loc.get("direccion", "—"), size=11, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
            ], spacing=8),
        )

    # ── Carga ─────────────────────────────────────────────────────────────────
    def load():
        loading.visible = True
        page.update()
        try:
            customers = APIClient.get("inventory/customers/") or []
            q = (search_tf.value or "").strip().lower()
            if q:
                customers = [c for c in customers
                             if q in c.get("nombre_cliente", "").lower()
                             or q in (c.get("ubicacion") or {}).get("ciudad", "").lower()]
            rows_col.controls.clear()
            if not customers:
                rows_col.controls.append(ft.Container(
                    padding=ft.padding.all(30),
                    content=ft.Text("No hay clientes registrados.", italic=True, color=ThemeColors.TEXT_SECONDARY),
                ))
            else:
                for c in customers:
                    rows_col.controls.append(_make_row(c))
        except Exception as ex:
            show_snack(page, f"Error al cargar clientes: {ex}", True)
        loading.visible = False
        page.update()

    # ── Detalle al hacer clic ─────────────────────────────────────────────────
    def open_detail(c):
        loc = c.get("ubicacion") or {}

        def info(label, value, icon):
            return ft.Row([
                ft.Icon(icon, size=14, color=ThemeColors.ACCENT_BLUE),
                ft.Text(label, size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY, width=85),
                ft.Text(str(value) if value else "—", size=13),
            ], spacing=8)

        def close_then(fn):
            def _h(e):
                page.dialog.open = False
                page.update()
                fn()
            return _h

        btns = [ft.TextButton("Cerrar", on_click=lambda e: setattr(page.dialog, "open", False) or page.update())]
        if can_access(rol, "customer:update"):
            btns.insert(0, ft.ElevatedButton("Editar", icon=ft.icons.EDIT_ROUNDED,
                                              style=JetBrainsTheme.primary_button_style(),
                                              on_click=close_then(lambda: open_form(c))))
        if can_access(rol, "customer:delete"):
            btns.insert(1 if can_access(rol, "customer:update") else 0,
                        ft.ElevatedButton("Eliminar", icon=ft.icons.DELETE_ROUNDED,
                                          bgcolor=ft.colors.RED_700, color=ft.colors.WHITE,
                                          on_click=close_then(lambda: confirm_delete(c))))

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.BUSINESS_ROUNDED, color=ThemeColors.ACCENT_BLUE, size=26),
                ft.Column([
                    ft.Text(c.get("nombre_cliente", "—"), weight="bold", size=16),
                    ft.Text(c.get("sucursal", "Principal"), size=11, color=ThemeColors.TEXT_SECONDARY),
                ], spacing=1, tight=True),
            ], spacing=12),
            content=ft.Container(width=400, content=ft.Column([
                info("Ciudad",    loc.get("ciudad"),    ft.icons.LOCATION_CITY),
                info("Dirección", loc.get("direccion"), ft.icons.LOCATION_ON),
            ], tight=True, spacing=12)),
            actions=btns,
        )
        page.dialog.open = True
        page.update()

    # ── Formulario crear / editar ─────────────────────────────────────────────
    def open_form(cust=None):
        is_edit = cust is not None
        loc     = cust.get("ubicacion") or {} if is_edit else {}

        name_tf = ft.TextField(label="Razón Social / Nombre *",
                               value=cust.get("nombre_cliente", "") if is_edit else "",
                               **JetBrainsTheme.input_style())
        suc_tf  = ft.TextField(label="Nombre de Sucursal",
                               value=cust.get("sucursal", "") if is_edit else "",
                               **JetBrainsTheme.input_style())
        city_tf = ft.TextField(label="Ciudad",
                               value=loc.get("ciudad", "") if is_edit else "",
                               **JetBrainsTheme.input_style())
        addr_tf = ft.TextField(label="Dirección Completa",
                               value=loc.get("direccion", "") if is_edit else "",
                               multiline=True, min_lines=2, **JetBrainsTheme.input_style())

        def save(e):
            if not name_tf.value.strip():
                show_snack(page, "El nombre del cliente es obligatorio", True)
                return
            payload = {
                "nombre_cliente": name_tf.value.strip(),
                "sucursal":       suc_tf.value.strip(),
                "ubicacion": {"ciudad": city_tf.value.strip(), "direccion": addr_tf.value.strip()},
            }
            try:
                if is_edit:
                    APIClient.put(f"inventory/customers/{cust['id']}/", json=payload)
                    show_snack(page, f"Cliente '{name_tf.value.strip()}' actualizado")
                else:
                    APIClient.post("inventory/customers/", json=payload)
                    show_snack(page, f"Cliente '{name_tf.value.strip()}' registrado")
                page.dialog.open = False
                page.update()
                load()
            except Exception as ex:
                show_snack(page, f"Error: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.BUSINESS_ROUNDED, color=ThemeColors.ACCENT_BLUE),
                ft.Text("Editar Cliente" if is_edit else "Nuevo Cliente", weight="bold"),
            ], spacing=10),
            content=ft.Container(width=420,
                                  content=ft.Column([name_tf, suc_tf, city_tf, addr_tf], tight=True, spacing=15)),
            actions=[
                ft.TextButton("Cancelar",
                              on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Guardar", style=JetBrainsTheme.primary_button_style(), on_click=save),
            ],
        )
        page.dialog.open = True
        page.update()

    # ── Confirmar eliminación ─────────────────────────────────────────────────
    def confirm_delete(cust):
        def do_delete(e):
            try:
                APIClient.delete(f"inventory/customers/{cust['id']}/")
                page.dialog.open = False
                page.update()
                load()
                show_snack(page, f"Cliente '{cust.get('nombre_cliente')}' eliminado")
            except Exception as ex:
                show_snack(page, f"Error al eliminar: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.icons.WARNING_ROUNDED, color=ft.colors.RED_400),
                          ft.Text("Eliminar Cliente", weight="bold")], spacing=10),
            content=ft.Text(f"¿Eliminar al cliente '{cust.get('nombre_cliente')}'?\nEsta acción es irreversible.", size=14),
            actions=[
                ft.TextButton("No, cancelar",
                              on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Sí, eliminar", bgcolor=ft.colors.RED_700,
                                  color=ft.colors.WHITE, on_click=do_delete),
            ],
        )
        page.dialog.open = True
        page.update()

    # ── Layout ────────────────────────────────────────────────────────────────
    threading.Timer(0.1, load).start()

    return ft.Column([
        ft.Row([
            ft.Text("Cartera de Clientes", size=24, weight="bold", color=ThemeColors.TEXT_PRIMARY),
            ft.ElevatedButton("Nuevo Cliente", icon=ft.icons.PERSON_ADD_ALT_1_ROUNDED,
                              style=JetBrainsTheme.primary_button_style(),
                              on_click=lambda e: open_form(),
                              visible=can_access(rol, "customer:create")),
        ], alignment="justify"),
        ft.Container(
            **JetBrainsTheme.card_style(),
            content=ft.Row([
                search_tf,
                ft.ElevatedButton("Buscar", icon=ft.icons.SEARCH,
                                  style=JetBrainsTheme.primary_button_style(),
                                  on_click=lambda e: load(), height=45),
                ft.IconButton(ft.icons.REFRESH_ROUNDED, tooltip="Actualizar", on_click=lambda e: load()),
            ], spacing=12),
        ),
        loading,
        ft.Container(
            **JetBrainsTheme.card_style(),
            content=ft.Column([header_row,
                               ft.Divider(height=1, color=ft.colors.with_opacity(0.06, ft.colors.WHITE)),
                               rows_col], spacing=0),
        ),
    ], expand=True, spacing=15, scroll=ft.ScrollMode.AUTO)
