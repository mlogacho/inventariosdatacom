import hashlib
import re
from datetime import datetime, timezone

import mongoengine as me
from django.core.cache import cache
from rest_framework.views import APIView

from config.apps.inventory.models.item import Item
from config.apps.inventory.models.customer import Customer
from config.apps.inventory.models.movement import Movement
from config.apps.inventory.models.store import Store
from config.apps.inventory.serializers.movement_serializer import MovementSerializer
from config.apps.users.permissions.rbac_permission import DRFRBACPermission
from config.apps.users.services.crm_sso_service import CRMServiceError, get_crm_active_clients, get_crm_active_users
from config.utils.api_response import api_response

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
DEFAULT_MOV_LIMIT = 25
MAX_MOV_LIMIT = 100
CATALOG_TTL_SECONDS = 60


def _location_type(item: Item) -> str:
    estado = str(getattr(item, "estado", "") or "").upper()
    if estado in {"INSTALADO_CLIENTE", "ACTIVO_EN_CAMPO"}:
        return "CLIENTE"
    if getattr(item, "ot_id", None) and estado in {"RESERVADO", "SALIDA_INSTALACION", "INSTALADO_CLIENTE"}:
        return "CLIENTE"
    return "BODEGA"


def _normalize_store_id(value) -> str:
    if not value:
        return ""
    return str(value)


def _serialize_item(item: Item, store_name_by_id: dict[str, str]) -> dict:
    store_id = _normalize_store_id(getattr(item, "ubicacion_actual_id", None))
    return {
        "id": str(item.id),
        "codigo": item.codigo,
        "nombre": item.nombre,
        "estado": item.estado,
        "serial": getattr(item, "serial", "") or "",
        "marca": getattr(item, "marca", "") or "",
        "modelo": getattr(item, "modelo", "") or "",
        "numero_factura": getattr(item, "numero_factura", "") or "",
        "responsable_id": getattr(item, "responsable_id", "") or "",
        "responsable_nombre": getattr(item, "responsable_nombre", "") or "",
        "cliente_id": getattr(item, "cliente_id", "") or "",
        "cliente_nombre": getattr(item, "cliente_nombre", "") or "",
        "ubicacion_actual_id": store_id,
        "ubicacion_nombre": store_name_by_id.get(store_id, "") if store_id else "",
        "ot_id": getattr(item, "ot_id", "") or "",
        "tipo_item": getattr(item, "tipo_item", "general") or "general",
        "cantidad": getattr(item, "cantidad", 1) if getattr(item, "cantidad", None) is not None else 1,
    }


def _customers_from_crm(request) -> tuple[list[dict], str | None]:
    auth_payload = request.auth if isinstance(request.auth, dict) else {}
    crm_token = auth_payload.get("crm_token")
    if not crm_token:
        return [], "Sesion ERP no disponible para consultar clientes CRM."

    token_hash = hashlib.sha1(crm_token.encode("utf-8")).hexdigest()[:16]
    cache_key = f"kardex:crm_customers:{token_hash}"
    cached = cache.get(cache_key)
    if isinstance(cached, list):
        return cached, None

    try:
        clients = get_crm_active_clients(crm_token)
    except CRMServiceError as exc:
        return [], str(exc)

    normalized = [
        {
            "key": f"crm:{str(c.get('id'))}",
            "id": str(c.get("id")),
            "nombre_cliente": (c.get("name") or "").strip(),
            "tax_id": (c.get("tax_id") or "").strip(),
            "city": (c.get("city") or "").strip(),
            "source": "crm",
        }
        for c in clients
        if c.get("id") is not None and (c.get("name") or "").strip()
    ]

    cache.set(cache_key, normalized, CATALOG_TTL_SECONDS)
    return normalized, None


def _customers_from_system() -> list[dict]:
    customers = []
    for c in Customer.objects(is_active=True).only("id", "nombre_cliente", "sucursal"):
        customer_id = str(c.id)
        name = (c.nombre_cliente or "").strip()
        if not customer_id or not name:
            continue
        customers.append(
            {
                "key": f"customer:{customer_id}",
                "id": customer_id,
                "codigo_cliente": customer_id,
                "nombre_cliente": name,
                "sucursal": (c.sucursal or "").strip(),
                "source": "system",
            }
        )
    return customers


