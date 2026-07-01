from rest_framework.views import APIView
from rest_framework import status
import logging

from config.apps.inventory.models.item import Item
from config.apps.inventory.serializers.item_serializer import ItemSerializer
from config.apps.users.permissions.rbac_permission import DRFRBACPermission
from config.apps.inventory.services.traceability_service import process_asset_transition
from config.utils.api_response import api_response

logger = logging.getLogger(__name__)


class ItemListCreateView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "item"

    def get(self, request):
        queryset = Item.objects(is_active=True)

        # filtro por estado
        estado = request.query_params.get("estado")
        if estado:
            queryset = queryset.filter(estado=estado)

        # filtro por tipo_item (herramienta / material / equipo / general)
        tipo_item = request.query_params.get("tipo_item")
        if tipo_item:
            queryset = queryset.filter(tipo_item=tipo_item)

        # filtro por subcategoría (ObjectId)
        subcategoria_id = request.query_params.get("subcategoria_id")
        if subcategoria_id:
            try:
                queryset = queryset.filter(subcategoria=subcategoria_id)
            except Exception:
                return api_response(
                    success=False,
                    message="ID de subcategoría inválido",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # búsqueda por nombre o código
        search = request.query_params.get("search", "").strip()
        if search:
            import re
            pattern = re.compile(re.escape(search), re.IGNORECASE)
            queryset = queryset.filter(
                __raw__={"$or": [
                    {"nombre": {"$regex": pattern.pattern, "$options": "i"}},
                    {"codigo": {"$regex": pattern.pattern, "$options": "i"}},
                ]}
            )

        # Paginación opcional (mantiene compatibilidad: si no viene page_size, devuelve lista completa)
        page_size_raw = request.query_params.get("page_size")
        if page_size_raw:
            try:
                page_size = max(1, min(200, int(page_size_raw)))
                page = max(1, int(request.query_params.get("page", 1)))
                offset = (page - 1) * page_size
                queryset = queryset.skip(offset).limit(page_size)
            except (TypeError, ValueError):
                pass

        # Optimiza la carga de referencias (subcategoria/categoria) para listados grandes.
        queryset = queryset.select_related(max_depth=2)

        serializer = ItemSerializer(queryset, many=True)
        return api_response(
            success=True,
            message="Items listados con éxito",
            data=serializer.data,
        )

    def post(self, request):
        serializer = ItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # 1. Crear el activo en estado INGRESO_BODEGA
            item = serializer.save(estado="INGRESO_BODEGA")

            # 2. Registrar el movimiento inicial: Ingreso a Bodega
            from config.apps.inventory.services.movement_service import registrarMovimiento
            
            registrarMovimiento(
                item_id=str(item.id),
                estado_anterior="---",
                estado_nuevo="INGRESO_BODEGA",
                usuario_id=str(request.user.id),
                observaciones="INGRESO INICIAL A SISTEMA"
            )

            # 3. Transición automática a STOCK
            updated_item = process_asset_transition(
                item=item,
                next_state="STOCK",
                user=request.user,
                ip_address=request.META.get("REMOTE_ADDR", ""),
                module_source="SISTEMA",
                notes="Activación a STOCK tras Ingreso a Bodega."
            )

            return api_response(
                success=True,
                message="Activo ingresado y disponible en STOCK",
                data=ItemSerializer(updated_item).data,
                status_code=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.exception("Error en el flujo de creación de ítem")
            error_msg = str(e) if "duplicate" in str(e).lower() else "No se pudo crear el ítem"
            return api_response(
                success=False,
                message=error_msg,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ItemDetailView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "item"

    def get(self, request, pk):
        try:
            item = Item.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de item inválido",
                status_code=status.HTTP_400_BAD_REQUEST
              )

        if not item:
            return api_response(
                success=False,
                message="Item no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = ItemSerializer(item)
        return api_response(
            success=True,
            message="Detalle de item obtenido",
            data=serializer.data
        )

    def put(self, request, pk):
        try:
            item = Item.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de item inválido",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if not item:
            return api_response(
                success=False,
                message="Item no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = ItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(
            success=True,
            message="Item actualizado con éxito",
            data=serializer.data
        )

    def delete(self, request, pk):
        try:
            item = Item.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de item inválido",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if not item:
            return api_response(
                success=False,
                message="Item no encontrado",
                status_code=status.HTTP_404_NOT_FOUND
            )

        item.is_active = False
        item.save()
        return api_response(
            success=True,
            message="Item eliminado correctamente"
        )


class ItemTransitionView(APIView):
    """
    Controla las transiciones de estado de un activo (Ciclo de Vida).
    ISO 9001 8.1 — Planificación y control operacional.
    """
    permission_classes = [DRFRBACPermission]
    resource_name = "item"

    def post(self, request, pk):
        try:
            item = Item.objects(id=pk, is_active=True).first()
            if not item:
                return api_response(
                    success=False,
                    message="Item no encontrado",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            next_state = request.data.get("next_state")
            ot_id = request.data.get("ot_id")
            notes = request.data.get("notes", "")

            if not next_state:
                return api_response(
                    success=False,
                    message="El campo 'next_state' es obligatorio",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Ejecutar transición a través del servicio de trazabilidad (MÁQUINA DE ESTADOS)
            updated_item = process_asset_transition(
                item=item,
                next_state=next_state,
                user=request.user,
                ot_id=ot_id,
                notes=notes,
                ip_address=request.META.get("REMOTE_ADDR", ""),
                module_source="FRONTEND_V4"
            )

            serializer = ItemSerializer(updated_item)
            return api_response(
                success=True,
                message=f"Estado del activo actualizado a '{updated_item.estado}'",
                data=serializer.data
            )

        except ValueError as e:
            return api_response(
                success=False,
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception("Error en transición de activo")
            return api_response(
                success=False,
                message=f"Error interno: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
