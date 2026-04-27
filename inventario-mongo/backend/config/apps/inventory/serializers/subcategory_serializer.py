from rest_framework import serializers
from config.apps.inventory.models.subcategory import SubCategory
from config.apps.inventory.models.category import Category


class SubCategorySerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)

    nombre = serializers.CharField()
    categoria_id = serializers.CharField(write_only=True)

    def validate_categoria_id(self, value):
        categoria = Category.objects(id=value, is_active=True).first()
        if not categoria:
            raise serializers.ValidationError(
                "La categoría no existe o está inactiva"
            )
        return categoria

    def create(self, validated_data):
        categoria = validated_data.pop("categoria_id")
        return SubCategory.objects.create(
            categoria=categoria,
            **validated_data
        )

    def update(self, instance, validated_data):
        if "categoria_id" in validated_data:
            instance.categoria = validated_data.pop("categoria_id")

        instance.nombre = validated_data.get("nombre", instance.nombre)
        instance.save()
        return instance