def _users_from_crm(request) -> tuple[list[dict], str | None]:
    auth_payload = request.auth if isinstance(request.auth, dict) else {}
    crm_token = auth_payload.get("crm_token")
    if not crm_token:
        return [], "Sesion ERP no disponible para consultar usuarios CRM."

    token_hash = hashlib.sha1(crm_token.encode("utf-8")).hexdigest()[:16]
    cache_key = f"kardex:crm_users:{token_hash}"
    cached = cache.get(cache_key)
    if isinstance(cached, list):
        return cached, None

    try:
        users = get_crm_active_users(crm_token)
    except CRMServiceError as exc:
        return [], str(exc)

    normalized = []
    for u in users:
        uid = u.get("id")
        username = (u.get("username") or "").strip()
        first_name = (u.get("first_name") or "").strip()
        last_name = (u.get("last_name") or "").strip()
        full_name = (u.get("full_name") or "").strip()
        if not full_name:
            full_name = " ".join(part for part in [first_name, last_name] if part).strip()
        if not full_name:
            full_name = username
        profile = u.get("profile") if isinstance(u.get("profile"), dict) else {}
        role_name = (u.get("role_name") or profile.get("role_name") or "").strip()
        if uid is None or not username:
            continue
        normalized.append(
            {
                "key": f"crmuser:{str(uid)}",
                "id": str(uid),
                "username": username,
                "full_name": full_name,
                "email": (u.get("email") or "").strip(),
                "rol": role_name or (u.get("role") or ""),
                "source": "crm",
            }
        )

    cache.set(cache_key, normalized, CATALOG_TTL_SECONDS)
    return normalized, None


