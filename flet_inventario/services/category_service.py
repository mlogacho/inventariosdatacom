from core.api_client import APIClient

# =========================
# LISTAR CATEGORÍAS
# =========================
def list_categories():
    return APIClient.get("inventory/categories/")
