"""
Health check endpoint.

ISO 9001 9.1.3 — Análisis y evaluación: verificación del estado del sistema.
Endpoint público para monitoreo y verificación de disponibilidad.
"""
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


class HealthCheckView(APIView):
    """
    Endpoint de health check del sistema.

    GET /api/health/
    - No requiere autenticación
    - Retorna estado del servidor y versión
    - Usado para monitoreo y balanceadores de carga
    """
    permission_classes = [AllowAny]
    authentication_classes = []  # Skip JWT auth for health check
    throttle_classes = []  # No rate limiting on health check

    def get(self, request):
        return Response(
            {
                "status": "healthy",
                "service": "inventory-api",
                "version": "1.0.0",
            },
            status=status.HTTP_200_OK,
        )
