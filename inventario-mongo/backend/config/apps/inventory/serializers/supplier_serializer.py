from rest_framework import serializers
from config.apps.inventory.models.supplier import Supplier


class SupplierSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)

    nombre_proveedor = serializers.CharField()
    sucursal = serializers.CharField(required=False, allow_blank=True)
    ubicacion = serializers.DictField(required=False, default=dict)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if hasattr(instance, "id"):
            ret["id"] = str(instance.id)
        return ret

    def create(self, validated_data):
        instance = Supplier(**validated_data)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
