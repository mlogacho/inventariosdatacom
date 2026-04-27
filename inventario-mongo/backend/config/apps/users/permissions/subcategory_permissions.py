from rest_framework.permissions import BasePermission, SAFE_METHODS
from config.apps.users.permissions.permissions_map import ROLE_PERMISSIONS


class SubCategoryPermission(BasePermission):
    """
    Permisos CRUD para subcategorías.
    DELETE = soft delete
    """

    def has_permission(self, request, view):
        user = getattr(request, "user", None)

        if not user or not user.is_active:
            return False

        role_permissions = ROLE_PERMISSIONS.get(user.rol, set())

        if request.method in SAFE_METHODS:
            return "subcategory:read" in role_permissions

        if request.method == "POST":
            return "subcategory:create" in role_permissions

        if request.method in ("PUT", "PATCH"):
            return "subcategory:update" in role_permissions

        if request.method == "DELETE":
            return "subcategory:delete" in role_permissions

        return False
