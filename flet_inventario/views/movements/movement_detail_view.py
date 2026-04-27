import flet as ft
from services.movement_service import list_movements
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

    load_movements()

    return ft.Column(
        [
            ft.Text("Auditoría del item", size=22, weight="bold"),
            ft.Text(f'{item.get("codigo","")} - {item.get("nombre","")}', italic=True),

            table,

            ft.Row(
                [
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
