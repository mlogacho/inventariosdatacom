"""
Mapa centralizado de permisos por rol — RBAC.

ISO 27001 A.9.1 — Principio de mínimo privilegio.
ISO 9001 5.3   — Roles, responsabilidades y autoridades.

IMPORTANTE: Los movimientos son APPEND-ONLY.
No existe `movements:update` ni `movements:delete`.
"""
from config.apps.users.permissions.roles import Roles

ROLE_PERMISSIONS = {

    Roles.ADMIN.value: {
        "user:create",
        "user:read",
        "user:update",
        "user:delete",

        "store:create",
        "store:read",
        "store:update",
        "store:delete",

        "customer:create",
        "customer:read",
        "customer:update",
        "customer:delete",

        "supplier:create",
        "supplier:read",
        "supplier:update",
        "supplier:delete",

        "movement:create",
        "movement:read",

        "category:create",
        "category:read",
        "category:update",
        "category:delete",

        "subcategory:create",
        "subcategory:read",
        "subcategory:update",
        "subcategory:delete",

        "item:create",
        "item:read",
        "item:update",
        "item:delete",

        "vehicle:create",
        "vehicle:read",
        "vehicle:update",
        "vehicle:delete",

        "facility:create",
        "facility:read",
        "facility:update",
        "facility:delete",
    },

    Roles.TECNICO.value: {
        "facility:create",
        "facility:read",
        "facility:update",
        "facility:delete",

        "user:read",
        "movement:create",
        "movement:read",

        "store:read",

        "customer:create",
        "customer:read",
        "customer:update",

        "item:create",
        "item:read",
        "item:update",

        "vehicle:read",
        "category:read",
        "subcategory:read",
    },

    Roles.ADMINISTRATIVO.value: {
        "user:read",

        "store:read",

        "customer:create",
        "customer:read",
        "customer:update",

        "supplier:create",
        "supplier:read",
        "supplier:update",

        "item:create",
        "item:read",
        "item:update",

        "category:read",
        "subcategory:read",

        "movement:read",

        "facility:read",
    },
}
