"""
Vistas de categorías.

ISO 9001 10.2 — Respuestas de error estructuradas y consistentes.
V-H1 Fix: Migrar de Response() directo a api_response() estándar.
V-H2 Fix: Agregar manejo de IDs inválidos con try/except.
"""
from rest_framework.views import APIView
from rest_framework import status

from config.apps.inventory.models.category import Category
from config.apps.inventory.serializers.category_serializer import CategorySerializer
from config.apps.users.permissions.rbac_permission import DRFRBACPermission
from config.utils.api_response import api_response


class CategoryListCreateView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "category"

    def get(self, request):
        categories = Category.objects(is_active=True)
        serializer = CategorySerializer(categories, many=True)
        return api_response(
            success=True,
            message="Categorías listadas con éxito",
            data=serializer.data,
        )

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
            return api_response(
                success=True,
                message="Categoría creada con éxito",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            error_msg = str(e) if "duplicate" in str(e).lower() else "No se pudo crear la categoría"
            return api_response(
                success=False,
                message=error_msg,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CategoryDetailView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "category"

    def get(self, request, pk):
        try:
            category = Category.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de categoría inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not category:
            return api_response(
                success=False,
                message="Categoría no encontrada",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = CategorySerializer(category)
        return api_response(
            success=True,
            message="Detalle de categoría obtenido",
            data=serializer.data,
        )

    def put(self, request, pk):
        try:
            category = Category.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de categoría inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not category:
            return api_response(
                success=False,
                message="Categoría no encontrada",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = CategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(
            success=True,
            message="Categoría actualizada con éxito",
            data=serializer.data,
        )

    def delete(self, request, pk):
        try:
            category = Category.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de categoría inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not category:
            return api_response(
                success=False,
                message="Categoría no encontrada",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        category.is_active = False
        category.save()
        return api_response(
            success=True,
            message="Categoría eliminada correctamente",
        )
