from core.api_client import APIClient

# =========================
# LISTAR USUARIOS
# =========================
def list_users():
    return APIClient.get("users/")
