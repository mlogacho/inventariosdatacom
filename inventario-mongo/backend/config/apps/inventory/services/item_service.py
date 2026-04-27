"""
Servicio de gestión de ítems del inventario.
ISO 9001 8.1 — Validación de estados según reglas de negocio documentadas.
"""
from config.apps.inventory.models.item import Item, ALL_ESTADOS

# Fuente de verdad importada directamente del modelo
ALLOWED_ITEM_STATES = ALL_ESTADOS


def soft_delete_item(item: Item) -> None:
    item.is_active = False
    item.save()


def change_item_status(item: Item, new_status: str) -> None:
    """[DEPRECADO] Usar traceability_service.process_asset_transition."""
    import logging
    logging.getLogger(__name__).warning(
        "change_item_status está deprecado. Usar process_asset_transition."
    )
    if new_status not in ALLOWED_ITEM_STATES:
        raise ValueError(f"Estado '{new_status}' no válido.")
    item.estado = new_status
    item.save()


def update_item_location(item: Item, location_id) -> None:
    """Actualiza la ubicación actual del ítem."""
    item.ubicacion_actual_id = location_id
    item.save()
