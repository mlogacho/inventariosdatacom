import mongoengine as me
from config.apps.base.base_document import BaseDocument


class Customer(BaseDocument):
    nombre_cliente = me.StringField(required=True)
    sucursal = me.StringField()
    ubicacion = me.DictField()

    meta = {
        "collection": "clientes",
    }
