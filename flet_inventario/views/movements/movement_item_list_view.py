import flet as ft
from services.item_service import list_items


def movement_item_list_view(page, go_menu):
    nombre_tf = ft.TextField(label="Nombre", width=240)
    categoria_tf = ft.TextField(label="Categoría", width=220)
    subcategoria_tf = ft.TextField(label="Subcategoría", width=220)

    table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Código")),
            ft.DataColumn(ft.Text("Nombre")),
            ft.DataColumn(ft.Text("Categoría")),
            ft.DataColumn(ft.Text("Subcategoría")),
        ],
        rows=[],
        expand=True,
    )

    def load_items():
        try:
            items = list_items({})
            table.rows.clear()

            for item in items:
                if nombre_tf.value and nombre_tf.value.lower() not in item.get("nombre", "").lower():
                    continue

                categoria = item.get("categoria", {})
                cat_name = categoria.get("nombre") if isinstance(categoria, dict) else str(categoria)
                if categoria_tf.value and categoria_tf.value.lower() not in cat_name.lower():
                    continue

                sub = item.get("subcategoria", {})
                sub_name = sub.get("nombre") if isinstance(sub, dict) else str(sub)
                if subcategoria_tf.value and subcategoria_tf.value.lower() not in sub_name.lower():
                    continue

                table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(item.get("codigo", "—"))),
                            ft.DataCell(ft.Text(item.get("nombre", "—"))),
                            ft.DataCell(ft.Text(cat_name)),
                            ft.DataCell(ft.Text(sub_name)),
                        ],
                        on_select_changed=lambda e, it=item: open_item(it),
                    )
                )

            page.update()

        except Exception as e:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"Error cargando items: {e}"),
                bgcolor=ft.colors.RED_400,
            )
            page.snack_bar.open = True
            page.update()

    def open_item(item):
        from views.movements.movement_detail_view import movement_detail_view
        go_menu(movement_detail_view(page, item, go_menu))

    load_items()

    return ft.Column(
        [
            ft.Text("Seleccionar item para auditoría", size=22, weight="bold"),

            ft.Container(
                padding=15,
                border_radius=10,
                bgcolor=ft.colors.with_opacity(0.04, ft.colors.WHITE),
                content=ft.Row(
                    [
                        nombre_tf,
                        categoria_tf,
                        subcategoria_tf,
                        ft.ElevatedButton("🔍 Filtrar", on_click=lambda e: load_items()),
                    ],
                    spacing=15,
                ),
            ),

            table,

            ft.ElevatedButton("⬅ Volver al menú", on_click=lambda e: go_menu()),
        ],
        expand=True,
        spacing=20,
    )
