"""
Vistas de autenticación de usuarios.

ISO 27001 A.9.1.2 — Control de acceso: rate limiting en login.
V-02 Fix: Rate limiting via LoginRateThrottle (5 intentos/minuto por IP).
V-19 Fix: Usar api_response estándar en todas las respuestas.
"""
import logging
import secrets
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny

from config.apps.users.models.user import User
from config.apps.users.serializers.auth_serializers import LoginSerializer
from config.apps.users.services.jwt_service import create_access_token
from config.apps.users.services.crm_sso_service import (
    CRMServiceError,
    get_crm_permissions,
)
from config.utils.throttles import LoginRateThrottle
from config.utils.api_response import api_response

logger = logging.getLogger(__name__)


class LoginView(APIView):
    """
    Endpoint de autenticación.

    POST /api/users/login/
    - Rate limited: máximo 5 intentos por minuto por IP (ISO 27001 A.9.1.2)
    - No requiere autenticación previa (AllowAny)
    - Registra intentos fallidos para auditoría (ISO 27001 A.12.4)
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = User.objects(username=username, is_active=True).first()

        # Respuesta genérica para no revelar si el usuario existe (ISO 27001 A.9)
        if not user or not user.check_password(password):
            logger.warning(
                "Intento de login fallido para usuario '%s' desde IP %s",
                username,
                request.META.get("REMOTE_ADDR", "desconocida"),
            )
            return api_response(
                success=False,
                message="Credenciales inválidas",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        token = create_access_token(user)

        logger.info(
            "Login exitoso: usuario '%s' (rol: %s) desde IP %s",
            user.username,
            user.rol,
            request.META.get("REMOTE_ADDR", "desconocida"),
        )

        return api_response(
            success=True,
            message="Autenticación exitosa",
            data={
                "access_token": token,
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "rol": user.rol,
                },
            },
            status_code=status.HTTP_200_OK,
        )


class CRMSSOLoginView(APIView):
    """Intercambia el token SSO del ERP por un JWT local de Inventarios."""

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        sso_token = (request.data or {}).get("sso_token") or request.query_params.get("sso_token")
        if not sso_token:
            return api_response(
                success=False,
                message="Debe enviar sso_token.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = get_crm_permissions(sso_token)
        except CRMServiceError as exc:
            return api_response(
                success=False,
                message=str(exc),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        username = profile.get("username")
        if not username:
            return api_response(
                success=False,
                message="No se pudo identificar usuario desde CRM.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        rol = "admin" if profile.get("is_superuser") else "administrativo"
        user = User.objects(username=username).first()
        if not user:
            user = User(username=username, rol=rol, is_active=True)
            user.set_password(secrets.token_urlsafe(24))
            user.save()
        else:
            user.rol = rol
            user.is_active = True
            user.save()

        token = create_access_token(user, extra_claims={"crm_token": sso_token})

        return api_response(
            success=True,
            message="Autenticación SSO ERP exitosa",
            data={
                "access_token": token,
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "rol": user.rol,
                },
            },
            status_code=status.HTTP_200_OK,
        )
