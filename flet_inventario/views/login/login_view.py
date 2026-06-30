import flet as ft
from urllib.parse import parse_qs

from services.auth_service import login, login_with_sso_token
from core.session import Session
from core.theme import ThemeColors, JetBrainsTheme
from views.menu_view import menu_view

def login_view(page: ft.Page):
    # =========================
    # CONFIGURACIÓN GLOBAL
    # =========================
    page.title = "Sistema de Inventario"
    page.bgcolor = ThemeColors.BG_DEEP
    page.window_width = 1000
    page.window_height = 700
    page.window_resizable = False
    page.horizontal_alignment = "center"
    page.vertical_alignment = "center"
    page.padding = 0

    # =========================
    # CONTROLES
    # =========================
    username_tf = ft.TextField(
        label="Usuario",
        autofocus=True,
        prefix_icon=ft.icons.PERSON_OUTLINE,
        **JetBrainsTheme.input_style(),
        on_submit=lambda e: password_tf.focus()
    )

    password_tf = ft.TextField(
        label="Contraseña",
        password=True,
        can_reveal_password=True,
        prefix_icon=ft.icons.LOCK_OUTLINE,
        **JetBrainsTheme.input_style(),
        on_submit=lambda e: handle_login(None)
    )

    error_txt = ft.Text("", color=ft.colors.RED_400, size=12, weight="w500")
    loading = ft.ProgressBar(visible=False, color=ThemeColors.ACCENT_BLUE, width=300)

    def handle_login(e):
        error_txt.value = ""
        loading.visible = True
        page.update()
        
        data, error = login(username_tf.value, password_tf.value)
        
        if error:
            error_txt.value = error.get("detail", "Credenciales inválidas")
            loading.visible = False
            page.update()
            return

        Session.set(token=data["access_token"], user=data["user"])
        
        # Animación de salida (opcional)
        page.clean()
        menu_view(page)

    def _extract_sso_token():
        candidates = []
        for attr in ("query", "route", "url"):
            value = getattr(page, attr, None)
            if value:
                candidates.append(str(value))

        params = getattr(page, "query_params", None)
        if isinstance(params, dict) and params.get("sso_token"):
            return str(params.get("sso_token"))

        for raw in candidates:
            query_str = raw
            if "?" in raw:
                query_str = raw.split("?", 1)[1]
            if query_str.startswith("?"):
                query_str = query_str[1:]
            if not query_str:
                continue

            parsed = parse_qs(query_str)
            token_values = parsed.get("sso_token")
            if token_values and token_values[0]:
                return token_values[0]
        return None

    def try_sso_autologin():
        sso_token = _extract_sso_token()
        if not sso_token:
            return

        error_txt.value = ""
        loading.visible = True
        page.update()

        data, error = login_with_sso_token(sso_token)
        if error:
            detail = str(error.get("detail", ""))
            if "CRM no esta en linea" in detail:
                error_txt.value = "CRM no esta en linea"
            else:
                error_txt.value = detail or "No se pudo validar sesion ERP"
            loading.visible = False
            page.update()
            return

        Session.set(token=data["access_token"], user=data["user"])
        page.clean()
        menu_view(page)

    login_btn = ft.ElevatedButton(
        text="INGRESAR AL SISTEMA",
        style=JetBrainsTheme.primary_button_style(),
        width=300,
        height=50,
        on_click=handle_login,
    )

    # =========================
    # BACKGROUND DECORATION (JETBRAINS BLOBS)
    # =========================
    blobs = ft.Stack([
        ft.Container(
            width=500, height=500, border_radius=250,
            bgcolor=ft.colors.with_opacity(0.1, ThemeColors.ACCENT_BLUE),
            blur=ft.Blur(100, 100),
            left=-150, top=-150
        ),
        ft.Container(
            width=400, height=400, border_radius=200,
            bgcolor=ft.colors.with_opacity(0.08, ThemeColors.ACCENT_VIOLET),
            blur=ft.Blur(80, 80),
            right=-100, bottom=-100
        )
    ])

    # =========================
    # LOGIN CARD
    # =========================
    login_card = ft.Container(
        **JetBrainsTheme.card_style(),
        width=400,
        content=ft.Column([
            ft.Row([
                ft.Container(width=8, height=30, bgcolor=ThemeColors.ACCENT_BLUE, border_radius=4),
                ft.Text("ACCESO", size=24, weight="black", color=ThemeColors.TEXT_PRIMARY),
            ], spacing=10, alignment="center"),
            
            ft.Text("Inventario de Alto Rendimiento", size=14, color=ThemeColors.TEXT_SECONDARY, text_align="center"),
            ft.Container(height=20),
            
            username_tf,
            password_tf,
            error_txt,
            ft.Container(height=10),
            
            login_btn,
            loading,
            
            ft.Container(height=20),
            ft.Text("© 2026 Antigravity Systems", size=10, color=ft.colors.with_opacity(0.3, ThemeColors.TEXT_SECONDARY))
        ], horizontal_alignment="center", spacing=15)
    )

    content = ft.Stack([
        blobs,
        ft.Container(
            expand=True,
            content=ft.Row([
                # Lado izquierdo: Ilustración simple JetBrains (opcional)
                ft.Column([
                    ft.Text("Administración\nLogística", 
                            size=48, weight="black", 
                            color=ft.colors.WHITE,
                           ),
                    ft.Text("Control absoluto de infraestructura, activos y logística operativa.", 
                           size=16, color=ThemeColors.TEXT_SECONDARY, width=400)
                ], expand=True, alignment="center", horizontal_alignment="center", visible=True),
                
                # Lado derecho: El card
                ft.Column([login_card], expand=True, alignment="center", horizontal_alignment="center")
            ], expand=True)
        )
    ], expand=True)

    try_sso_autologin()
    return content
