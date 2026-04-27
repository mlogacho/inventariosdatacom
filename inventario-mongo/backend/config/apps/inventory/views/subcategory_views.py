"""
Vistas de subcategorías.

ISO 9001 10.2 — Respuestas de error estructuradas y consistentes.
V-H1 Fix: Migrar de Response() directo a api_response() estándar.
"""
from rest_framework.views import APIView
from rest_framework import status

from config.apps.inventory.models.subcategory import SubCategory
from config.apps.inventory.serializers.subcategory_serializer import SubCategorySerializer
from config.apps.users.permissions.rbac_permission import DRFRBACPermission
from config.utils.api_response import api_response


class SubCategoryListCreateView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "subcategory"

    def get(self, request):
        queryset = SubCategory.objects(is_active=True)

        category_id = request.query_params.get("category_id") or request.query_params.get("categoria_id")
        if category_id:
            try:
                queryset = queryset.filter(categoria=category_id)
            except Exception:
                return api_response(
                    success=False,
                    message="ID de categoría inválido",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        serializer = SubCategorySerializer(queryset, many=True)
        return api_response(
            success=True,
            message="Subcategorías listadas con éxito",
            data=serializer.data,
        )

    def post(self, request):
        serializer = SubCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
            return api_response(
                success=True,
                message="Subcategoría creada con éxito",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            error_msg = str(e) if "duplicate" in str(e).lower() else "No se pudo crear la subcategoría"
            return api_response(
                success=False,
                message=error_msg,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SubCategoryDetailView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "subcategory"

    def get(self, request, pk):
        try:
            sub = SubCategory.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de subcategoría inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not sub:
            return api_response(
                success=False,
                message="Subcategoría no encontrada",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubCategorySerializer(sub)
        return api_response(
            success=True,
            message="Detalle de subcategoría obtenido",
            data=serializer.data,
        )

    def put(self, request, pk):
        try:
            sub = SubCategory.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de subcategoría inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not sub:
            return api_response(
                success=False,
                message="Subcategoría no encontrada",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubCategorySerializer(sub, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(
            success=True,
            message="Subcategoría actualizada con éxito",
            data=serializer.data,
        )

    def delete(self, request, pk):
        try:
            sub = SubCategory.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de subcategoría inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not sub:
            return api_response(
                success=False,
                message="Subcategoría no encontrada",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        sub.is_active = False
        sub.save()
        return api_response(
            success=True,
            message="Subcategoría eliminada correctamente",
        )
