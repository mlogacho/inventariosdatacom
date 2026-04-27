from rest_framework import serializers
from config.apps.inventory.models.category import Category


class CategorySerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    nombre_categoria = serializers.CharField()

    def create(self, validated_data):
        return Category.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.nombre_categoria = validated_data.get(
            "nombre_categoria", instance.nombre_categoria
        )
        instance.save()
        return instance
