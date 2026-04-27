from core.api_client import APIClient

# =========================
# LISTAR SUBCATEGORÍAS
# =========================
def list_subcategories(filters=None):
    return APIClient.get("inventory/subcategories/", params=filters)
