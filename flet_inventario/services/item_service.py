from core.api_client import APIClient

# =========================
# LISTAR ITEMS
# =========================
def list_items(filters=None):
    return APIClient.get("inventory/items/", params=filters)


# =========================
# CREAR ITEM
# =========================
def create_item(data: dict):
    return APIClient.post("inventory/items/", json=data)


# =========================
# TRANSICIÓN DE ESTADO (Lifecycle)
# =========================
def transition_item(item_id, next_state, ot_id=None, notes=""):
    payload = {
        "next_state": next_state,
        "ot_id": ot_id,
        "notes": notes
    }
    return APIClient.post(f"inventory/items/{item_id}/transition/", json=payload)
