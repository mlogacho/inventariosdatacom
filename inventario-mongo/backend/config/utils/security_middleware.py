"""
Middleware de cabeceras de seguridad HTTP.

ISO 27001 A.13.1.3 — Seguridad en comunicaciones.
Aplica cabeceras de seguridad estándar a todas las respuestas HTTP.
Referencias OWASP: Secure Headers Project.

V-H9 Fix: Agregar Content-Security-Policy y Strict-Transport-Security.
"""
from django.conf import settings


class SecurityHeadersMiddleware:
    """
    Añade cabeceras de seguridad HTTP a todas las respuestas.

    Cabeceras implementadas:
    - X-Frame-Options: Previene clickjacking (ISO 27001 A.13)
    - X-Content-Type-Options: Previene MIME sniffing
    - X-XSS-Protection: Activa filtro XSS del navegador
    - Referrer-Policy: Controla información de referrer
    - Permissions-Policy: Restringe APIs del navegador
    - Content-Security-Policy: Previene XSS y data injection (ISO 27001 A.13)
    - Strict-Transport-Security: Fuerza HTTPS (producción)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Prevenir clickjacking (ISO 27001 A.13)
        response["X-Frame-Options"] = "DENY"

        # Prevenir MIME type sniffing (OWASP)
        response["X-Content-Type-Options"] = "nosniff"

        # Filtro XSS del navegador (capa defensiva adicional)
        response["X-XSS-Protection"] = "1; mode=block"

        # Política de referrer: solo el origen, no la ruta completa
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restringir APIs del navegador no necesarias
        response["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

        # Content-Security-Policy (ISO 27001 A.13 — prevenir XSS)
        response["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "frame-ancestors 'none'"
        )

        # Strict-Transport-Security (solo en producción)
        if not getattr(settings, "DEBUG", False):
            response["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Eliminar header que revela el stack tecnológico
        if "X-Powered-By" in response:
            del response["X-Powered-By"]

        return response
