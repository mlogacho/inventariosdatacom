from rest_framework import serializers
from config.apps.inventory.models.item import Item, ALL_ESTADOS
from config.apps.inventory.models.subcategory import SubCategory


class ItemSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)

    codigo = serializers.CharField()
    nombre = serializers.CharField()

    subcategoria_id = serializers.CharField(write_only=True)

    tipo_item = serializers.ChoiceField(
        choices=["equipo", "herramienta", "material", "general"],
        default="general",
        required=False,
    )

    marca  = serializers.CharField(required=False, allow_blank=True)
    modelo = serializers.CharField(required=False, allow_blank=True)
    serial = serializers.CharField(required=False, allow_blank=True)

    estado = serializers.ChoiceField(
        choices=ALL_ESTADOS,
        default="STOCK",
        read_only=True,
    )

    # Cantidad disponible en bodega (Opción A — materiales/consumibles)
    cantidad = serializers.IntegerField(default=1, min_value=0, required=False)

    criticidad = serializers.ChoiceField(
        choices=["alta", "media", "baja"],
        default="media",
        required=False,
    )

    ubicacion_actual_id = serializers.CharField(required=False, allow_null=True)

    def validate_subcategoria_id(self, value):
        subcategoria = SubCategory.objects(id=value, is_active=True).first()
        if not subcategoria:
            raise serializers.ValidationError(
                "La subcategoría no existe o está inactiva"
            )
        return subcategoria

    def create(self, validated_data):
        subcategoria = validated_data.pop("subcategoria_id")

        from bson import ObjectId
        if "ubicacion_actual_id" in validated_data and validated_data["ubicacion_actual_id"]:
            try:
                validated_data["ubicacion_actual_id"] = ObjectId(
                    validated_data["ubicacion_actual_id"]
                )
            except Exception:
                pass

        return Item.objects.create(subcategoria=subcategoria, **validated_data)

    def update(self, instance, validated_data):
        if "subcategoria_id" in validated_data:
            instance.subcategoria = validated_data.pop("subcategoria_id")
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance

    def to_representation(self, instance):
        ret = super().to_representation(instance)

        sub = instance.subcategoria
        if sub:
            ret["subcategoria"] = {
                "id": str(sub.id),
                "nombre": sub.nombre,
                "categoria": {
                    "id": str(sub.categoria.id),
                    "nombre_categoria": sub.categoria.nombre_categoria,
                } if sub.categoria else None,
            }

        if instance.ubicacion_actual_id:
            ret["ubicacion_actual_id"] = str(instance.ubicacion_actual_id)

        # Exponer tipo_item y cantidad siempre
        ret["tipo_item"] = instance.tipo_item or "general"
        ret["cantidad"]  = instance.cantidad if instance.cantidad is not None else 1

        return ret
