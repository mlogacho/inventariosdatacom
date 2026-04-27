import flet as ft
from core.theme import ThemeColors, JetBrainsTheme
from components.status_badge import status_badge
from components.timeline import asset_timeline
from services.movement_service import get_asset_history
from core.api_client import APIClient

def item_traceability_view(page: ft.Page, navigate, item_id=None, item_data=None):
    if not item_id:
        return ft.Container(content=ft.Text("ID de ítem no proporcionado", color=ft.colors.RED))

    # Estado local
    state = {
        "item": item_data or {},
        "movements": [],
        "loading": True
    }

    # Contenedores de UI
    timeline_container = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    header_container = ft.Container()
    loading_indicator = ft.ProgressBar(visible=True, color=ThemeColors.ACCENT_BLUE)

    def load_data():
        try:
            # 1. Cargar datos del ítem si no vienen en item_data
            if not state["item"]:
                res_item = APIClient.get(f"inventory/items/{item_id}/")
                state["item"] = res_item
            
            # 2. Cargar historial
            history_res = get_asset_history(item_id)
            state["movements"] = history_res.get("results", [])
            
            # 3. Renderizar
            render_header()
            render_timeline()
        except Exception as e:
            timeline_container.controls = [ft.Text(f"Error al cargar datos: {e}", color=ft.colors.RED_400)]
        finally:
            loading_indicator.visible = False
            page.update()

    def render_header():
        item = state["item"]
        header_container.content = ft.Container(
            **JetBrainsTheme.card_style(),
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.icons.INVENTORY_ROUNDED, color=ThemeColors.ACCENT_BLUE, size=40),
                    padding=20, bgcolor=ft.colors.with_opacity(0.1, ThemeColors.ACCENT_BLUE),
                    border_radius=15
                ),
                ft.Column([
                    ft.Row([
                        ft.Text(item.get("nombre", "Cargando..."), size=24, weight="bold", color=ft.colors.WHITE),
                        status_badge(item.get("estado", "STOCK")),
                    ], spacing=15),
                    ft.Row([
                        ft.Text(f"CÓDIGO: {item.get('codigo','—')}", size=12, color=ThemeColors.TEXT_SECONDARY, weight="bold"),
                        ft.Text("•", color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(f"SERIAL: {item.get('serial','—')}", size=12, color=ThemeColors.TEXT_SECONDARY),
                        ft.Text("•", color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(f"TIPO: {item.get('tipo_item','').upper()}", size=12, color=ThemeColors.TEXT_SECONDARY),
                    ], spacing=10)
                ], expand=True),
                ft.ElevatedButton(
                    "Volver",
                    icon=ft.icons.ARROW_BACK,
                    on_click=lambda _: navigate("movements"),
                    style=JetBrainsTheme.secondary_button_style()
                )
            ], spacing=20)
        )

    def render_timeline():
        movements = state["movements"]
        timeline_entries = []
        
        for m in movements:
            prev = m.get("origen", {}).get("estado", "INICIO")
            curr = m.get("destino", {}).get("estado", "---")
            ot = m.get("ot_id")
            ot_str = f" [OT: {ot}]" if ot else ""
            
            timeline_entries.append({
                "date": m.get("fecha")[:16].replace("T", " "),
                "user": m.get("responsable", {}).get("username", "---"),
                "change": f"{prev} → {curr}{ot_str}",
                "notes": m.get("observaciones", "") or m.get("notes", "")
            })

        timeline_container.controls = [
            ft.Container(
                **JetBrainsTheme.card_style(),
                expand=True,
                padding=40,
                content=ft.Column([
                    ft.Text("HISTORIAL DE TRAZABILIDAD", size=18, weight="bold", color=ThemeColors.ACCENT_BLUE),
                    ft.Divider(height=30, color=ft.colors.with_opacity(0.1, ft.colors.WHITE)),
                    asset_timeline(timeline_entries)
                ], spacing=20)
            )
        ]

    # Ejecutar carga inicial
    import threading
    threading.Timer(0.1, load_data).start()

    return ft.Column([
        header_container,
        loading_indicator,
        timeline_container
    ], expand=True, spacing=20)
