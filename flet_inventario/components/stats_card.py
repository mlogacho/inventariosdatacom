import flet as ft
from core.theme import ThemeColors, JetBrainsTheme

# Proporción Áurea φ ≈ 1.618
PHI = 1.618

def stats_card(
    title: str,
    value: str,
    icon,
    color: str = ThemeColors.ACCENT_BLUE,
    on_click=None,
):
    """
    Tarjeta de estadísticas con proporciones áureas.
    Ancho base: 260px  →  Alto: 260 / PHI ≈ 161px
    Compatible con Flet 0.19.
    """
    card_width  = 260
    card_height = int(card_width / PHI)   # ≈ 161

    return ft.Container(
        width=card_width,
        height=card_height,
        border_radius=16,
        bgcolor=ft.colors.with_opacity(0.08, ft.colors.WHITE),
        border=ft.border.all(1, ft.colors.with_opacity(0.12, ft.colors.WHITE)),
        padding=ft.padding.only(left=18, right=16, top=14, bottom=14),
        ink=on_click is not None,
        on_click=on_click,
        content=ft.Column([
            ft.Row([
                ft.Container(
                    width=38,
                    height=38,
                    border_radius=10,
                    bgcolor=ft.colors.with_opacity(0.18, color),
                    alignment=ft.alignment.center,
                    content=ft.Icon(icon, color=color, size=20),
                ),
                ft.Container(width=10),
                ft.Text(
                    title,
                    color=ThemeColors.TEXT_SECONDARY,
                    size=12,
                    weight="w500",
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ], spacing=0),
            ft.Container(height=8),
            ft.Text(
                value,
                color=ThemeColors.TEXT_PRIMARY,
                size=34,
                weight="bold",
            ),
            ft.Text(
                "Actualizado ahora",
                color=ft.colors.with_opacity(0.35, ThemeColors.TEXT_SECONDARY),
                size=10,
            ),
        ], spacing=0),
    )
