import mongoengine as me
from config.apps.base.base_document import BaseDocument


class Supplier(BaseDocument):
    nombre_proveedor = me.StringField(required=True)
    sucursal = me.StringField()
    ubicacion = me.DictField()

    meta = {
        "collection": "proveedores",
    }
