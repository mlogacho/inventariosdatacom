from rest_framework.permissions import BasePermission, SAFE_METHODS
from config.apps.users.permissions.permissions_map import ROLE_PERMISSIONS


class DRFRBACPermission(BasePermission):
    """
    Permiso global basado en Roles (RBAC) para Django Rest Framework.
    
    ISO 27001 A.9.1 — Control de acceso: requiere autenticación y permisos específicos.
    ISO 9001 5.3   — Roles, responsabilidades y autoridades definidos.
    
    Funciona leyendo 'resource_name' de la vista y validando contra ROLE_PERMISSIONS.
    """

    def has_permission(self, request, view):
        user = getattr(request, "user", None)

        # 1. El usuario debe estar autenticado y activo
        if not user or not user.is_active:
            return False

        # 2. Obtener el nombre del recurso de la vista
        # Si no está definido, se deniega el acceso para forzar la declaración de recursos.
        resource = getattr(view, "resource_name", None)
        if not resource:
            # En login no solemos usar RBAC (usamos AllowAny), 
            # pero para seguridad interna, si falta el nombre del recurso, bloqueamos.
            return False

        # 3. Obtener el mapa de permisos del rol del usuario
        role_permissions = ROLE_PERMISSIONS.get(user.rol, set())

        # 4. Validar según método HTTP
        if request.method in SAFE_METHODS:
            return f"{resource}:read" in role_permissions

        if request.method == "POST":
            return f"{resource}:create" in role_permissions

        if request.method in ("PUT", "PATCH"):
            return f"{resource}:update" in role_permissions

        if request.method == "DELETE":
            return f"{resource}:delete" in role_permissions

        return False
