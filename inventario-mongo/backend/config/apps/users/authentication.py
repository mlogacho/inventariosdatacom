from rest_framework.authentication import BaseAuthentication

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
            return None

        token = header.replace("Bearer ", "")
        payload = decode_access_token(token)

        if not payload:
            return None

        user = User.objects(id=payload["user_id"], is_active=True).first()

        if not user:
            return None

        return (user, payload)
