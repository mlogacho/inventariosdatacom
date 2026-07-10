"""
Vistas de movimientos de inventario.

ISO 27001 A.12.4.1 — Audit logging: captura IP del cliente en cada movimiento.
ISO 9001  9.1     — Seguimiento y medición: historial paginado por ítem.

V-24 Fix: Paginación y endpoint de historial por ítem.
V-25 Fix: Captura de IP del cliente antes de registrar el movimiento.
"""
import logging
from datetime import datetime, timezone

from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework import status
import mongoengine as me

from config.apps.inventory.models.item import Item
from config.apps.inventory.models.movement import Movement
from config.apps.inventory.models.movement import OperationType
from config.apps.inventory.serializers.movement_serializer import MovementSerializer
from config.apps.inventory.services.acta_entrega_recepcion_service import generate_acta_entrega_recepcion_pdf
from config.apps.users.models.user import User
from config.apps.users.permissions.rbac_permission import DRFRBACPermission
from config.apps.users.services.crm_sso_service import CRMServiceError, get_crm_active_users
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


class MovementActaEntregaRecepcionView(APIView):
    """Genera el PDF ACTA DE ENTREGA - RECEPCION en base a movimientos."""

    permission_classes = [DRFRBACPermission]
    resource_name = "movement"

    def post(self, request):
        try:
            recibe_user_id = str((request.data or {}).get("recibe_user_id") or "").strip()
            observacion = str((request.data or {}).get("observacion") or "").strip()
            item_id = str((request.data or {}).get("item_id") or "").strip()
            item_ids_raw = (request.data or {}).get("item_ids") or []

            if not recibe_user_id:
                return api_response(
                    success=False,
                    message="Debe seleccionar el usuario que recibe.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            auth_payload = request.auth if isinstance(request.auth, dict) else {}
            crm_token = auth_payload.get("crm_token")
            if not crm_token:
                return api_response(
                    success=False,
                    message="Sesion ERP no disponible para consultar usuarios CRM.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            try:
                crm_users = get_crm_active_users(crm_token)
            except CRMServiceError as exc:
                return api_response(
                    success=False,
                    message=str(exc),
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            def _name_of(user: dict) -> str:
                return (
                    (user.get("full_name") or "").strip()
                    or (user.get("username") or "").strip()
                    or "N/D"
                )

            def _role_of(user: dict) -> str:
                profile = user.get("profile") if isinstance(user.get("profile"), dict) else {}
                return (
                    (user.get("role_name") or "").strip()
                    or (profile.get("role_name") or "").strip()
                    or (user.get("role") or "").strip()
                    or "Cargo no registrado"
                )

            entrega_user = next(
                (u for u in crm_users if (u.get("username") or "").strip() == (request.user.username or "").strip()),
                None,
            )
            recibe_user = next((u for u in crm_users if str(u.get("id")) == recibe_user_id), None)

            if not recibe_user:
                return api_response(
                    success=False,
                    message="El usuario seleccionado para recibe no existe en CRM.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            normalized_ids = []
            if isinstance(item_ids_raw, list):
                for raw in item_ids_raw:
                    sid = str(raw or "").strip()
                    if sid and sid not in normalized_ids:
                        normalized_ids.append(sid)
            if item_id and item_id not in normalized_ids:
                normalized_ids.append(item_id)

            items_rows = []
            items_for_audit = []

            if normalized_ids:
                selected_items = []
                item_map = {
                    str(it.id): it
                    for it in Item.objects(id__in=normalized_ids, is_active=True)
                }
                for sid in normalized_ids:
                    if sid in item_map:
                        selected_items.append(item_map[sid])

                if not selected_items:
                    return api_response(
                        success=False,
                        message="Los items seleccionados no existen o estan inactivos.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

                for it in selected_items:
                    items_for_audit.append(it)
                    items_rows.append(
                        {
                            "detalle": it.nombre,
                            "marca": getattr(it, "marca", "") or "---",
                            "modelo": getattr(it, "modelo", "") or "---",
                            "serie": getattr(it, "serial", "") or "---",
                            "mac": getattr(it, "mac", "") or "",
                            "cantidad": 1,
                            "unidad": "Unidad",
                        }
                    )
            else:
                movimiento_qs = Movement.objects(tipo_movimiento__in=["SALIDA", "INSTALACION"]).order_by("-fecha")

                seen_item_ids = set()
                selected_movements = []
                for mov in movimiento_qs:
                    if not mov.item:
                        continue
                    sid = str(mov.item.id)
                    if sid in seen_item_ids:
                        continue
                    seen_item_ids.add(sid)
                    selected_movements.append(mov)

                if not selected_movements:
                    return api_response(
                        success=False,
                        message="Debe seleccionar al menos un item para generar el acta.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

                fallback_item_ids = [mov.item.id for mov in selected_movements if mov.item]
                item_map = {str(it.id): it for it in Item.objects(id__in=fallback_item_ids, is_active=True)}
                for mov in selected_movements:
                    it = item_map.get(str(mov.item.id))
                    if not it:
                        continue
                    items_for_audit.append(it)
                    items_rows.append(
                        {
                            "detalle": it.nombre,
                            "marca": getattr(it, "marca", "") or "---",
                            "modelo": getattr(it, "modelo", "") or "---",
                            "serie": getattr(it, "serial", "") or "---",
                            "mac": getattr(it, "mac", "") or "",
                            "cantidad": 1,
                            "unidad": "Unidad",
                        }
                    )

            if not items_rows:
                return api_response(
                    success=False,
                    message="No se pudieron preparar items activos para el acta.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            entrega_nombre = _name_of(entrega_user) if entrega_user else (request.user.username or "N/D")
            entrega_cargo = _role_of(entrega_user) if entrega_user else (getattr(request.user, "rol", "") or "Usuario")
            recibe_nombre = _name_of(recibe_user)
            recibe_cargo = _role_of(recibe_user)

            pdf_bytes = generate_acta_entrega_recepcion_pdf(
                entrega_nombre=entrega_nombre,
                entrega_cargo=entrega_cargo,
                recibe_nombre=recibe_nombre,
                recibe_cargo=recibe_cargo,
                items=items_rows,
                observacion=observacion,
                city="Quito",
                generated_at=datetime.now(),
            )

            responsable_user = request.user if isinstance(request.user, User) else None
            if not responsable_user:
                req_username = str(getattr(request.user, "username", "") or "").strip()
                if req_username:
                    responsable_user = User.objects(username=req_username, is_active=True).first()

            if responsable_user:
                client_ip = _get_client_ip(request)
                notes_prefix = "ACTA ENTREGA-RECEPCION"
                if observacion:
                    notes_prefix = f"{notes_prefix}: {observacion}"

                for it in items_for_audit:
                    estado_actual = str(getattr(it, "estado", "") or "N/D")
                    Movement(
                        item=it,
                        tipo_movimiento=OperationType.AJUSTE,
                        fecha=datetime.now(timezone.utc),
                        responsable=responsable_user,
                        origen={
                            "tipo": "ACTA",
                            "estado": estado_actual,
                            "ubicacion": getattr(it, "ubicacion_nombre", "") or "---",
                            "cliente": getattr(it, "cliente_nombre", "") or "---",
                        },
                        destino={
                            "tipo": "ACTA",
                            "estado": estado_actual,
                            "ubicacion": getattr(it, "ubicacion_nombre", "") or "---",
                            "cliente": getattr(it, "cliente_nombre", "") or "---",
                            "recibe_user_id": recibe_user_id,
                            "recibe_nombre": recibe_nombre,
                        },
                        estado_anterior={"estado": estado_actual},
                        estado_nuevo={"estado": estado_actual},
                        ip_address=client_ip,
                        module_source="ACTA_ENTREGA_RECEPCION",
                        notes=notes_prefix,
                        ot_id=str(getattr(it, "ot_id", "") or ""),
                        previous_quantity=1,
                        new_quantity=1,
                        delta=0,
                    ).save()
            else:
                logger.warning("No se pudo registrar movimiento de ACTA: usuario responsable no resuelto")

            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = 'attachment; filename="acta_entrega_recepcion.pdf"'
            return response
        except Exception as ex:
            logger.exception("Error generando ACTA ENTREGA RECEPCION")
            return api_response(
                success=False,
                message=str(ex),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
