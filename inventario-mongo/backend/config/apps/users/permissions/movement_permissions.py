"""
Permisos para movimientos de inventario.

ISO 27001 A.12.4.1 — Registros de auditoría inmutables.
Los movimientos son APPEND-ONLY: solo se permite GET (lectura) y POST (creación).
PUT, PATCH y DELETE están EXPLÍCITAMENTE BLOQUEADOS.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS
from config.apps.users.permissions.permissions_map import ROLE_PERMISSIONS


class MovementPermission(BasePermission):
    """
    Permisos para movimientos de inventario (APPEND-ONLY).

    Operaciones permitidas:
    - GET:  Lectura de movimientos (requiere movements:read)
    - POST: Creación de movimientos (requiere movements:create)

    Operaciones BLOQUEADAS (inmutabilidad):
    - PUT/PATCH: No se permite modificar movimientos existentes
    - DELETE:    No se permite eliminar movimientos
    """

    def has_permission(self, request, view):
        user = getattr(request, "user", None)

        if not user or not user.is_active:
            return False

        # BLOQUEAR explícitamente UPDATE y DELETE — append-only
        if request.method in ("PUT", "PATCH", "DELETE"):
            return False

        role_permissions = ROLE_PERMISSIONS.get(user.rol, set())

        if request.method in SAFE_METHODS:
            return "movements:read" in role_permissions

        if request.method == "POST":
            return "movements:create" in role_permissions

        return False
