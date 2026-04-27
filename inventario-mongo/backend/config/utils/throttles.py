"""
Throttles personalizados para el sistema de inventario.

ISO 27001 A.9.1.2 — Control de acceso: limitar intentos de login.
Previene ataques de fuerza bruta sobre el endpoint de autenticación.
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """
    Throttle para el endpoint de login: máximo 5 intentos por minuto por IP.
    Aplica a usuarios no autenticados (anónimos).
    """
    scope = "login"


class SustainedUserThrottle(UserRateThrottle):
    """
    Throttle sostenido para usuarios autenticados: 1000 requests/día.
    Previene abusos de la API por parte de tokens comprometidos.
    """
    scope = "sustained"
