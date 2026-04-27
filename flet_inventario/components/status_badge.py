import flet as ft
from core.theme import ThemeColors


def status_badge(status_key: str):
    states = {
        # ── Equipos (estados originales) ─────────────────────────────────────
        "INGRESO_BODEGA":       (ThemeColors.STATE_RETURN,     "INGRESO A BODEGA"),
        "STOCK":                (ThemeColors.STATE_STOCK,      "EN STOCK"),
        "RESERVADO":            (ThemeColors.STATE_RESERVED,   "RESERVADO"),
        "SALIDA_INSTALACION":   (ThemeColors.STATE_DISPATCH,   "EN INSTALACIÓN"),
        "INSTALADO_CLIENTE":    (ThemeColors.STATE_INSTALLED,  "INSTALADO EN CLIENTE"),
        "REINGRESO_BODEGA":     (ThemeColors.STATE_RETURN,     "REINGRESO A BODEGA"),
        "DEVOLUCION_PROVEEDOR": (ThemeColors.STATE_PROVIDER,   "DEVOLUCIÓN PROVEEDOR"),
        "OBSOLETO":             (ThemeColors.STATE_OBSOLETE,   "DADO DE BAJA"),
        "ACTIVO_EN_CAMPO":      (ThemeColors.STATE_FIELD,      "ACTIVO EN CAMPO"),
        # ── Herramientas ──────────────────────────────────────────────────────
        "RESERVADA":        (ThemeColors.STATE_RESERVED,   "RESERVADA"),
        "EN_USO":           (ThemeColors.STATE_DISPATCH,   "EN USO"),
        "EN_MANTENIMIENTO": ("#FF8F00",                    "EN MANTENIMIENTO"),
        "OBSOLETA":         (ThemeColors.STATE_OBSOLETE,   "OBSOLETA"),
        # ── Materiales ────────────────────────────────────────────────────────
        "CONSUMIDO":          (ThemeColors.STATE_OBSOLETE, "CONSUMIDO"),
        "PARCIALMENTE_USADO": ("#FF8F00",                  "PARCIALMENTE USADO"),
        # ── Estados de Instalación ────────────────────────────────────────────
        "planificada": (ThemeColors.STATE_RESERVED, "PLANIFICADO"),
        "en_proceso":  (ThemeColors.STATE_DISPATCH, "EN PROCESO"),
        "finalizada":  (ThemeColors.STATE_INSTALLED,"FINALIZADA"),
        "cancelada":   (ThemeColors.STATE_PROVIDER, "CANCELADA"),
        # ── Roles ─────────────────────────────────────────────────────────────
        "admin":          (ThemeColors.ACCENT_MAGENTA, "ADMINISTRADOR"),
        "tecnico":        (ThemeColors.STATE_STOCK,    "TÉCNICO"),
        "administrativo": (ThemeColors.STATE_RESERVED, "ADMINISTRATIVO"),
    }

    color, text = states.get(status_key, (ft.colors.GREY_400, status_key))

    return ft.Container(
        content=ft.Text(text, size=11, weight="bold", color=ft.colors.WHITE),
        bgcolor=ft.colors.with_opacity(0.1, color),
        border=ft.border.all(1, ft.colors.with_opacity(0.4, color)),
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        border_radius=20,
    )
