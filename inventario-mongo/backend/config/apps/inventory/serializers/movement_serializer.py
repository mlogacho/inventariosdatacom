"""
Serializador de movimientos de inventario.

ISO 9001 8.1 — Validación de tipo de operación con enum.
V-03 Fix: ChoiceField para tipo_movimiento en lugar de CharField libre.
"""
from rest_framework import serializers
from config.apps.inventory.models.movement import Movement, OperationType
from config.apps.inventory.models.item import Item
from config.apps.users.models.user import User


class MovementSerializer(serializers.Serializer):
    """
    Serializa y valida movimientos de inventario.

    Campos de escritura (input del cliente):
    - item_id, responsable_id, tipo_movimiento, origen, destino, notes

    Campos de solo lectura (calculados en el servidor):
    - id, fecha, estado_anterior, estado_nuevo, ip_address, module_source

    La colección es APPEND-ONLY: no existen métodos update() ni delete().
    """
    id = serializers.CharField(read_only=True)

    # Entrada (write_only): IDs que se resuelven a documentos Mongo
    item_id = serializers.CharField(write_only=True)
    responsable_id = serializers.CharField(write_only=True)

    # V-03 Fix: Enum explícito en lugar de CharField libre
    tipo_movimiento = serializers.ChoiceField(
        choices=OperationType.ALL,
        error_messages={
            "invalid_choice": (
                f"Tipo de movimiento inválido. "
                f"Valores permitidos: {', '.join(OperationType.ALL)}"
            )
        }
    )

    origen = serializers.DictField()
    destino = serializers.DictField()

    # Nota opcional del operador
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        default="",
    )

    # Solo lectura — se capturan en el servidor
    fecha = serializers.DateTimeField(read_only=True)
    estado_anterior = serializers.DictField(read_only=True)
    estado_nuevo = serializers.DictField(read_only=True)
    ip_address = serializers.CharField(read_only=True)
    module_source = serializers.CharField(read_only=True)

    # Campos cuantitativos (V-26)
    previous_quantity = serializers.IntegerField(read_only=True)
    new_quantity = serializers.IntegerField(read_only=True)
    delta = serializers.IntegerField(read_only=True)

    def validate_item_id(self, value):
        """Verifica que el ítem exista y esté activo."""
        item = Item.objects(id=value, is_active=True).first()
        if not item:
            raise serializers.ValidationError(
                "El ítem no existe o está inactivo."
            )
        return item

    def validate_responsable_id(self, value):
        """Verifica que el usuario responsable exista y esté activo."""
        user = User.objects(id=value, is_active=True).first()
        if not user:
            raise serializers.ValidationError(
                "El responsable no existe o está inactivo."
            )
        return user

    def validate_origen(self, value):
        """El origen no puede ser un diccionario vacío."""
        if not value:
            raise serializers.ValidationError("El campo 'origen' no puede estar vacío.")
        return value

    def validate_destino(self, value):
        """El destino no puede ser un diccionario vacío."""
        if not value:
            raise serializers.ValidationError("El campo 'destino' no puede estar vacío.")
        return value

    def to_representation(self, instance):
        """
        Enriquece la salida para el frontend (ISO 9001 8.5.1).
        Maneja compatibilidad con datos legados y enriquece objetos relacionados.
        """
        ret = super().to_representation(instance)

        # 1. Asegurar que origen/destino sean dicts (compatibilidad con datos antiguos)
        if isinstance(ret.get("origen"), str):
            ret["origen"] = {"tipo": "desconocido", "id": ret["origen"]}
        if isinstance(ret.get("destino"), str):
            ret["destino"] = {"tipo": "desconocido", "id": ret["destino"]}

        # 2. Enriquecer Ítem (para visualización en tablas globales)
        item = instance.item
        if item:
            ret["item"] = {
                "id": str(item.id),
                "codigo": item.codigo,
                "nombre": item.nombre,
            }

        # 3. Enriquecer Responsable
        resp = instance.responsable
        if resp:
            ret["responsable"] = {
                "id": str(resp.id),
                "username": resp.username,
            }

        ret["has_acta_pdf"] = bool(getattr(instance, "acta_pdf", None))
        ret["acta_filename"] = str(getattr(instance, "acta_filename", "") or "")

        return ret
