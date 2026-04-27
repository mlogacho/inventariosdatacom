"""
Servicio JWT para generación y validación de tokens de acceso.

ISO 27001 A.10.1 — Criptografía: tokens con expiración y campos de auditoría.
V-10 Fix: datetime.utcnow() → datetime.now(timezone.utc) (deprecated en Python 3.12+)
V-22 Fix: Agregar campo `iat` (issued at) para detectar tokens emitidos antes de rotación de clave.
"""
import jwt
import logging
from datetime import datetime, timedelta, timezone
from django.conf import settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(user) -> str:
    """
    Crea un token JWT de acceso para el usuario dado.

    El token incluye:
    - user_id: identificador único del usuario
    - username: nombre de usuario (para logging, no como identificador)
    - rol: rol del usuario para RBAC
    - exp: expiración (60 minutos desde ahora)
    - iat: momento de emisión (ISO 27001 A.12.4 — auditoría)

    Args:
        user: instancia del modelo User con id, username y rol.

    Returns:
        str: token JWT firmado.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": str(user.id),
        "username": user.username,
        "rol": user.rol,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """
    Decodifica y valida un token JWT de acceso.

    Returns:
        dict: payload del token si es válido.
        None: si el token está expirado o es inválido.
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.warning("Intento de uso de token JWT expirado.")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("Token JWT inválido: %s", str(e))
        return None
