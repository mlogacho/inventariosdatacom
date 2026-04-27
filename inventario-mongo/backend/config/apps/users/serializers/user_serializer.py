"""
Serializador de usuarios del sistema.

ISO 27001 A.9.4.3 — Gestión de contraseñas: validación de complejidad.
V-23 Fix: Validar rol contra enum Roles para prevenir asignación arbitraria.
"""
from rest_framework import serializers
from config.apps.users.models.user import User
from config.apps.users.permissions.roles import Roles

# Lista de valores de rol válidos derivada del enum
VALID_ROLES = [role.value for role in Roles]


class UserSerializer(serializers.Serializer):
    """
    Serializa y deserializa usuarios.

    Campos expuestos:
    - id (read_only): ObjectId de MongoDB convertido a string
    - username: nombre de usuario único
    - password (write_only): contraseña en texto plano (se hashea antes de guardar)
    - rol: rol del usuario validado contra el enum Roles

    Campos excluidos intencionalmente de la respuesta:
    - password_hash: NUNCA se expone al cliente (ISO 27001 A.10)
    """
    id = serializers.CharField(read_only=True)
    username = serializers.CharField(
        required=True,
        min_length=3,
        max_length=50,
    )
    password = serializers.CharField(
        write_only=True,
        required=False,  # Permitir actualizaciones parciales sin contraseña
        min_length=4,
        max_length=128,
        error_messages={
            "min_length": "La contraseña debe tener al menos 4 caracteres.",
        }
    )
    rol = serializers.ChoiceField(
        choices=VALID_ROLES,
        error_messages={
            "invalid_choice": f"Rol inválido. Opciones válidas: {', '.join(VALID_ROLES)}",
        }
    )

    def to_representation(self, instance):
        """Asegura que el ObjectId de Mongo se convierta a string."""
        ret = super().to_representation(instance)
        if hasattr(instance, "id"):
            ret["id"] = str(instance.id)
        return ret

    def validate_username(self, value):
        """
        Verifica unicidad del username.
        En update (instancia existente), excluye el propio usuario de la verificación.
        """
        qs = User.objects(username=value)
        if self.instance:
            qs = qs.filter(id__ne=self.instance.id)
        if qs.first():
            raise serializers.ValidationError("Este nombre de usuario ya existe.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "La contraseña es obligatoria al crear un usuario."})
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        if "password" in validated_data:
            instance.set_password(validated_data.pop("password"))
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