class KardexDashboardView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "movement"

    def get(self, request):
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (TypeError, ValueError):
            page = 1

        try:
            page_size = int(request.query_params.get("page_size", DEFAULT_PAGE_SIZE))
            page_size = min(MAX_PAGE_SIZE, max(1, page_size))
        except (TypeError, ValueError):
            page_size = DEFAULT_PAGE_SIZE

        try:
            mov_limit = int(request.query_params.get("mov_limit", DEFAULT_MOV_LIMIT))
            mov_limit = min(MAX_MOV_LIMIT, max(1, mov_limit))
        except (TypeError, ValueError):
            mov_limit = DEFAULT_MOV_LIMIT

        search = (request.query_params.get("search") or "").strip()
        where = (request.query_params.get("where") or "TODOS").strip().upper()
        responsable = (request.query_params.get("responsable") or "TODOS").strip()
        cliente = (request.query_params.get("cliente") or "TODOS").strip()
        missing_bodega = str(request.query_params.get("missing_bodega") or "0").strip() in {"1", "true", "TRUE", "yes"}
        missing_responsable = str(request.query_params.get("missing_responsable") or "0").strip() in {"1", "true", "TRUE", "yes"}
        missing_cliente = str(request.query_params.get("missing_cliente") or "0").strip() in {"1", "true", "TRUE", "yes"}

        queryset = Item.objects(is_active=True)

        if search:
            pattern = re.compile(re.escape(search), re.IGNORECASE)
            queryset = queryset.filter(
                __raw__={
                    "$or": [
                        {"codigo": {"$regex": pattern.pattern, "$options": "i"}},
                        {"nombre": {"$regex": pattern.pattern, "$options": "i"}},
                        {"serial": {"$regex": pattern.pattern, "$options": "i"}},
                    ]
                }
            )

        if responsable != "TODOS":
            if responsable.startswith("user:"):
                rid = responsable.split(":", 1)[1]
                queryset = queryset.filter(responsable_id=rid)
            elif responsable.startswith("crmuser:"):
                rid = responsable.split(":", 1)[1]
                queryset = queryset.filter(responsable_id=rid)
            elif responsable.startswith("name:"):
                rname = responsable.split(":", 1)[1]
                queryset = queryset.filter(responsable_nombre=rname)

        if cliente != "TODOS":
            if cliente.startswith("customer:"):
                cid = cliente.split(":", 1)[1]
                queryset = queryset.filter(cliente_id=cid)
            if cliente.startswith("crm:"):
                cid = cliente.split(":", 1)[1]
                queryset = queryset.filter(cliente_id=cid)
            elif cliente.startswith("name:"):
                cname = cliente.split(":", 1)[1]
                queryset = queryset.filter(cliente_nombre=cname)

        all_items_filtered = list(
            queryset.only(
                "id",
                "codigo",
                "nombre",
                "estado",
                "serial",
                "marca",
                "modelo",
                "numero_factura",
                "responsable_id",
                "responsable_nombre",
                "cliente_id",
                "cliente_nombre",
                "ubicacion_actual_id",
                "ot_id",
                "tipo_item",
                "cantidad",
            )
        )

        if missing_bodega:
            all_items_filtered = [it for it in all_items_filtered if not getattr(it, "ubicacion_actual_id", None)]

        if missing_responsable:
            all_items_filtered = [
                it for it in all_items_filtered
                if not (getattr(it, "responsable_nombre", "") or "").strip()
            ]

        if missing_cliente:
            all_items_filtered = [
                it for it in all_items_filtered
                if not (getattr(it, "cliente_nombre", "") or "").strip()
            ]

        if where in {"BODEGA", "CLIENTE"}:
            all_items_filtered = [it for it in all_items_filtered if _location_type(it) == where]

        total_filtered = len(all_items_filtered)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = all_items_filtered[start:end]

        store_ids = {
            _normalize_store_id(getattr(it, "ubicacion_actual_id", None))
            for it in page_items
            if getattr(it, "ubicacion_actual_id", None)
        }
        store_name_by_id = {
            str(s.id): s.nombre_bodega
            for s in Store.objects(id__in=list(store_ids), is_active=True).only("id", "nombre_bodega")
        }

        items_payload = [_serialize_item(it, store_name_by_id) for it in page_items]

        active_items = list(Item.objects(is_active=True).only("estado", "ot_id", "responsable_nombre", "cliente_nombre", "ubicacion_actual_id"))
        total_items = len(active_items)
        en_bodega = len([x for x in active_items if _location_type(x) == "BODEGA"])
        en_cliente = len([x for x in active_items if _location_type(x) == "CLIENTE"])
        sin_bodega = len([x for x in active_items if not getattr(x, "ubicacion_actual_id", None)])
        sin_responsable = len([x for x in active_items if not (getattr(x, "responsable_nombre", "") or "").strip()])
        sin_cliente = len([x for x in active_items if not (getattr(x, "cliente_nombre", "") or "").strip()])

        movement_qs = Movement.objects().order_by("-fecha").limit(mov_limit)
        movement_payload = MovementSerializer(movement_qs, many=True).data

        users_catalog, crm_users_error = _users_from_crm(request)

        system_customers = _customers_from_system()
        crm_customers, crm_error = _customers_from_crm(request)
        customers_catalog = system_customers + list(crm_customers)

        stores_catalog = [
            {
                "id": str(s.id),
                "nombre_bodega": s.nombre_bodega,
            }
            for s in Store.objects(is_active=True).only("id", "nombre_bodega")
        ]

        now_utc = datetime.now(timezone.utc).isoformat()

        return api_response(
            success=True,
            message="KARDEX consolidado obtenido",
            data={
                "meta": {
                    "generated_at": now_utc,
                    "crm_users_warning": crm_users_error,
                    "crm_customers_warning": crm_error,
                },
                "stats": {
                    "total_items": total_items,
                    "en_bodega": en_bodega,
                    "en_cliente": en_cliente,
                    "sin_bodega": sin_bodega,
                    "sin_responsable": sin_responsable,
                    "sin_cliente": sin_cliente,
                },
                "filters": {
                    "search": search,
                    "where": where,
                    "responsable": responsable,
                    "cliente": cliente,
                    "missing_bodega": missing_bodega,
                    "missing_responsable": missing_responsable,
                    "missing_cliente": missing_cliente,
                    "page": page,
                    "page_size": page_size,
                },
                "pagination": {
                    "total": total_filtered,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_filtered + page_size - 1) // page_size,
                },
                "catalogs": {
                    "responsables": users_catalog,
                    "clientes": customers_catalog,
                    "bodegas": stores_catalog,
                },
                "items": items_payload,
                "movements": movement_payload,
            },
        )
