import flet as ft
from core.theme import ThemeColors

def timeline_entry(date: str, user: str, change: str, notes: str = ""):
    return ft.Container(
        padding=ft.padding.only(left=20, bottom=20),
        border=ft.border.Border(left=ft.BorderSide(2, ft.colors.with_opacity(0.1, ThemeColors.ACCENT_BLUE))),
        content=ft.Column([
            ft.Row([
                ft.Container(
                    width=12, height=12, border_radius=6,
                    bgcolor=ThemeColors.ACCENT_BLUE,
                    margin=ft.margin.only(left=-27)
                ),
                ft.Text(date, size=12, color=ThemeColors.TEXT_SECONDARY, weight="bold"),
                ft.Text(" • ", color=ThemeColors.TEXT_SECONDARY),
                ft.Text(user, size=12, color=ThemeColors.ACCENT_BLUE, weight="w500"),
            ]),
            ft.Text(change, size=14, color=ThemeColors.TEXT_PRIMARY, weight="bold"),
            ft.Text(notes if notes else "Sin observaciones", 
                   size=12, color=ThemeColors.TEXT_SECONDARY, 
                   italic=True if not notes else False),
        ], spacing=5)
    )

def asset_timeline(entries: list):
    """entries should be a list of dicts with keys: date, user, change, notes"""
    if not entries:
        return ft.Container(
            content=ft.Text("No hay historial disponible", color=ThemeColors.TEXT_SECONDARY, italic=True),
            padding=20
        )
        
    return ft.Column(
        controls=[timeline_entry(**entry) for entry in entries],
        spacing=0
    )
