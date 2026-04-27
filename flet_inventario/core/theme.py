import flet as ft

class ThemeColors:
    # JetBrains / IntelliJ IDEA Style Palette
    BG_DEEP = "#0d0d0d"
    BG_SURFACE = "#1a1f3a"         # Semi-transparent blue-dark
    BG_CARD = BG_SURFACE           # Alias para compatibilidad
    BG_SURFACE_NAV = "#13131a"     # Sidebar dark grey
    
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#a0a0b0"
    
    # Accents
    ACCENT_BLUE = "#007fff"        # Electric blue
    ACCENT = ACCENT_BLUE           # Alias para compatibilidad
    ACCENT_VIOLET = "#8a2be2"
    ACCENT_MAGENTA = "#ff00ff"
    ACCENT_CORAL = "#ff7f50"
    
    # State Badges (JetBrains request)
    STATE_STOCK = "#007fff"        # Electric blue
    STATE_RESERVED = "#ffbf00"     # Amber/Gold
    STATE_DISPATCH = "#ff4500"     # Vibrant Orange
    STATE_INSTALLED = "#39ff14"    # Neon Green
    STATE_RETURN = "#00ffff"       # Cyan
    STATE_PROVIDER = "#ff2400"     # Scarlet/Coral
    STATE_OBSOLETE = "#808080"     # Medium Grey
    STATE_FIELD = "#006400"        # Dark Green

    # Card / Border opacity
    BORDER_OPACITY = 0.15
    SURFACE_OPACITY = 0.85

class JetBrainsTheme:
    @staticmethod
    def card_style():
        return {
            "padding": 20,
            "border_radius": 16,
            "bgcolor": ft.colors.with_opacity(0.1, ft.colors.WHITE),
            "border": ft.border.all(1, ft.colors.with_opacity(ThemeColors.BORDER_OPACITY, ft.colors.WHITE)),
        }

    @staticmethod
    def input_style():
        return {
            "border_color": ft.colors.with_opacity(0.2, ft.colors.WHITE),
            "focused_border_color": ThemeColors.ACCENT_BLUE,
            "bgcolor": ft.colors.with_opacity(0.05, ft.colors.BLACK),
            "label_style": ft.TextStyle(color=ThemeColors.TEXT_SECONDARY),
            "color": ThemeColors.TEXT_PRIMARY,
            "border_radius": 8,
        }

    @staticmethod
    def primary_button_style():
        return ft.ButtonStyle(
            color=ThemeColors.TEXT_PRIMARY,
            bgcolor={
                ft.MaterialState.DEFAULT: ThemeColors.ACCENT_BLUE,
                ft.MaterialState.HOVERED: ThemeColors.ACCENT_VIOLET,
            },
            shape=ft.RoundedRectangleBorder(radius=8),
        )

    @staticmethod
    def secondary_button_style():
        return ft.ButtonStyle(
            color=ThemeColors.TEXT_PRIMARY,
            bgcolor=ft.colors.TRANSPARENT,
            side=ft.BorderSide(1, ft.colors.with_opacity(0.3, ft.colors.WHITE)),
            shape=ft.RoundedRectangleBorder(radius=8),
        )
