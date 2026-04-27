"""
Serializador de autenticación.

ISO 27001 A.9.4.3 — Gestión de contraseñas: validaciones mínimas de seguridad.
V-21 Fix: Agregar min_length en username y password para prevenir payloads triviales.
"""
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    """
    Valida las credenciales de login antes de procesar la autenticación.

    Validaciones aplicadas (ISO 27001 A.9.4.3):
    - username: mínimo 3 caracteres, máximo 150
    - password: mínimo 8 caracteres, máximo 128
    """
    username = serializers.CharField(
        min_length=3,
        max_length=150,
        error_messages={
            "min_length": "El usuario debe tener al menos 3 caracteres.",
            "max_length": "El usuario no puede exceder 150 caracteres.",
        }
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=128,
        error_messages={
            "min_length": "La contraseña debe tener al menos 8 caracteres.",
            "max_length": "La contraseña no puede exceder 128 caracteres.",
        }
    )