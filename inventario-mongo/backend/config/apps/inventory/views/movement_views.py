"""
Vistas de movimientos de inventario.

ISO 27001 A.12.4.1 — Audit logging: captura IP del cliente en cada movimiento.
ISO 9001  9.1     — Seguimiento y medición: historial paginado por ítem.

V-24 Fix: Paginación y endpoint de historial por ítem.
V-25 Fix: Captura de IP del cliente antes de registrar el movimiento.
"""
import logging
from rest_framework.views import APIView
from rest_framework import status
import mongoengine as me
from datetime import datetime, timezone

from config.apps.inventory.models.movement import Movement
from config.apps.inventory.serializers.movement_serializer import MovementSerializer
from config.apps.users.permissions.rbac_permission import DRFRBACPermission
from config.utils.api_response import api_response

import logging
logger = logging.getLogger(__name__)

# Número de registros por página por defecto
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _get_client_ip(request) -> str:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class MovementListCreateView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "movement"

    def get(self, request):
        queryset = Movement.objects().order_by("-fecha")
        from config.apps.inventory.models.item import Item

        # Filtro por ítem
        item_id = request.query_params.get("item_id")
        if item_id:
            queryset = queryset.filter(item=item_id)

        # Filtro por tipo de movimiento
        tipo = request.query_params.get("tipo_movimiento")
        if tipo:
            queryset = queryset.filter(tipo_movimiento=tipo)

        # Filtro por responsable
        responsable_id = request.query_params.get("responsable_id")
        if responsable_id:
            queryset = queryset.filter(responsable=responsable_id)

        # Filtro por rango de fechas
        fecha_desde = request.query_params.get("fecha_desde")
        if fecha_desde:
            try:
                dt_desde = datetime.strptime(fecha_desde, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                queryset = queryset.filter(fecha__gte=dt_desde)
            except ValueError:
                pass

        fecha_hasta = request.query_params.get("fecha_hasta")
        if fecha_hasta:
            try:
                from datetime import timedelta
                dt_hasta = datetime.strptime(fecha_hasta, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
                queryset = queryset.filter(fecha__lt=dt_hasta)
            except ValueError:
                pass

        # Filtro por OT
        ot_id = request.query_params.get("ot_id")
        if ot_id:
            queryset = queryset.filter(ot_id=ot_id)

        # Filtro por ubicación actual del ítem
        ubicacion_id = request.query_params.get("ubicacion_id")
        if ubicacion_id:
            from config.apps.inventory.models.item import Item

            if ubicacion_id == "__none__":
                item_ids = [
                    item.id
                    for item in Item.objects(
                        is_active=True,
                        ubicacion_actual_id=None,
                    ).only("id")
                ]
            else:
                item_ids = [
                    item.id
                    for item in Item.objects(
                        is_active=True,
                        ubicacion_actual_id=ubicacion_id,
                    ).only("id")
                ]

            queryset = queryset.filter(item__in=item_ids or ["__no_match__"])

        # Filtro por cliente (vía instalaciones/OT vinculadas)
        cliente = request.query_params.get("cliente")
        if cliente:
            from config.apps.inventory.models.customer import Customer
            from config.apps.inventory.models.facility import Facility

            customer_ids = [
                c.id
                for c in Customer.objects(
                    nombre_cliente__icontains=cliente,
                    is_active=True,
                ).only("id")
            ]

            ot_codes = []
            if customer_ids:
                ot_codes = [
                    f.codigo_instalacion
                    for f in Facility.objects(
                        cliente__in=customer_ids,
                        is_active=True,
                    ).only("codigo_instalacion")
                ]

            queryset = queryset.filter(ot_id__in=ot_codes or ["__no_match__"])

        # Filtro de búsqueda global
        search = request.query_params.get("search")
        if search:
            item_ids = Item.objects.filter(
                me.Q(codigo__icontains=search) | 
                me.Q(nombre__icontains=search) | 
                me.Q(serial__icontains=search)
            ).values_list("id")
            queryset = queryset.filter(item__in=item_ids)

        # Mostrar únicamente movimientos vinculados a ítems activos.
        active_item_ids = Item.objects(is_active=True).values_list("id")
        queryset = queryset.filter(item__in=active_item_ids)

        # Paginación
        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(
                MAX_PAGE_SIZE,
                max(1, int(request.query_params.get("page_size", DEFAULT_PAGE_SIZE)))
            )
        except (ValueError, TypeError):
            page = 1
            page_size = DEFAULT_PAGE_SIZE

        total = queryset.count()
        offset = (page - 1) * page_size
        paginated = queryset.skip(offset).limit(page_size)

        serializer = MovementSerializer(paginated, many=True)
        return api_response(
            data={
                "results": serializer.data,
                "pagination": {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            },
            message="Movimientos listados correctamente",
        )

    def post(self, request):
        return api_response(
            success=False,
            message="La creación manual de movimientos está deshabilitada. El sistema los registra automáticamente.",
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class MovementItemHistoryView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "movement"

    def get(self, request, item_id):
        try:
            queryset = Movement.objects(item=item_id).order_by("-fecha")
        except Exception:
            return api_response(
                success=False,
                message="ID de ítem inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Filtros adicionales
        tipo = request.query_params.get("tipo_movimiento")
        if tipo:
            queryset = queryset.filter(tipo_movimiento=tipo)

        fecha_desde = request.query_params.get("fecha_desde")
        if fecha_desde:
            try:
                dt_desde = datetime.strptime(fecha_desde, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                queryset = queryset.filter(fecha__gte=dt_desde)
            except ValueError:
                pass

        fecha_hasta = request.query_params.get("fecha_hasta")
        if fecha_hasta:
            try:
                from datetime import timedelta
                dt_hasta = datetime.strptime(fecha_hasta, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
                queryset = queryset.filter(fecha__lt=dt_hasta)
            except ValueError:
                pass

        # Paginación
        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(
                MAX_PAGE_SIZE,
                max(1, int(request.query_params.get("page_size", DEFAULT_PAGE_SIZE)))
            )
        except (ValueError, TypeError):
            page = 1
            page_size = DEFAULT_PAGE_SIZE

        total = queryset.count()
        offset = (page - 1) * page_size
        paginated = queryset.skip(offset).limit(page_size)

        serializer = MovementSerializer(paginated, many=True)
        return api_response(
            data={
                "item_id": item_id,
                "results": serializer.data,
                "pagination": {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            },
            message=f"Historial del ítem obtenido ({total} movimientos)",
        )


class MovementStatsView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "movement"

    def get(self, request):
        from config.apps.inventory.models.item import Item
        
        total_items = Item.objects(is_active=True).count()
        
        pipeline = [
            {"$match": {"is_active": True}},
            {"$group": {"_id": "$estado", "count": {"$sum": 1}}}
        ]
        items_by_state = list(Item.objects.aggregate(pipeline))
        stats_by_state = {item["_id"]: item["count"] for item in items_by_state if item["_id"]}
        
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        movements_today = Movement.objects(fecha__gte=today_start).count()
        
        return api_response(
            data={
                "total_items": total_items,
                "stats_by_state": stats_by_state,
                "movements_today": movements_today,
            },
            message="Estadísticas obtenidas correctamente"
        )
