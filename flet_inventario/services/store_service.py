from core.api_client import APIClient
from core.session import Session


# =========================
# LISTAR BODEGAS
# =========================
def list_stores():
    return APIClient.get("inventory/stores/")
