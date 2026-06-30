from core.api_client import APIClient

# =========================
# LISTAR CLIENTES
# =========================
def list_customers(search=""):
    params = {"search": search} if search else None
    return APIClient.get("inventory/crm/customers/", params=params)
