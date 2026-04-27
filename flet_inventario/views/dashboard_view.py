import flet as ft
from core.theme import ThemeColors, JetBrainsTheme
from components.stats_card import stats_card
from services.movement_service import get_movement_stats
from components.status_badge import status_badge

def dashboard_view(page: ft.Page, navigate):
    # =========================
    # ESTADO Y VARIABLES
    # =========================
    def get_stats():
        try:
            return get_movement_stats()
        except:
            return {"total_items": 0, "movements_today": 0, "stats_by_state": {}}

    stats = get_stats()
    
    # =========================
    # COMPONENTES
    # =========================
    title = ft.Row([
        ft.Container(width=10, height=30, bgcolor=ThemeColors.ACCENT_BLUE, border_radius=5),
        ft.Text("Dashboard de Control", size=28, weight="black", color=ThemeColors.TEXT_PRIMARY),
    ], spacing=15)

    cards = ft.ResponsiveRow([
        ft.Column([stats_card("Activos Totales", str(stats.get("total_items", 0)), ft.icons.INVENTORY)], col={"sm": 6, "md": 3}),
        ft.Column([stats_card("En Stock", str(stats.get("stats_by_state", {}).get("STOCK", 0)), ft.icons.WAREHOUSE)], col={"sm": 6, "md": 3}),
        ft.Column([stats_card("Reservados", str(stats.get("stats_by_state", {}).get("RESERVADO", 0)), ft.icons.VPN_KEY)], col={"sm": 6, "md": 3}),
        ft.Column([stats_card("Movimientos", str(stats.get("movements_today", 0)), ft.icons.SYNC)], col={"sm": 6, "md": 3}),
    ], spacing=20)

    # Status Breakdown Card
    breakdown_items = []
    for state, count in stats.get("stats_by_state", {}).items():
        if count > 0:
            breakdown_items.append(
                ft.Row([
                    status_badge(state),
                    ft.Text(f"{count} unidades", size=14, weight="w500", color=ThemeColors.TEXT_PRIMARY)
                ], alignment="justify")
            )

    breakdown_card = ft.Container(
        **JetBrainsTheme.card_style(),
        width=400,
        content=ft.Column([
            ft.Text("Distribución de Inventario", size=18, weight="bold"),
            ft.Divider(height=10, color=ft.colors.with_opacity(0.1, ft.colors.WHITE)),
            ft.Column(breakdown_items if breakdown_items else [ft.Text("No hay datos disponibles", color=ThemeColors.TEXT_SECONDARY)], spacing=10)
        ], spacing=15)
    )

    welcome_banner = ft.Container(
        **JetBrainsTheme.card_style(),
        expand=True,
        content=ft.Column([
            ft.Text("Consola de Operaciones v2.0", size=20, weight="black", color=ThemeColors.ACCENT_BLUE),
            ft.Text("El núcleo central de logística e inventario está operativo.", size=16),
            ft.Text("Usa el menú lateral para navegar entre los módulos. Todas las transacciones están siendo auditadas bajo estándares ISO 27001.", 
                   color=ThemeColors.TEXT_SECONDARY, size=13),
            ft.Container(height=20),
            ft.Row([
                ft.ElevatedButton("Explorar Activos", style=JetBrainsTheme.primary_button_style(), on_click=lambda e: navigate("items")),
                ft.TextButton("Historial Completo", style=JetBrainsTheme.secondary_button_style(), on_click=lambda e: navigate("movements")),
            ], spacing=20)
        ], spacing=10)
    )

    return ft.Column([
        title,
        ft.Container(height=10),
        cards,
        ft.Container(height=20),
        ft.Row([
            welcome_banner,
            breakdown_card
        ], spacing=20, alignment="start", vertical_alignment="start"),
    ], expand=True, spacing=15, scroll="auto")
