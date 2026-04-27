"""
Vistas de gestión de usuarios.

ISO 27001 A.9 — Control de acceso: solo admin puede crear/leer usuarios.
V-06 Fix: Eliminar exposición de str(e) en respuestas de error.
"""
import logging
from rest_framework.views import APIView
from rest_framework import status
from config.apps.users.models.user import User
from config.apps.users.serializers.user_serializer import UserSerializer
from config.utils.api_response import api_response
from config.apps.users.permissions.rbac_permission import DRFRBACPermission

logger = logging.getLogger(__name__)


class UserListCreateView(APIView):
    """
    GET  → Listar usuarios (requiere permiso user:read)
    POST → Crear usuario  (requiere permiso user:create — solo admin)
    """
    permission_classes = [DRFRBACPermission]
    resource_name = "user"

    def get(self, request):
        users = User.objects(is_active=True).only("id", "username", "rol", "created_at")
        serializer = UserSerializer(users, many=True)
        return api_response(
            success=True,
            message="Usuarios listados con éxito",
            data=serializer.data,
        )

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                success=False,
                message="Datos inválidos",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            serializer.save()
            logger.info(
                "Usuario '%s' creado por '%s'",
                request.data.get("username"),
                request.user.username,
            )
            return api_response(
                success=True,
                message="Usuario creado con éxito",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            # V-06 Fix: Loggear internamente, pero devolver mensaje informativo si es error de integridad
            logger.exception("Error al crear usuario por '%s'", request.user.username)
            error_msg = str(e) if "duplicate" in str(e).lower() else "No se pudo crear el usuario. Intente nuevamente."
            return api_response(
                success=False,
                message=error_msg,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserDetailView(APIView):
    """
    GET    → Ver detalle de un usuario
    PUT    → Actualizar rol o contraseña
    DELETE → Baja lógica del usuario
    """
    permission_classes = [DRFRBACPermission]
    resource_name = "user"

    def get(self, request, pk):
        try:
            user = User.objects(id=pk, is_active=True).first()
            if not user:
                return api_response(success=False, message="Usuario no encontrado", status_code=status.HTTP_404_NOT_FOUND)
            
            serializer = UserSerializer(user)
            return api_response(success=True, data=serializer.data)
        except Exception:
            return api_response(success=False, message="ID de usuario inválido", status_code=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        try:
            user = User.objects(id=pk, is_active=True).first()
            if not user:
                return api_response(success=False, message="Usuario no encontrado", status_code=status.HTTP_404_NOT_FOUND)

            serializer = UserSerializer(user, data=request.data, partial=True)
            if not serializer.is_valid():
                return api_response(success=False, message="Datos inválidos", data=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
            
            serializer.save()
            logger.info("Usuario '%s' actualizado por '%s'", user.username, request.user.username)
            return api_response(success=True, message="Usuario actualizado con éxito", data=serializer.data)
        except Exception as e:
            logger.exception("Error al actualizar usuario")
            return api_response(success=False, message="No se pudo actualizar el usuario", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        try:
            user = User.objects(id=pk, is_active=True).first()
            if not user:
                return api_response(success=False, message="Usuario no encontrado", status_code=status.HTTP_404_NOT_FOUND)

            if user.id == request.user.id:
                return api_response(success=False, message="No puedes eliminar tu propio usuario", status_code=status.HTTP_400_BAD_REQUEST)

            user.is_active = False
            user.save()
            logger.warning("Usuario '%s' eliminado (baja lógica) por '%s'", user.username, request.user.username)
            return api_response(success=True, message="Usuario eliminado correctamente")
        except Exception as e:
            logger.exception("Error al eliminar usuario")
            return api_response(success=False, message="No se pudo eliminar el usuario", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
