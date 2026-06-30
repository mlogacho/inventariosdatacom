import os
import requests
from dotenv import load_dotenv
from core.session import Session

# Cargar variables de entorno (Opcional si ya se cargan en main)
load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")

class APIClient:
    """
    Cliente centralizado para realizar peticiones HTTP a la API.
    Maneja automáticamente el formato estándar de respuesta y la autenticación.
    """

    @staticmethod
    def _get_headers(include_auth=True):
        headers = {}
        if include_auth and Session.token:
            headers["Authorization"] = f"Bearer {Session.token}"
        return headers

    @classmethod
    def request(cls, method, endpoint, **kwargs):
        url = f"{BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"

        include_auth = kwargs.pop("include_auth", True)
        
        # Inyectar headers de autenticación
        headers = kwargs.pop("headers", {})
        headers.update(cls._get_headers(include_auth=include_auth))
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=kwargs.pop("timeout", 10),
                **(kwargs)
            )
            
            # Lanzar error si el status no es 2xx
            response.raise_for_status()
            
            json_data = response.json()
            
            # Si el backend sigue el estándar {success, data, message}
            if isinstance(json_data, dict) and "success" in json_data:
                if not json_data["success"]:
                    raise Exception(json_data.get("message", "Error desconocido en la API"))
                return json_data.get("data")
            
            # Fallback para endpoints no refactorizados aún
            return json_data

        except requests.exceptions.RequestException as e:
            # Manejo centralizado de errores de red o HTTP
            error_msg = "Error de conexión con el servidor"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    base_msg = error_data.get("message", error_msg)
                    details = error_data.get("data")
                    if details and isinstance(details, dict):
                        detail_strs = []
                        for field, errs in details.items():
                            err_str = errs[0] if isinstance(errs, list) and len(errs) > 0 else str(errs)
                            detail_strs.append(f"{field}: {err_str}")
                        error_msg = f"{base_msg} | Detalles: " + ", ".join(detail_strs)
                    else:
                        error_msg = base_msg
                except Exception:
                    pass
            raise Exception(error_msg)

    @classmethod
    def get(cls, endpoint, params=None, **kwargs):
        return cls.request("GET", endpoint, params=params, **kwargs)

    @classmethod
    def post(cls, endpoint, data=None, json=None, **kwargs):
        return cls.request("POST", endpoint, data=data, json=json, **kwargs)

    @classmethod
    def put(cls, endpoint, data=None, json=None, **kwargs):
        return cls.request("PUT", endpoint, data=data, json=json, **kwargs)

    @classmethod
    def patch(cls, endpoint, data=None, json=None, **kwargs):
        return cls.request("PATCH", endpoint, data=data, json=json, **kwargs)

    @classmethod
    def delete(cls, endpoint, **kwargs):
        return cls.request("DELETE", endpoint, **kwargs)
