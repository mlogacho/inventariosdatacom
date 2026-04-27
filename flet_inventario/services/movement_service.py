from core.api_client import APIClient

# =========================
# LISTAR MOVIMIENTOS
# =========================
def list_movements(params=None):
    """
    Obtiene movimientos filtrados desde el backend.
    """
    return APIClient.get("inventory/movements/", params=params)

def get_movement_stats():
    """
    Obtiene estadísticas globales de movimientos y activos.
    """
    return APIClient.get("inventory/movements/stats/")

def get_asset_history(item_id: str):
    """
    Obtiene la línea de tiempo de un activo específico.
    """
    return APIClient.get(f"inventory/movements/{item_id}/history/")

def register_movement(data: dict):
    """
    Registra un nuevo movimiento en el sistema.
    """
    return APIClient.post("inventory/movements/", json=data)
