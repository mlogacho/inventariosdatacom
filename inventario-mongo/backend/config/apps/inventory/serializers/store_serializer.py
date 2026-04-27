from rest_framework import serializers
from config.apps.inventory.models.store import Store


class StoreSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)

    nombre_bodega = serializers.CharField()
    ubicacion = serializers.DictField(required=False, default=dict)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if hasattr(instance, "id"):
            ret["id"] = str(instance.id)
        return ret

    def create(self, validated_data):
        instance = Store(**validated_data)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.nombre_bodega = validated_data.get(
            "nombre_bodega", instance.nombre_bodega
        )
        instance.ubicacion = validated_data.get(
            "ubicacion", instance.ubicacion
        )
        instance.save()
        return instance
