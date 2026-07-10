import flet as ft
from services.movement_service import list_movements
from services.movement_service import download_acta_entrega_recepcion
from services.user_service import list_crm_users
from core.session import Session
import threading
import webbrowser


def load_item_list(page, go_menu):
    from views.movements.movement_item_list_view import movement_item_list_view
    go_menu(movement_item_list_view(page, go_menu))

def movement_detail_view(page, item, go_menu):
    table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Tipo")),
            ft.DataColumn(ft.Text("E. Anterior")),
            ft.DataColumn(ft.Text("E. Nuevo")),
            ft.DataColumn(ft.Text("OT")),
            ft.DataColumn(ft.Text("Notas")),
            ft.DataColumn(ft.Text("Responsable")),
            ft.DataColumn(ft.Text("Fecha")),
        ],
        rows=[],
        expand=True,
    )

    def load_movements():
        try:
            movements = list_movements({"item_id": item["id"]})
            table.rows.clear()

            for m in movements:
                ant = m.get("estado_anterior", {}).get("estado", "—")
                new = m.get("estado_nuevo", {}).get("estado", "—")
                
                table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(m.get("tipo_movimiento", "—"))),
                            ft.DataCell(ft.Text(str(ant))),
                            ft.DataCell(ft.Text(str(new))),
                            ft.DataCell(ft.Text(m.get("ot_id", "—"))),
                            ft.DataCell(ft.Text(m.get("notes", "—"))),
                            ft.DataCell(
                                ft.Text(
                                    m.get("responsable", {}).get("username", "—")
                                    if isinstance(m.get("responsable"), dict)
                                    else str(m.get("responsable", "—"))
                                )
                            ),
                            ft.DataCell(ft.Text(m.get("fecha", "—"))),
                        ]
                    )
                )

            page.update()

        except Exception as e:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"Error cargando movimientos: {e}"),
                bgcolor=ft.colors.RED_400,
            )
            page.snack_bar.open = True
            page.update()

    def show_snack(msg: str, is_error: bool = False):
        page.snack_bar = ft.SnackBar(
            ft.Text(msg),
            bgcolor=ft.colors.RED_400 if is_error else ft.colors.GREEN_700,
        )
        page.snack_bar.open = True
        page.update()

    def open_acta_dialog(_):
        try:
            users = list_crm_users() or []
        except Exception as ex:
            show_snack(f"No se pudo cargar usuarios CRM: {ex}", True)
            return

        current_username = ""
        if Session.user and isinstance(Session.user, dict):
            current_username = str(Session.user.get("username") or "").strip()

        options = []
        for u in users:
            uid = str(u.get("id") or "").strip()
            username = str(u.get("username") or "").strip()
            if not uid or username == current_username:
                continue
            full_name = (u.get("full_name") or username).strip()
            role_name = (u.get("role_name") or "Cargo no registrado").strip()
            options.append((uid, f"{full_name} | {role_name}"))

        if not options:
            show_snack("No hay usuarios CRM disponibles para 'Recibe'.", True)
            return

        recibe_dd = ft.Dropdown(
            label="Recibe (CRM)",
            width=430,
            value=options[0][0],
            options=[ft.dropdown.Option(key=k, text=t) for k, t in options],
        )
        obs_tf = ft.TextField(label="Observacion", multiline=True, min_lines=3, max_lines=4, width=430)

        def do_generate(__):
            payload = {
                "recibe_user_id": str(recibe_dd.value or "").strip(),
                "observacion": (obs_tf.value or "").strip(),
                "item_id": item.get("id"),
                "item_ids": [item.get("id")],
            }

            if not payload["recibe_user_id"]:
                show_snack("Selecciona el usuario que recibe.", True)
                return

            page.dialog.open = False
            page.update()

            def _worker():
                try:
                    show_snack("Generando ACTA...")
                    pdf_path = download_acta_entrega_recepcion(payload)
                    webbrowser.open(f"file://{pdf_path}")
                    show_snack("ACTA generada correctamente")
                except Exception as ex:
                    show_snack(f"Error generando ACTA: {ex}", True)

            threading.Thread(target=_worker, daemon=True).start()

        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Generar ACTA DE ENTREGA - RECEPCION"),
            content=ft.Column([recibe_dd, obs_tf], tight=True),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda __: setattr(page.dialog, "open", False) or page.update()),
                ft.ElevatedButton("Generar PDF", on_click=do_generate),
            ],
        )
        page.dialog.open = True
        page.update()

    load_movements()

    return ft.Column(
        [
            ft.Text("Auditoría del item", size=22, weight="bold"),
            ft.Text(f'{item.get("codigo","")} - {item.get("nombre","")}', italic=True),

            table,

            ft.Row(
                [
                    ft.ElevatedButton(
                        "ACTA ENTREGA-RECEPCION",
                        icon=ft.icons.PICTURE_AS_PDF,
                        on_click=open_acta_dialog,
                    ),
                    ft.ElevatedButton(
                        "⬅ Volver a items",
                        on_click=lambda e: (
                            load_item_list(page, go_menu),
                        ),
                    ),
                    ft.ElevatedButton(
                        "🏠 Menú principal",
                        on_click=lambda e: go_menu(),
                    ),
                ],
                spacing=15,
            ),
        ],
        expand=True,
        spacing=20,
    )
