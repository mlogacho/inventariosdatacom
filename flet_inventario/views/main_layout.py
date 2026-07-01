import flet as ft
from core.theme import ThemeColors, JetBrainsTheme
from core.session import Session

class MainLayout(ft.Container):
    def __init__(self, page: ft.Page, content: ft.Control, title: str, navigate_callback, nav_key: str = "dashboard"):
        super().__init__()
        self.page = page
        self.main_content = content
        self.nav_title = title
        self.nav_key = nav_key
        self.navigate = navigate_callback

        self.title_text = ft.Text(self.nav_title, size=20, weight="bold", color=ThemeColors.TEXT_PRIMARY)
        self.breadcrumb_text = ft.Text(self.nav_title, size=11, color=ThemeColors.ACCENT_BLUE)
        self.main_content_container = ft.Container(
            content=self.main_content,
            expand=True,
            padding=ft.padding.only(left=30, right=30, bottom=30, top=10),
        )
        
        self.expand = True
        self.bgcolor = ThemeColors.BG_DEEP
        
        # Elementos de la UI
        self.sidebar = self._build_sidebar()
        self.header = self._build_header()
        self.root_row = ft.Row([
            self.sidebar,
            ft.Container(width=1, bgcolor=ft.colors.with_opacity(0.1, ft.colors.WHITE)),
            ft.Column([
                self.header,
                self.main_content_container,
            ], expand=True, spacing=0)
        ], expand=True, spacing=0)
        
        # Layout principal
        self.content = ft.Stack(
            controls=[
                # Background Blobs (Abstract Decor)
                self._build_background_blobs(),

                # Application Layer
                self.root_row,
            ],
            expand=True,
        )

    def set_view(self, title: str, content: ft.Control, nav_key: str):
        self.nav_title = title
        self.nav_key = nav_key
        self.main_content = content

        self.title_text.value = title
        self.breadcrumb_text.value = title
        self.main_content_container.content = content

        self.sidebar = self._build_sidebar()
        self.root_row.controls[0] = self.sidebar

    def _build_background_blobs(self):
        return ft.Stack([
            ft.Container(
                width=400, height=400, border_radius=200,
                bgcolor=ft.colors.with_opacity(0.15, ThemeColors.ACCENT_BLUE),
                blur=ft.Blur(100, 100),
                left=-100, top=-100,
            ),
            ft.Container(
                width=300, height=300, border_radius=150,
                bgcolor=ft.colors.with_opacity(0.1, ThemeColors.ACCENT_MAGENTA),
                blur=ft.Blur(120, 120),
                right=-50, bottom=100,
            ),
        ])

    def _build_header(self):
        user = Session.user.get("username", "Usuario") if Session.user else "Usuario"
        role = Session.user.get("rol", "técnico").upper() if Session.user else "GUEST"
        
        return ft.Container(
            height=70,
            padding=ft.padding.symmetric(horizontal=30),
            # bgcolor=ft.colors.with_opacity(0.3, ThemeColors.BG_SURFACE_NAV),
            content=ft.Row([
                ft.Column([
                    self.title_text,
                    ft.Row([
                        ft.Text("Inventario", size=11, color=ThemeColors.TEXT_SECONDARY),
                        ft.Icon(ft.icons.CHEVRON_RIGHT, size=14, color=ThemeColors.TEXT_SECONDARY),
                        self.breadcrumb_text,
                    ], spacing=5)
                ], spacing=2, alignment="center"),
                
                ft.Row([
                    ft.Column([
                        ft.Text(user, size=14, weight="w600", color=ThemeColors.TEXT_PRIMARY),
                        ft.Text(role, size=10, color=ThemeColors.TEXT_SECONDARY, weight="bold"),
                    ], horizontal_alignment="end", spacing=0),
                    ft.Container(
                        width=40, height=40, border_radius=20,
                        bgcolor=ThemeColors.ACCENT_BLUE,
                        alignment=ft.alignment.center,
                        content=ft.Text(user[0].upper(), color=ft.colors.WHITE, weight="bold")
                    )
                ], spacing=15)
            ], alignment="justify")
        )

    def _build_sidebar(self):
        from core.permissions import can_access
        rol = Session.user.get("rol", "tecnico") if Session.user else "tecnico"

        # (Label, Icon, Key, Required Permission)
        menu_items = [
            ("Dashboard",       ft.icons.DASHBOARD,            "dashboard",  None),
            ("Ítems (Activos)", ft.icons.INVENTORY_2,          "items",      "item:read"),
            ("Movimientos",     ft.icons.SYNC_ALT,             "movements",  "movement:read"),
            ("Bodegas",         ft.icons.WAREHOUSE,            "stores",     "store:read"),
        ]

        # ── Logo / Marca ──────────────────────────────────────────────────────
        sidebar_controls = [
            ft.Container(
                padding=ft.padding.only(left=20, right=20, top=28, bottom=20),
                content=ft.Row([
                    ft.Container(
                        width=8, height=30,
                        bgcolor=ThemeColors.ACCENT_BLUE,
                        border_radius=4,
                    ),
                    ft.Column([
                        ft.Text("INVENTARIO", size=16, weight="black",
                                color=ThemeColors.TEXT_PRIMARY),
                        ft.Text("Sistema de Control", size=9,
                                color=ThemeColors.TEXT_SECONDARY),
                    ], spacing=0),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ),
            ft.Container(
                height=1,
                bgcolor=ft.colors.with_opacity(0.08, ft.colors.WHITE),
                margin=ft.padding.symmetric(horizontal=16),
            ),
            ft.Container(height=8),
        ]

        for name, icon, key, perm in menu_items:
            if perm and not can_access(rol, perm):
                continue

            is_active = key == self.nav_key

            icon_color = ThemeColors.ACCENT_BLUE if is_active else ThemeColors.TEXT_SECONDARY
            text_color = ThemeColors.TEXT_PRIMARY if is_active else ThemeColors.TEXT_SECONDARY

            sidebar_controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                    margin=ft.padding.symmetric(horizontal=10, vertical=1),
                    border_radius=10,
                    bgcolor=(ft.colors.with_opacity(0.12, ThemeColors.ACCENT_BLUE)
                             if is_active else ft.colors.TRANSPARENT),
                    border=(ft.border.all(1, ft.colors.with_opacity(0.2, ThemeColors.ACCENT_BLUE))
                            if is_active else None),
                    ink=True,
                    on_click=lambda e, k=key: self.navigate_by_key(k),
                    content=ft.Row([
                        # Contenedor de icono con fondo sutil
                        ft.Container(
                            width=34, height=34,
                            border_radius=9,
                            bgcolor=(ft.colors.with_opacity(0.18, ThemeColors.ACCENT_BLUE)
                                     if is_active
                                     else ft.colors.with_opacity(0.06, ft.colors.WHITE)),
                            alignment=ft.alignment.center,
                            content=ft.Icon(icon, color=icon_color, size=18),
                        ),
                        ft.Text(name, color=text_color, size=13,
                                weight="w600" if is_active else "normal",
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                )
            )

        sidebar_controls.append(ft.Container(expand=True))

        # ── Cerrar Sesión ─────────────────────────────────────────────────────
        sidebar_controls.append(
            ft.Container(
                height=1,
                bgcolor=ft.colors.with_opacity(0.08, ft.colors.WHITE),
                margin=ft.padding.symmetric(horizontal=16),
            )
        )
        sidebar_controls.append(
            ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                margin=ft.padding.only(left=10, right=10, top=6, bottom=24),
                border_radius=10,
                ink=True,
                on_click=lambda e: self.navigate("logout"),
                content=ft.Row([
                    ft.Container(
                        width=34, height=34, border_radius=9,
                        bgcolor=ft.colors.with_opacity(0.12, ft.colors.RED_400),
                        alignment=ft.alignment.center,
                        content=ft.Icon(ft.icons.LOGOUT,
                                        color=ft.colors.RED_400, size=18),
                    ),
                    ft.Text("Cerrar Sesión", color=ft.colors.RED_400, size=13),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            )
        )

        return ft.Container(
            width=220,
            bgcolor=ThemeColors.BG_SURFACE_NAV,
            content=ft.Column(sidebar_controls, spacing=0, expand=True),
        )

    def navigate_by_key(self, key):
        # Mapeo de llaves a funciones de navegación (esto se manejará en menu_view)
        # Por ahora pasamos la llave al callback de navegación superior
        self.navigate(key)
