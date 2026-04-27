"""
Vistas de proveedores.

ISO 9001 10.2 — Respuestas de error estructuradas y consistentes.
V-H1 Fix: Migrar de Response() directo a api_response() estándar.
"""
from rest_framework.views import APIView
from rest_framework import status

from config.apps.inventory.models.supplier import Supplier
from config.apps.inventory.serializers.supplier_serializer import SupplierSerializer
from config.apps.users.permissions.rbac_permission import DRFRBACPermission
from config.utils.api_response import api_response


class SupplierListCreateView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "supplier"

    def get(self, request):
        suppliers = Supplier.objects(is_active=True)
        serializer = SupplierSerializer(suppliers, many=True)
        return api_response(
            success=True,
            message="Proveedores listados con éxito",
            data=serializer.data,
        )

    def post(self, request):
        serializer = SupplierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
            return api_response(
                success=True,
                message="Proveedor creado con éxito",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            error_msg = str(e) if "duplicate" in str(e).lower() else "No se pudo crear el proveedor"
            return api_response(
                success=False,
                message=error_msg,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SupplierDetailView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "supplier"

    def get(self, request, pk):
        try:
            supplier = Supplier.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de proveedor inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not supplier:
            return api_response(
                success=False,
                message="Proveedor no encontrado",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = SupplierSerializer(supplier)
        return api_response(
            success=True,
            message="Detalle de proveedor obtenido",
            data=serializer.data,
        )

    def put(self, request, pk):
        try:
            supplier = Supplier.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de proveedor inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not supplier:
            return api_response(
                success=False,
                message="Proveedor no encontrado",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = SupplierSerializer(supplier, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(
            success=True,
            message="Proveedor actualizado con éxito",
            data=serializer.data,
        )

    def delete(self, request, pk):
        try:
            supplier = Supplier.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de proveedor inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not supplier:
            return api_response(
                success=False,
                message="Proveedor no encontrado",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        supplier.is_active = False
        supplier.save()
        return api_response(
            success=True,
            message="Proveedor eliminado correctamente",
        )
