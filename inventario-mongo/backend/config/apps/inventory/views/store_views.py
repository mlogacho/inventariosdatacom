from rest_framework.views import APIView
from rest_framework import status

from config.apps.inventory.models.store import Store
from config.apps.inventory.serializers.store_serializer import StoreSerializer
from config.apps.users.permissions.rbac_permission import DRFRBACPermission
from config.utils.api_response import api_response


class StoreListCreateView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "store"

    def get(self, request):
        stores = Store.objects(is_active=True)
        serializer = StoreSerializer(stores, many=True)
        return api_response(
            success=True,
            message="Bodegas listadas con éxito",
            data=serializer.data
        )

    def post(self, request):
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

        store.is_active = False
        store.save()
        return api_response(
            success=True,
            message="Bodega eliminada correctamente"
        )
