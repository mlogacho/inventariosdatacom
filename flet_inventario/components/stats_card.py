import flet as ft
from core.theme import ThemeColors, JetBrainsTheme

def stats_card(title: str, value: str, icon, color: str = ThemeColors.ACCENT_BLUE):
    return ft.Container(
        **JetBrainsTheme.card_style(),
        width=260,
        height=140,
        content=ft.Column([
            ft.Row([
                ft.Icon(icon, color=color, size=24),
                ft.Text(title, color=ThemeColors.TEXT_SECONDARY, size=13, weight="w500"),
            ], spacing=10),
            ft.Container(height=5),
            ft.Text(value, color=ThemeColors.TEXT_PRIMARY, size=32, weight="bold"),
            ft.Text("Actualizado ahora", color=ft.colors.with_opacity(0.3, ThemeColors.TEXT_SECONDARY), size=10),
        ], spacing=5, alignment="center")
    )
