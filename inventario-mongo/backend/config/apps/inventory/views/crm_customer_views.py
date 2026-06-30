from rest_framework import status
from rest_framework.views import APIView

from config.apps.users.services.crm_sso_service import CRMServiceError, get_crm_active_clients
from config.utils.api_response import api_response


class CRMActiveCustomerListView(APIView):
    """Clientes activos provenientes de CRM para operaciones de Inventarios."""

    def get(self, request):
        auth_payload = request.auth if isinstance(request.auth, dict) else {}
        crm_token = auth_payload.get("crm_token")
        search = request.query_params.get("search", "").strip()

        if not crm_token:
            return api_response(
                success=False,
                message="Sesion ERP no disponible para consultar clientes CRM.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            clients = get_crm_active_clients(crm_token, search=search)
        except CRMServiceError as exc:
            return api_response(
                success=False,
                message=str(exc),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        normalized = []
        q = search.lower()
        for c in clients:
            name = (c.get("name") or "").strip()
            ruc = (c.get("tax_id") or "").strip()
            city = (c.get("city") or "").strip()

            haystack = f"{name} {ruc} {city}".lower()
            if q and q not in haystack:
                continue

            normalized.append(
                {
                    "id": c.get("id"),
                    "nombre_cliente": name,
                    "tax_id": ruc,
                    "city": city,
                    "classification": c.get("classification", "ACTIVE"),
                }
            )

        return api_response(
            success=True,
            message="Clientes activos CRM listados con exito",
            data=normalized,
            status_code=status.HTTP_200_OK,
        )
