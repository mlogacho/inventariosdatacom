import mongoengine as me
from config.apps.base.base_document import BaseDocument
from config.apps.inventory.models.category import Category


class SubCategory(BaseDocument):
    categoria = me.ReferenceField(Category, required=True, reverse_delete_rule=me.DENY)
    nombre = me.StringField(required=True)

    meta = {
        "collection": "subcategorias",
        "indexes": ["nombre"],
    }
