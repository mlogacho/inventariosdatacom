from rest_framework.views import APIView
from rest_framework import status

from config.apps.inventory.models.store import Store
from config.apps.inventory.serializers.store_serializer import StoreSerializer
from config.apps.inventory.services.inventory_scope_service import (
    ALLOWED_STORE_NAMES,
    get_allowed_stores_queryset,
    is_allowed_store_name,
)
from config.apps.users.permissions.rbac_permission import DRFRBACPermission
from config.utils.api_response import api_response


class StoreListCreateView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "store"

    def get(self, request):
        stores = get_allowed_stores_queryset()
        serializer = StoreSerializer(stores, many=True)
        return api_response(
            success=True,
            message="Bodegas listadas con éxito",
            data=serializer.data
        )

    def post(self, request):
        requested_name = (request.data or {}).get("nombre_bodega", "")
        if not is_allowed_store_name(requested_name):
            return api_response(
                success=False,
                message=(
                    "Solo se permiten las bodegas operativas: "
                    "Bodega General Conocoto y Mini Bodega Cumbaya."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = StoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
            return api_response(
                success=True,
                message="Bodega creada con éxito",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED
            )
        except Exception as e:
            error_msg = str(e) if "duplicate" in str(e).lower() else "No se pudo crear la bodega"
            return api_response(
                success=False,
                message=error_msg,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StoreDetailView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "store"

    def get(self, request, pk):
        try:
            store = Store.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de bodega inválido",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if not store:
            return api_response(
                success=False,
                message="Bodega no encontrada",
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = StoreSerializer(store)
        return api_response(
            success=True,
            message="Detalle de bodega obtenido",
            data=serializer.data
        )

    def put(self, request, pk):
        try:
            store = Store.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de bodega inválido",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if not store:
            return api_response(
                success=False,
                message="Bodega no encontrada",
                status_code=status.HTTP_404_NOT_FOUND
            )

        requested_name = (request.data or {}).get("nombre_bodega", store.nombre_bodega)
        if not is_allowed_store_name(requested_name):
            return api_response(
                success=False,
                message=(
                    "No se puede renombrar fuera del alcance. "
                    "Bodegas permitidas: Bodega General Conocoto y Mini Bodega Cumbaya."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = StoreSerializer(store, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(
            success=True,
            message="Bodega actualizada con éxito",
            data=serializer.data
        )

    def delete(self, request, pk):
        try:
            store = Store.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de bodega inválido",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if not store:
            return api_response(
                success=False,
                message="Bodega no encontrada",
                status_code=status.HTTP_404_NOT_FOUND
            )

        if store.nombre_bodega in ALLOWED_STORE_NAMES:
            return api_response(
                success=False,
                message="No se puede eliminar una bodega operativa del alcance de inventarios.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        store.is_active = False
        store.save()
        return api_response(
            success=True,
            message="Bodega eliminada correctamente"
        )
