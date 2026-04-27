import mongoengine as me

from config.apps.base.base_document import BaseDocument
from config.apps.inventory.models.customer import Customer
from config.apps.users.models.user import User


class Facility(BaseDocument):
    """
    Representa una instalación realizada para un cliente.
    """

    codigo_instalacion = me.StringField(required=True, unique=True)

    cliente = me.ReferenceField(
        Customer,
        required=True,
        reverse_delete_rule=me.DENY
    )

    tecnico = me.ReferenceField(
        User,
        required=True
    )

    # V-FAC-01: Vehículo asignado a la instalación
    vehiculo_id = me.StringField()  # Guardamos ID como string para evitar problemas de referencia

    direccion_instalacion = me.StringField()

    estado = me.StringField(
        choices=[
            "planificada",
            "en_proceso",
            "finalizada",
            "cancelada"
        ],
        default="planificada"
    )

    fecha_programada = me.DateTimeField()
    fecha_inicio = me.DateTimeField()
    fecha_fin = me.DateTimeField()

    # Sección 2: Equipos en STOCK seleccionados
    # Cada dict: {item_id, destino_final}
    items_planificados = me.ListField(me.DictField())

    # Sección 3: Herramientas desde stock real
    # Cada dict: {item_id, nombre, codigo, bodega_origen_id,
    #             cantidad, observaciones, retorno_registrado,
    #             estado_retorno, observaciones_retorno}
    herramientas = me.ListField(me.DictField())

    # Sección 4: Materiales / Consumibles desde stock real
    # Cada dict: {item_id, nombre, codigo, unidad,
    #             cantidad_reservada, cantidad_usada,
    #             bodega_retorno_id, observaciones}
    consumibles = me.ListField(me.DictField())

    # Sección 5: Servicios entregados al cliente
    # Cada dict: {detalle, descripcion}
    servicios = me.ListField(me.DictField())

    # Observaciones generales
    observaciones = me.StringField()

    meta = {
        "collection": "instalaciones",  # NO se cambia para no romper datos
        "indexes": ["codigo_instalacion", "estado"],
    }
