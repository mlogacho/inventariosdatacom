import flet as ft
from core.session import Session
from core.theme import ThemeColors
from views.main_layout import MainLayout

# Imports dinámicos para evitar circulares y cargar solo lo necesario
from views.dashboard_view import dashboard_view
from views.items.item_view import item_view, create_item_view
from views.items.category_item_view import category_item_view
from views.items.item_traceability_view import item_traceability_view
from views.movements.movement_view import movement_view
from views.kardex.kardex_view import kardex_view
from views.stores.store_view import store_view

def menu_view(page: ft.Page):
    if not Session.user:
        return ft.Column([ft.Text("Sesión expirada", color=ft.colors.RED)], alignment="center")

    # Configuración global de la página para el nuevo estilo
    page.bgcolor = ThemeColors.BG_DEEP
    page.window_width = 1400
    page.window_height = 900
    page.window_resizable = True
    page.padding = 0
    page.spacing = 0
    current_layout = {"value": None}

    def navigate(key, **kwargs):
        """Manejador central de navegación con soporte para parámetros."""
        
        # Mapa de llaves a (Título, Función de Vista)
        modules = {
            "dashboard": ("Dashboard", dashboard_view),
            "items": ("Inventario de Activos", item_view),
            "create_item": ("Nuevo Activo", create_item_view),
            "kardex": ("KARDEX de Activos", kardex_view),
            "movements": ("Trazabilidad de Movimientos", movement_view),
            "item_traceability": ("Trazabilidad de Activo", item_traceability_view),
            "category_items":   ("Inventario por Categoría", category_item_view),
            "stores": ("Gestión de Bodegas", store_view),
        }

        if key == "logout":
            from views.login.login_view import login_view
            Session.clear()
            page.clean()
            page.add(login_view(page))
            page.update()
            return

        # Sincronizar IDs en sesión para compatibilidad con vistas legacy
        if key == "facility_detail" and "facility_id" in kwargs:
            page.session.set("facility_detail_id", kwargs["facility_id"])
        if "item_id" in kwargs:
            page.session.set("item_detail_id", kwargs["item_id"])

        if key not in modules:
            print(f"Error: Módulo '{key}' no encontrado.")
            return

        title, view_func = modules.get(key, ("Dashboard", dashboard_view))
        
        # Pasar navigate y cualquier parámetro adicional a la vista
        view_content = view_func(page, navigate, **kwargs)

        if current_layout["value"] is None:
            current_layout["value"] = MainLayout(
                page=page,
                content=view_content,
                title=title,
                navigate_callback=navigate,
                nav_key=key,
            )
        else:
            current_layout["value"].set_view(title=title, content=view_content, nav_key=key)

        page.update()
        return current_layout["value"]

    # Inicializar con el Dashboard
    layout = navigate("dashboard")
    return layout
