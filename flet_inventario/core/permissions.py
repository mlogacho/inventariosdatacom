# core/permissions.py
"""
Mapa de permisos del frontend — sincronizado con backend permissions_map.py

ISO 27001 A.9.1 — Principio de mínimo privilegio.
IMPORTANTE: Esta es una copia client-side para mostrar/ocultar elementos UI.
La validación REAL de permisos ocurre SIEMPRE en el servidor (server-side).

V-C1 Fix: Eliminar movements:update (movimientos son APPEND-ONLY).
V-H3/H4 Fix: Agregar category:delete, subcategory:delete, store:delete para admin.
"""

PERMISSIONS = {
    "admin": {
        "user:create", "user:read", "user:update", "user:delete",
        "store:create", "store:read", "store:update", "store:delete",
        "customer:create", "customer:read", "customer:update", "customer:delete",
        "supplier:create", "supplier:read", "supplier:update", "supplier:delete",
        "movement:create", "movement:read",
        "category:create", "category:read", "category:update", "category:delete",
        "subcategory:create", "subcategory:read", "subcategory:update", "subcategory:delete",
        "item:create", "item:read", "item:update", "item:delete",
        "vehicle:create", "vehicle:read", "vehicle:update", "vehicle:delete",
        "facility:create", "facility:read", "facility:update", "facility:delete",
    },
    "tecnico": {
        "facility:create", "facility:read", "facility:update", "facility:delete",
        "user:read",
        "movement:create", "movement:read",
        "store:read",
        "customer:create", "customer:read", "customer:update",
        "item:create", "item:read", "item:update",
        "vehicle:read",
        "category:read", "subcategory:read",
    },
    "administrativo": {
        "user:read",
        "store:read",
        "customer:create", "customer:read", "customer:update",
        "supplier:create", "supplier:read", "supplier:update",
        "item:create", "item:read", "item:update",
        "category:read", "subcategory:read",
        "movement:read",
        "facility:read",
    },
}


def can_access(rol: str, permission: str) -> bool:
    """
    Verifica si el rol tiene el permiso EXACTO definido en backend.
    NOTA: Esta es validación UI-only. El servidor siempre revalida.
    """
    return permission in PERMISSIONS.get(rol, set())
