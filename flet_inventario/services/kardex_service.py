from core.api_client import APIClient


def get_kardex_dashboard(params=None):
    return APIClient.get("inventory/kardex/", params=params)
