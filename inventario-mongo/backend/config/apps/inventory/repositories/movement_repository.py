from config.apps.base.repositories.base_repository import BaseRepository
from config.apps.inventory.models.movement import Movement

class MovementRepository(BaseRepository):
    model = Movement
