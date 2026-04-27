from rest_framework import serializers
from config.apps.inventory.models.vehicle import Vehicle


class VehicleSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)

    placa = serializers.CharField()
    marca = serializers.CharField(required=False, allow_blank=True)
    modelo = serializers.CharField(required=False, allow_blank=True)
    anio = serializers.IntegerField(required=False, allow_null=True)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if hasattr(instance, "id"):
            ret["id"] = str(instance.id)
        return ret

    def create(self, validated_data):
        instance = Vehicle(**validated_data)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
