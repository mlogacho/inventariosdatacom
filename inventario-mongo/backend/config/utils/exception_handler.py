"""
Manejador de excepciones personalizado para DRF.

ISO 9001 10.2 — No conformidad y acción correctiva: respuestas de error estructuradas.
V-26 Fix: No exponer str(exc) en producción para evitar filtración de información interna.
"""
import logging
from django.conf import settings
from rest_framework.views import exception_handler
from config.utils.api_response import api_response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Manejador de excepciones que retorna respuestas JSON estandarizadas.

    En DESARROLLO (DEBUG=True): incluye el mensaje de la excepción para depuración.
    En PRODUCCIÓN (DEBUG=False): mensaje genérico para no revelar detalles internos.

    ISO 27001 A.12.4 — Los detalles de excepciones se registran en logs,
    no en respuestas al cliente en producción.
    """
    # Llamar al manejador DRF por defecto para obtener la respuesta estándar
    response = exception_handler(exc, context)

    view = context.get("view")
    view_name = view.__class__.__name__ if view else "unknown"

    if response is not None:
        # Loggear la excepción para auditoría interna
        logger.warning(
            "Excepción DRF [%s] en %s: %s",
            response.status_code,
            view_name,
            str(exc),
        )

        # V-26 Fix: Solo exponer detalles en DEBUG
        if settings.DEBUG:
            message = str(exc)
        else:
            # En producción: mensaje genérico para no filtrar info interna
            message = _get_safe_message(response.status_code)

        return api_response(
            data=response.data,
            message=message,
            status_code=response.status_code,
            success=False,
        )

    # Excepción no manejada (error 500)
    logger.exception("Excepción inesperada en %s", view_name)

    return api_response(
        data=None,
        message=str(exc) if settings.DEBUG else "Ocurrió un error inesperado en el servidor.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        success=False,
    )


def _get_safe_message(status_code: int) -> str:
    """
    Retorna un mensaje de error genérico y seguro según el código de estado HTTP.
    Evita filtrar detalles de implementación al cliente en producción.
    """
    messages = {
        400: "Solicitud inválida. Verifique los datos enviados.",
        401: "No autenticado. Inicie sesión para continuar.",
        403: "No tiene permiso para realizar esta acción.",
        404: "El recurso solicitado no fue encontrado.",
        405: "Método HTTP no permitido para este endpoint.",
        429: "Demasiadas solicitudes. Intente nuevamente en un momento.",
        500: "Error interno del servidor.",
    }
    return messages.get(status_code, "Ocurrió un error en la solicitud.")
