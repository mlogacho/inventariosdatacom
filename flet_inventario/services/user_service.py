from core.api_client import APIClient

# =========================
# LISTAR USUARIOS
# =========================
def list_users():
    return APIClient.get("users/")


def list_crm_users(search=""):
    params = {"search": search} if search else None
    return APIClient.get("inventory/crm/users/", params=params)
