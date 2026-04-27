import flet as ft
from core.theme import ThemeColors, JetBrainsTheme
from core.session import Session

class MainLayout(ft.Container):
    def __init__(self, page: ft.Page, content: ft.Control, title: str, navigate_callback):
        super().__init__()
        self.page = page
        self.main_content = content
        self.nav_title = title
        self.navigate = navigate_callback
        
        self.expand = True
        self.bgcolor = ThemeColors.BG_DEEP
        
        # Elementos de la UI
        self.sidebar = self._build_sidebar()
        self.header = self._build_header()
        
        # Layout principal
        self.content = ft.Stack(
            controls=[
                # Background Blobs (Abstract Decor)
                self._build_background_blobs(),

                # Application Layer
                ft.Row([
                    self.sidebar,
                    ft.Container(width=1, bgcolor=ft.colors.with_opacity(0.1, ft.colors.WHITE)),
                    ft.Column([
                        self.header,
                        ft.Container(
                            content=self.main_content,
                            expand=True,
                            padding=ft.padding.only(left=30, right=30, bottom=30, top=10),
                        )
                    ], expand=True, spacing=0)
                ], expand=True, spacing=0)
            ],
            expand=True,
        )

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
                    ft.Text(self.nav_title, size=20, weight="bold", color=ThemeColors.TEXT_PRIMARY),
                    ft.Row([
                        ft.Text("Inventario", size=11, color=ThemeColors.TEXT_SECONDARY),
                        ft.Icon(ft.icons.CHEVRON_RIGHT, size=14, color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(self.nav_title, size=11, color=ThemeColors.ACCENT_BLUE),
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
            ("Dashboard", ft.icons.DASHBOARD, "dashboard", None),
            ("Instalaciones", ft.icons.BUILD, "facilities", "facility:read"),
            ("Ítems (Activos)", ft.icons.INVENTORY_2, "items", "item:read"),
            ("Movimientos", ft.icons.SYNC_ALT, "movements", "movement:read"),
            ("Clientes", ft.icons.PEOPLE, "customers", "customer:read"),
            ("Proveedores", ft.icons.LOCAL_SHIPPING, "suppliers", "supplier:read"),
            ("Vehículos", ft.icons.DIRECTIONS_CAR, "vehicles", "vehicle:read"),
            ("Bodegas", ft.icons.WAREHOUSE, "stores", "store:read"),
            ("Usuarios", ft.icons.ADMIN_PANEL_SETTINGS, "users", "user:read"),
        ]
        
        sidebar_controls = [
            ft.Container(
                padding=ft.padding.all(30),
                content=ft.Row([
                    ft.Container(width=10, height=25, bgcolor=ThemeColors.ACCENT_BLUE, border_radius=5),
                    ft.Text("INVENTARIO", size=18, weight="black", color=ThemeColors.TEXT_PRIMARY),
                ], spacing=10)
            )
        ]
        
        for name, icon, key, perm in menu_items:
            # Validar permisos
            if perm and not can_access(rol, perm):
                continue

            # Seleccionar el ítem activo comparando títulos
            is_active = name in self.nav_title or (self.nav_title == "Menú Principal" and key == "dashboard")
            
            sidebar_controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    margin=ft.padding.symmetric(horizontal=15),
                    border_radius=10,
                    bgcolor=ft.colors.with_opacity(0.1, ThemeColors.ACCENT_BLUE) if is_active else ft.colors.TRANSPARENT,
                    ink=True,
                    on_click=lambda e, k=key: self.navigate_by_key(k),
                    content=ft.Row([
                        ft.Icon(icon, color=ThemeColors.ACCENT_BLUE if is_active else ThemeColors.TEXT_SECONDARY, size=20),
                        ft.Text(name, color=ThemeColors.TEXT_PRIMARY if is_active else ThemeColors.TEXT_SECONDARY, 
                               size=14, weight="w500" if is_active else "normal")
                    ], spacing=15)
                )
            )
            
        sidebar_controls.append(ft.Container(expand=True))
        
        # Logout
        sidebar_controls.append(
            ft.Container(
                padding=ft.padding.symmetric(horizontal=20, vertical=12),
                margin=ft.padding.only(left=15, right=15, bottom=30),
                border_radius=10,
                on_click=lambda e: self.navigate("logout"),
                content=ft.Row([
                    ft.Icon(ft.icons.LOGOUT, color=ft.colors.RED_400, size=20),
                    ft.Text("Cerrar Sesión", color=ft.colors.RED_400, size=14)
                ], spacing=15)
            )
        )
        
        return ft.Container(
            width=200,
            bgcolor=ThemeColors.BG_SURFACE_NAV,
            content=ft.Column(sidebar_controls, spacing=5)
        )

    def navigate_by_key(self, key):
        # Mapeo de llaves a funciones de navegación (esto se manejará en menu_view)
        # Por ahora pasamos la llave al callback de navegación superior
        self.navigate(key)
