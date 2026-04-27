import mongoengine as me
from config.apps.base.base_document import BaseDocument


class Category(BaseDocument):
    nombre_categoria = me.StringField(required=True, unique=True)

    meta = {
        "collection": "categorias",
        "indexes": ["nombre_categoria"],
    }
