import json
import os
from urllib import error, parse, request


class CRMServiceError(Exception):
    pass


def _crm_base_url() -> str:
    return os.getenv("CRM_API_BASE_URL", "http://crm.datacom.ec").rstrip("/")


def _crm_get(path: str, token: str, params: dict | None = None, timeout: int = 8) -> dict:
    if not token:
        raise CRMServiceError("Sesion ERP no disponible para consultar CRM.")

    url = f"{_crm_base_url()}{path}"
    if params:
        query = parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
        if query:
            url = f"{url}?{query}"

    req = request.Request(
        url,
        headers={
            "Authorization": f"Token {token}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        if exc.code in (401, 403):
            raise CRMServiceError("Token SSO ERP invalido o expirado.")
        raise CRMServiceError(f"CRM respondio con error HTTP {exc.code}.")
    except (error.URLError, TimeoutError):
        raise CRMServiceError("CRM no esta en linea.")
    except json.JSONDecodeError:
        raise CRMServiceError("Respuesta invalida desde CRM.")


def get_crm_permissions(token: str) -> dict:
    return _crm_get("/api/core/user-permissions/", token)


def get_crm_active_clients(token: str, search: str | None = None) -> list[dict]:
    data = _crm_get("/api/clients/clients/", token, params={"search": search or ""})
    records = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(records, list):
        return []

    def is_active_client(item: dict) -> bool:
        classification = str(item.get("classification", "")).upper()
        if classification and classification != "ACTIVE":
            return False
        if item.get("is_active") is False:
            return False
        return True

    return [c for c in records if isinstance(c, dict) and is_active_client(c)]
