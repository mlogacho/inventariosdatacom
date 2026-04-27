from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from config.apps.users.models.user import User
from config.apps.users.services.jwt_service import decode_access_token


class JWTAuthentication(BaseAuthentication):
    """
    Autenticación global JWT para DRF.
    """

    def authenticate(self, request):
        header = request.headers.get("Authorization")

        if not header:
            return None

        if not header.startswith("Bearer "):
            raise AuthenticationFailed("Formato de token inválido")

        token = header.replace("Bearer ", "")
        payload = decode_access_token(token)

        if not payload:
            raise AuthenticationFailed("Token inválido o expirado")

        user = User.objects(id=payload["user_id"], is_active=True).first()

        if not user:
            raise AuthenticationFailed("Usuario no válido o inactivo")

        return (user, None)
