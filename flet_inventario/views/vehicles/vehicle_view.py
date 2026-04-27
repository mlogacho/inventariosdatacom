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


def vehicle_view(page: ft.Page, navigate):
    rol = (Session.user or {}).get("rol", "tecnico")

    search_tf = ft.TextField(
        label="Buscar por placa o marca",
        expand=True,
        on_submit=lambda e: load(),
        **JetBrainsTheme.input_style(),
    )

    loading  = ft.ProgressBar(visible=False, color=ThemeColors.ACCENT_BLUE)
    rows_col = ft.Column(spacing=0)

    COL = {"placa": 110, "marca": 170, "modelo": 200, "anio": 80}

    header_row = ft.Container(
        bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
        content=ft.Row([
            ft.Container(width=COL["placa"],  content=ft.Text("PLACA",  size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["marca"],  content=ft.Text("MARCA",  size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["modelo"], content=ft.Text("MODELO", size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
            ft.Container(width=COL["anio"],   content=ft.Text("AÑO",    size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY)),
        ], spacing=8),
    )

    def _make_row(v):
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.colors.with_opacity(0.05, ft.colors.WHITE))),
            ink=True,
            on_click=lambda e, obj=v: open_detail(obj),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        ft.colors.with_opacity(0.04, ft.colors.WHITE) if e.data == "true"
                        else ft.colors.TRANSPARENT) or page.update()
            ),
            content=ft.Row([
                ft.Container(width=COL["placa"], content=ft.Container(
                    content=ft.Text(v.get("placa", "—"), size=12, weight="bold", color=ft.colors.WHITE),
                    bgcolor=ThemeColors.ACCENT_BLUE,
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    border_radius=5,
                )),
                ft.Container(width=COL["marca"],  content=ft.Text(v.get("marca",  "—"), weight="bold", size=13, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=COL["modelo"], content=ft.Text(v.get("modelo", "—"), size=12, color=ThemeColors.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(width=COL["anio"],   content=ft.Text(str(v.get("anio", "—")), size=12)),
            ], spacing=8),
        )

    def load():
        loading.visible = True
        page.update()
        try:
            vehicles = APIClient.get("inventory/vehicles/") or []
            q = (search_tf.value or "").strip().lower()
            if q:
                vehicles = [v for v in vehicles
                            if q in v.get("placa", "").lower() or q in v.get("marca", "").lower()]
            rows_col.controls.clear()
            if not vehicles:
                rows_col.controls.append(ft.Container(
                    padding=ft.padding.all(30),
                    content=ft.Text("No hay vehículos registrados.", italic=True, color=ThemeColors.TEXT_SECONDARY),
                ))
            else:
                for v in vehicles:
                    rows_col.controls.append(_make_row(v))
        except Exception as ex:
            show_snack(page, f"Error al cargar vehículos: {ex}", True)
        loading.visible = False
        page.update()

    def open_detail(v):
        def info(label, value, icon):
            return ft.Row([
                ft.Icon(icon, size=14, color=ThemeColors.ACCENT_BLUE),
                ft.Text(label, size=11, weight="bold", color=ThemeColors.TEXT_SECONDARY, width=70),
                ft.Text(str(value) if value else "—", size=13),
            ], spacing=8)

        def close_then(fn):
            def _h(_e):
                page.dialog.open = False
                page.update()
                fn()
            return _h

        btns = [ft.TextButton("Cerrar", on_click=lambda e: setattr(page.dialog, "open", False) or page.update())]
        if can_access(rol, "vehicle:update"):
            btns.insert(0, ft.ElevatedButton("Editar", icon=ft.icons.EDIT_ROUNDED,
                                              style=JetBrainsTheme.primary_button_style(),
                                              on_click=close_then(lambda: open_form(v))))
        if can_access(rol, "vehicle:delete"):
            idx = 1 if can_access(rol, "vehicle:update") else 0
            btns.insert(idx, ft.ElevatedButton("Retirar", icon=ft.icons.DELETE_ROUNDED,
                                               bgcolor=ft.colors.RED_700, color=ft.colors.WHITE,
                                               on_click=close_then(lambda: confirm_delete(v))))

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.DIRECTIONS_CAR_ROUNDED, color=ThemeColors.ACCENT_BLUE, size=26),
                ft.Column([
                    ft.Text(v.get("placa", "—"), weight="bold", size=16),
                    ft.Text(f"{v.get('marca','')} {v.get('modelo','')}".strip(),
                            size=11, color=ThemeColors.TEXT_SECONDARY),
                ], spacing=1, tight=True),
            ], spacing=12),
            content=ft.Container(width=360, content=ft.Column([
                info("Marca",  v.get("marca"),  ft.icons.DIRECTIONS_CAR),
                info("Modelo", v.get("modelo"), ft.icons.SETTINGS),
                info("Año",    v.get("anio"),   ft.icons.CALENDAR_TODAY),
            ], tight=True, spacing=12)),
            actions=btns,
        )
        page.dialog.open = True
        page.update()

    def open_form(veh=None):
        is_edit  = veh is not None
        placa_tf = ft.TextField(label="Placa *",
                                value=veh.get("placa", "") if is_edit else "",
                                disabled=is_edit, **JetBrainsTheme.input_style())
        marca_tf  = ft.TextField(label="Marca",  value=veh.get("marca",  "") if is_edit else "", **JetBrainsTheme.input_style())
        modelo_tf = ft.TextField(label="Modelo", value=veh.get("modelo", "") if is_edit else "", **JetBrainsTheme.input_style())
        anio_tf   = ft.TextField(label="Año",    value=str(veh.get("anio", "")) if is_edit else "",
                                 keyboard_type=ft.KeyboardType.NUMBER, **JetBrainsTheme.input_style())

        def save(e):
            if not placa_tf.value.strip():
                show_snack(page, "La placa es obligatoria", True)
                return
            payload = {
                "placa":  placa_tf.value.strip().upper(),
                "marca":  marca_tf.value.strip(),
                "modelo": modelo_tf.value.strip(),
                "anio":   int(anio_tf.value) if anio_tf.value and anio_tf.value.isdigit() else None,
            }
            try:
                if is_edit:
                    APIClient.put(f"inventory/vehicles/{veh['id']}/", json=payload)
                    show_snack(page, f"Vehículo {veh.get('placa')} actualizado")
                else:
                    APIClient.post("inventory/vehicles/", json=payload)
                    show_snack(page, f"Vehículo {payload['placa']} registrado")
                page.dialog.open = False
                page.update()
                load()
            except Exception as ex:
                show_snack(page, f"Error: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.DIRECTIONS_CAR_ROUNDED, color=ThemeColors.ACCENT_BLUE),
                ft.Text("Editar Vehículo" if is_edit else "Nuevo Vehículo", weight="bold"),
            ], spacing=10),
            content=ft.Container(width=420,
                                  content=ft.Column([placa_tf, marca_tf, modelo_tf, anio_tf], tight=True, spacing=15)),
            actions=[
                ft.TextButton("Cancelar",
                              on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Guardar", style=JetBrainsTheme.primary_button_style(), on_click=save),
            ],
        )
        page.dialog.open = True
        page.update()

    def confirm_delete(veh):
        def do_delete(e):
            try:
                APIClient.delete(f"inventory/vehicles/{veh['id']}/")
                page.dialog.open = False
                page.update()
                load()
                show_snack(page, f"Vehículo {veh.get('placa')} retirado de la flota")
            except Exception as ex:
                show_snack(page, f"Error: {ex}", True)

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.icons.WARNING_ROUNDED, color=ft.colors.RED_400),
                          ft.Text("Retirar Vehículo", weight="bold")], spacing=10),
            content=ft.Text(f"¿Dar de baja al vehículo '{veh.get('placa')}'?\nYa no estará disponible para instalaciones.", size=14),
            actions=[
                ft.TextButton("No, cancelar",
                              on_click=lambda e: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Sí, retirar", bgcolor=ft.colors.RED_700,
                                  color=ft.colors.WHITE, on_click=do_delete),
            ],
        )
        page.dialog.open = True
        page.update()

    threading.Timer(0.1, load).start()

    return ft.Column([
        ft.Row([
            ft.Text("Flota de Vehículos", size=24, weight="bold", color=ThemeColors.TEXT_PRIMARY),
            ft.ElevatedButton("Nuevo Vehículo", icon=ft.icons.DIRECTIONS_CAR_FILLED_ROUNDED,
                              style=JetBrainsTheme.primary_button_style(),
                              on_click=lambda e: open_form(),
                              visible=can_access(rol, "vehicle:create")),
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
