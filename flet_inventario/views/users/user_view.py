import flet as ft
import threading

from core.api_client import APIClient
from core.session import Session
from core.permissions import can_access
from core.theme import ThemeColors, JetBrainsTheme
from components.status_badge import status_badge


def show_snack(page, msg, is_error=False):
    page.snack_bar = ft.SnackBar(
        ft.Text(msg, color=ft.colors.WHITE, weight="bold"),
        bgcolor=ft.colors.RED_700 if is_error else ft.colors.GREEN_700,
        duration=3000,
    )
    page.snack_bar.open = True
    page.update()


def user_view(page: ft.Page, navigate):
    current_user = Session.user or {}
    rol = current_user.get("rol", "tecnico")

    search_tf = ft.TextField(
        label="Buscar usuario",
        expand=True,
        on_submit=lambda e: load_users(),
        **JetBrainsTheme.input_style(),
    )

    loading  = ft.ProgressBar(visible=False, color=ThemeColors.ACCENT_BLUE)
    rows_col = ft.Column(spacing=0)

    COL = {"user": 260, "rol": 160, "date": 130}

    header_row = ft.Container(
        bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
        content=ft.Row([
            ft.Container(width=COL["user"], content=ft.Text("USUARIO", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["rol"],  content=ft.Text("ROL",     size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["date"], content=ft.Text("CREADO",  size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
        ], spacing=8),
    )

    def _make_row(u):
        is_self = u.get("id") == current_user.get("id")
        created = (u.get("created_at") or "")[:10] or "—"
        initial = (u.get("username") or "?")[0].upper()
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.colors.with_opacity(0.05, ft.colors.WHITE))),
            ink=True,
            on_click=lambda e, obj=u: open_detail(obj),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        ft.colors.with_opacity(0.04, ft.colors.WHITE) if e.data == "true"
                        else ft.colors.TRANSPARENT) or page.update()
            ),
            content=ft.Row([
                ft.Container(width=COL["user"], content=ft.Row([
                    ft.Container(
                        width=30, height=30, border_radius=15,
                        bgcolor=ThemeColors.ACCENT_BLUE,
                        alignment=ft.alignment.center,
                        content=ft.Text(initial, size=12, weight="bold", color=ft.colors.WHITE),
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text(u.get("username", "—"), weight="bold", size=13),
                            ft.Container(
                                content=ft.Text("Tú", size=9, weight="bold", color=ft.colors.WHITE),
                                bgcolor=ThemeColors.ACCENT_BLUE,
                                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                border_radius=8,
                                visible=is_self,
                            ),
                        ], spacing=6),
                    ], spacing=0, tight=True),
                ], spacing=8)),
                ft.Container(width=COL["rol"],  content=status_badge(u.get("rol", "—"))),
                ft.Container(width=COL["date"], content=ft.Text(created, size=12, color=ThemeColors.TEXT_SECONDARY)),
            ], spacing=8),
        )

    def load_users():
        loading.visible = True
        page.update()
        try:
            data = APIClient.get("users/") or []
            q = (search_tf.value or "").strip().lower()
            if q:
                data = [u for u in data if q in u.get("username", "").lower()]
            rows_col.controls.clear()
            if not data:
                rows_col.controls.append(ft.Container(
                    padding=ft.padding.all(30),
                    content=ft.Text("No hay usuarios registrados.", italic=True, color=ThemeColors.TEXT_SECONDARY),
                ))
            else:
                for u in data:
                    rows_col.controls.append(_make_row(u))
        except Exception as ex:
            show_snack(page, f"Error al cargar usuarios: {ex}", True)
        loading.visible = False
        page.update()

    def open_detail(u):
        is_self  = u.get("id") == current_user.get("id")
        created  = (u.get("created_at") or "")[:10] or "—"

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

        if is_self or can_access(rol, "user:update"):
            btns.insert(0, ft.ElevatedButton("Cambiar Clave", icon=ft.icons.PASSWORD_ROUNDED,
                                              style=JetBrainsTheme.primary_button_style(),
                                              on_click=close_then(lambda: open_password(u))))

        if can_access(rol, "user:update") and not is_self:
            btns.insert(1, ft.ElevatedButton("Cambiar Rol", icon=ft.icons.MANAGE_ACCOUNTS_ROUNDED,
                                              style=JetBrainsTheme.primary_button_style(),
                                              on_click=close_then(lambda: open_role_edit(u))))

        if can_access(rol, "user:delete") and not is_self:
            btns.append(ft.ElevatedButton("Eliminar", icon=ft.icons.DELETE_FOREVER_ROUNDED,
                                          bgcolor=ft.colors.RED_700, color=ft.colors.WHITE,
                                          on_click=close_then(lambda: confirm_delete(u))))

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Container(
                    width=40, height=40, border_radius=20,
                    bgcolor=ThemeColors.ACCENT_BLUE,
                    alignment=ft.alignment.center,
                    content=ft.Text((u.get("username") or "?")[0].upper(),
                                    size=16, weight="bold", color=ft.colors.WHITE),
                ),
                ft.Column([
                    ft.Text(u.get("username", "—"), weight="bold", size=16),
                    status_badge(u.get("rol", "—")),
                ], spacing=4, tight=True),
            ], spacing=12),
            content=ft.Container(width=380, content=ft.Column([
                info("Creado", created, ft.icons.CALENDAR_TODAY),
            ], tight=True, spacing=12)),
            actions=btns,
        )
        page.dialog.open = True
        page.update()

    def open_create(e):
        user_tf = ft.TextField(label="Nombre de Usuario", **JetBrainsTheme.input_style())
        pass_tf = ft.TextField(label="Contraseña (mín. 4 caracteres)",
                               password=True, can_reveal_password=True,
                               **JetBrainsTheme.input_style())
        rol_dd  = ft.Dropdown(
            label="Rol",
            options=[
                ft.dropdown.Option("tecnico",        text="Técnico"),
                ft.dropdown.Option("administrativo", text="Administrativo"),
                ft.dropdown.Option("admin",          text="Administrador"),
            ],
            **JetBrainsTheme.input_style(),
        )

        def save(e):
            if not user_tf.value or not pass_tf.value or not rol_dd.value:
                show_snack(page, "Todos los campos son obligatorios", True)
                return
            if len(pass_tf.value) < 4:
                show_snack(page, "La contraseña debe tener al menos 4 caracteres", True)
                return
            try:
                APIClient.post("users/", json={
                    "username": user_tf.value.strip(),
                    "password": pass_tf.value,
                    "rol":      rol_dd.value,
                })
                page.dialog.open = False
                page.update()
                load_users()
                show_snack(page, f"Usuario '{user_tf.value.strip()}' creado")
            except Exception as ex:
                show_snack(page, f"Error: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.PERSON_ADD_ROUNDED, color=ThemeColors.ACCENT_BLUE),
                ft.Text("Nuevo Usuario", weight="bold"),
            ], spacing=10),
            content=ft.Container(width=400,
                                  content=ft.Column([user_tf, pass_tf, rol_dd], tight=True, spacing=15)),
            actions=[
                ft.TextButton("Cancelar",
                              on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Crear Usuario", style=JetBrainsTheme.primary_button_style(), on_click=save),
            ],
        )
        page.dialog.open = True
        page.update()

    def open_password(u):
        pass_tf = ft.TextField(label="Nueva Contraseña (mín. 4 caracteres)",
                               password=True, can_reveal_password=True,
                               **JetBrainsTheme.input_style())

        def save(e):
            if not pass_tf.value or len(pass_tf.value) < 4:
                show_snack(page, "La contraseña debe tener al menos 4 caracteres", True)
                return
            try:
                APIClient.put(f"users/{u['id']}/", json={"password": pass_tf.value})
                page.dialog.open = False
                page.update()
                show_snack(page, "Contraseña actualizada correctamente")
            except Exception as ex:
                show_snack(page, f"Error: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.PASSWORD_ROUNDED, color=ThemeColors.ACCENT_BLUE),
                ft.Text(f"Cambiar clave: {u.get('username')}", weight="bold"),
            ], spacing=10),
            content=ft.Container(width=380, content=pass_tf),
            actions=[
                ft.TextButton("Cancelar",
                              on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Actualizar", style=JetBrainsTheme.primary_button_style(), on_click=save),
            ],
        )
        page.dialog.open = True
        page.update()

    def open_role_edit(u):
        rol_dd = ft.Dropdown(
            label="Nuevo Rol",
            value=u.get("rol"),
            options=[
                ft.dropdown.Option("tecnico",        text="Técnico"),
                ft.dropdown.Option("administrativo", text="Administrativo"),
                ft.dropdown.Option("admin",          text="Administrador"),
            ],
            **JetBrainsTheme.input_style(),
        )

        def save(e):
            try:
                APIClient.put(f"users/{u['id']}/", json={"rol": rol_dd.value})
                page.dialog.open = False
                page.update()
                load_users()
                show_snack(page, f"Rol de '{u.get('username')}' actualizado")
            except Exception as ex:
                show_snack(page, f"Error: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.MANAGE_ACCOUNTS_ROUNDED, color=ThemeColors.ACCENT_BLUE),
                ft.Text(f"Editar rol: {u.get('username')}", weight="bold"),
            ], spacing=10),
            content=ft.Container(width=380, content=rol_dd),
            actions=[
                ft.TextButton("Cancelar",
                              on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Guardar", style=JetBrainsTheme.primary_button_style(), on_click=save),
            ],
        )
        page.dialog.open = True
        page.update()

    def confirm_delete(u):
        def do_delete(e):
            try:
                APIClient.delete(f"users/{u['id']}/")
                page.dialog.open = False
                page.update()
                load_users()
                show_snack(page, f"Usuario '{u.get('username')}' eliminado")
            except Exception as ex:
                show_snack(page, f"Error: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.icons.WARNING_ROUNDED, color=ft.colors.RED_400),
                          ft.Text("Eliminar Usuario", weight="bold")], spacing=10),
            content=ft.Text(f"¿Eliminar permanentemente al usuario '{u.get('username')}'?\nEsta acción no se puede deshacer.", size=14),
            actions=[
                ft.TextButton("No, cancelar",
                              on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Sí, eliminar", bgcolor=ft.colors.RED_700,
                                  color=ft.colors.WHITE, on_click=do_delete),
            ],
        )
        page.dialog.open = True
        page.update()

    threading.Timer(0.1, load_users).start()

    return ft.Column([
        ft.Row([
            ft.Text("Gestión de Personal", size=24, weight="bold", color=ThemeColors.TEXT_PRIMARY),
            ft.ElevatedButton("Nuevo Usuario", icon=ft.icons.PERSON_ADD_ROUNDED,
                              style=JetBrainsTheme.primary_button_style(),
                              on_click=open_create,
                              visible=can_access(rol, "user:create")),
        ], alignment="justify"),
        ft.Container(
            **JetBrainsTheme.card_style(),
            content=ft.Row([
                search_tf,
                ft.ElevatedButton("Buscar", icon=ft.icons.SEARCH,
                                  style=JetBrainsTheme.primary_button_style(),
                                  on_click=lambda e: load_users(), height=45),
                ft.IconButton(ft.icons.REFRESH_ROUNDED, tooltip="Actualizar",
                              on_click=lambda e: load_users()),
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
