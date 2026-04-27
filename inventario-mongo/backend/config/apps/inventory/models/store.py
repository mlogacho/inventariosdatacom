import mongoengine as me
from config.apps.base.base_document import BaseDocument


class Store(BaseDocument):
    nombre_bodega = me.StringField(required=True)
    ubicacion = me.DictField()
    is_active = me.BooleanField(default=True)

    meta = {
        "collection": "bodegas",
    }
