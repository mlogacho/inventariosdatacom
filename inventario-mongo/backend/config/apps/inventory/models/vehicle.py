import mongoengine as me
from config.apps.base.base_document import BaseDocument


class Vehicle(BaseDocument):
    placa = me.StringField(required=True, unique=True)
    marca = me.StringField()
    modelo = me.StringField()
    anio = me.IntField()

    meta = {
        "collection": "vehiculos",
    }
