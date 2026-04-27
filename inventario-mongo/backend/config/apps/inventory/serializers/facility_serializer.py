from rest_framework import serializers
from config.apps.inventory.models.facility import Facility
from config.apps.inventory.models.customer import Customer
from config.apps.users.models.user import User


class FacilitySerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)

    codigo_instalacion = serializers.CharField()

    cliente_id = serializers.CharField(write_only=True)
    tecnico_id = serializers.CharField(write_only=True)
    vehiculo_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    direccion_instalacion = serializers.CharField(required=False, allow_blank=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)

    estado = serializers.ChoiceField(
        choices=["planificada", "en_proceso", "finalizada", "cancelada"],
        default="planificada"
    )

    fecha_programada = serializers.DateTimeField(required=False, allow_null=True)
    fecha_inicio = serializers.DateTimeField(required=False, allow_null=True)
    fecha_fin = serializers.DateTimeField(required=False, allow_null=True)

    items_planificados = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )
    herramientas = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )
    consumibles = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if hasattr(instance, "id"):
            ret["id"] = str(instance.id)
        # Enriquecer cliente
        if hasattr(instance, "cliente") and instance.cliente:
            ret["cliente"] = {
                "id": str(instance.cliente.id),
                "nombre_cliente": getattr(instance.cliente, "nombre_cliente", "---"),
            }
        # Enriquecer técnico
        if hasattr(instance, "tecnico") and instance.tecnico:
            ret["tecnico"] = {
                "id": str(instance.tecnico.id),
                "username": getattr(instance.tecnico, "username", "---"),
            }
        return ret

    def validate_codigo_instalacion(self, value):
        # 1. Limpieza de "fantasmas": Borrar registros inactivos con este código
        # Esto permite reintentar tras un fallo previo que dejó un registro is_active=False.
        from config.apps.inventory.models.facility import Facility
        Facility.objects(codigo_instalacion=value, is_active=False).delete()

        # 2. Validar contra registros activos
        query = Facility.objects(codigo_instalacion=value, is_active=True)
        if self.instance:
            query = query.filter(id__ne=self.instance.id)
            
        if query.first():
            raise serializers.ValidationError(f"Ya existe una instalación activa con el código '{value}'")
        return value

    def validate_cliente_id(self, value):
        cliente = Customer.objects(id=value, is_active=True).first()
        if not cliente:
            raise serializers.ValidationError("Cliente no existe o está inactivo")
        return cliente

    def validate_tecnico_id(self, value):
        tecnico = User.objects(id=value, is_active=True).first()
        if not tecnico:
            raise serializers.ValidationError("Técnico no existe o está inactivo")
        return tecnico

    def create(self, validated_data):
        cliente = validated_data.pop("cliente_id")
        tecnico = validated_data.pop("tecnico_id")
        instance = Facility(cliente=cliente, tecnico=tecnico, **validated_data)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        if "cliente_id" in validated_data:
            instance.cliente = validated_data.pop("cliente_id")
        if "tecnico_id" in validated_data:
            instance.tecnico = validated_data.pop("tecnico_id")
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
