from core.api_client import APIClient

# =========================
# LISTAR CLIENTES
# =========================
def list_customers():
    # APIClient handles base URL, authentication, and error handling.
    # It returns the JSON response directly on success, or raises an exception on error.
    return APIClient.get("inventory/customers/")
