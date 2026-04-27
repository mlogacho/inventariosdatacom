from config.apps.base.repositories.base_repository import BaseRepository
from config.apps.inventory.models.item import Item

class ItemRepository(BaseRepository):
    model = Item

    @classmethod
    def update_location(cls, item, new_location_id, session=None):
        item.ubicacion_actual_id = new_location_id
        item.save(session=session)
        return item
