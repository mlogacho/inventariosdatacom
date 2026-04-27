from rest_framework.permissions import BasePermission, SAFE_METHODS
from config.apps.users.permissions.permissions_map import ROLE_PERMISSIONS


class ItemPermission(BasePermission):
    """
    Permisos CRUD para items (inventario).
    DELETE = soft delete
    """

    def has_permission(self, request, view):
        user = getattr(request, "user", None)

        if not user or not user.is_active:
            return False

        role_permissions = ROLE_PERMISSIONS.get(user.rol, set())

        # READ
        if request.method in SAFE_METHODS:
            return "items:read" in role_permissions

        # CREATE
        if request.method == "POST":
            return "items:create" in role_permissions

        # UPDATE
        if request.method in ("PUT", "PATCH"):
            return "items:update" in role_permissions

        # DELETE (lógico)
        if request.method == "DELETE":
            return "items:delete" in role_permissions

        return False
