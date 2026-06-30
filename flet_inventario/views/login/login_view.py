import flet as ft
import os
from urllib.parse import parse_qs

from services.auth_service import login_with_sso_token
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
    # CONTROLES (SSO only)
    # =========================
    status_txt = ft.Text("Validando acceso ERP...", color=ThemeColors.TEXT_SECONDARY, size=13)
    loading = ft.ProgressBar(visible=True, color=ThemeColors.ACCENT_BLUE, width=300)

    erp_portal_url = os.getenv("ERP_PORTAL_URL", "https://erp.datacom.ec/erp-datacom")

    def _go_to_erp(reason=None):
        # En web, reemplaza la pestaña actual para evitar volver a una URL con token vencido.
        page.launch_url(erp_portal_url, web_window_name="_self")
        if reason:
            status_txt.value = reason
            loading.visible = False
            page.update()

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
            _go_to_erp("Redirigiendo a ERP DataCom...")
            return False

        loading.visible = True
        status_txt.value = "Validando token ERP..."
        page.update()

        data, error = login_with_sso_token(sso_token)
        if error:
            detail = str(error.get("detail", ""))
            if "expirado" in detail.lower() or "invalido" in detail.lower() or "inválido" in detail.lower():
                _go_to_erp("Sesion ERP expirada. Redirigiendo...")
                return False
            if "CRM no esta en linea" in detail or "CRM no está en línea" in detail:
                status_txt.value = "CRM no esta en linea. Reintenta desde ERP."
            else:
                status_txt.value = detail or "No se pudo validar sesion ERP"
            loading.visible = False
            page.update()
            return False

        Session.set(token=data["access_token"], user=data["user"])
        page.clean()
        menu_view(page)
        return True

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
    # ACCESO SSO CARD
    # =========================
    login_card = ft.Container(
        **JetBrainsTheme.card_style(),
        width=400,
        content=ft.Column([
            ft.Row([
                ft.Container(width=8, height=30, bgcolor=ThemeColors.ACCENT_BLUE, border_radius=4),
                ft.Text("ACCESO ERP", size=24, weight="black", color=ThemeColors.TEXT_PRIMARY),
            ], spacing=10, alignment="center"),
            
            ft.Text("Ingreso controlado por ERP DataCom", size=14, color=ThemeColors.TEXT_SECONDARY, text_align="center"),
            ft.Container(height=20),
            status_txt,
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

    sso_ok = try_sso_autologin()
    if sso_ok:
        return ft.Container(width=0, height=0, visible=False)
    return content
