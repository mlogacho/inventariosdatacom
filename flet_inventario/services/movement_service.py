from core.api_client import APIClient
from core.session import Session

from datetime import datetime
import os
import tempfile
from pathlib import Path

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

    download_dir = Path.home() / "Downloads" / "InventariosDatacom" / "Actas"
    download_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_path = download_dir / f"acta_entrega_recepcion_{timestamp}.pdf"

    # Si existe por colision de segundo, cae a un archivo temporal en la misma carpeta.
    if target_path.exists():
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf",
            prefix=f"acta_entrega_recepcion_{timestamp}_",
            dir=str(download_dir),
        ) as tmp:
            tmp.write(resp.content)
            return tmp.name

    target_path.write_bytes(resp.content)
    return str(target_path)


def download_movement_acta_pdf(movement_id: str) -> str:
    """Descarga ACTA PDF ya asociada a un movimiento y devuelve ruta local."""
    movement_id = str(movement_id or "").strip()
    if not movement_id:
        raise ValueError("movement_id es requerido")

    base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api").rstrip("/")
    url = f"{base_url}/inventory/movements/{movement_id}/acta-pdf/"

    headers = {}
    if Session.token:
        headers["Authorization"] = f"Bearer {Session.token}"

    resp = requests.get(url, headers=headers, timeout=45)
    resp.raise_for_status()

    download_dir = Path.home() / "Downloads" / "InventariosDatacom" / "Actas"
    download_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_path = download_dir / f"acta_movimiento_{movement_id}_{timestamp}.pdf"
    target_path.write_bytes(resp.content)
    return str(target_path)
