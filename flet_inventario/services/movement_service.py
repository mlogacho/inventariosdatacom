from core.api_client import APIClient
from core.session import Session

import os
import tempfile

import requests

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


def download_acta_entrega_recepcion(payload: dict | None = None) -> str:
    """Genera el ACTA en backend y devuelve la ruta local del PDF descargado."""
    payload = payload or {}

    base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api").rstrip("/")
    url = f"{base_url}/inventory/movements/acta-entrega-recepcion/"

    headers = {}
    if Session.token:
        headers["Authorization"] = f"Bearer {Session.token}"

    resp = requests.post(url, json=payload, headers=headers, timeout=45)
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="acta_entrega_recepcion_") as tmp:
        tmp.write(resp.content)
        return tmp.name
