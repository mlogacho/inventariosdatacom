"""
Vistas de vehículos.

ISO 9001 10.2 — Respuestas de error estructuradas y consistentes.
V-H1 Fix: Migrar de Response() directo a api_response() estándar.
"""
from rest_framework.views import APIView
from rest_framework import status

from config.apps.inventory.models.vehicle import Vehicle
from config.apps.inventory.serializers.vehicle_serializer import VehicleSerializer
from config.apps.users.permissions.rbac_permission import DRFRBACPermission
from config.utils.api_response import api_response


class VehicleListCreateView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "vehicle"

    def get(self, request):
        vehicles = Vehicle.objects(is_active=True)
        serializer = VehicleSerializer(vehicles, many=True)
        return api_response(
            success=True,
            message="Vehículos listados con éxito",
            data=serializer.data,
        )

    def post(self, request):
        serializer = VehicleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
            return api_response(
                success=True,
                message="Vehículo creado con éxito",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            error_msg = str(e) if "duplicate" in str(e).lower() else "No se pudo crear el vehículo"
            return api_response(
                success=False,
                message=error_msg,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VehicleDetailView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "vehicle"

    def get(self, request, pk):
        try:
            vehicle = Vehicle.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de vehículo inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not vehicle:
            return api_response(
                success=False,
                message="Vehículo no encontrado",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = VehicleSerializer(vehicle)
        return api_response(
            success=True,
            message="Detalle de vehículo obtenido",
            data=serializer.data,
        )

    def put(self, request, pk):
        try:
            vehicle = Vehicle.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de vehículo inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not vehicle:
            return api_response(
                success=False,
                message="Vehículo no encontrado",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = VehicleSerializer(vehicle, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(
            success=True,
            message="Vehículo actualizado con éxito",
            data=serializer.data,
        )

    def delete(self, request, pk):
        try:
            vehicle = Vehicle.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de vehículo inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not vehicle:
            return api_response(
                success=False,
                message="Vehículo no encontrado",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        vehicle.is_active = False
        vehicle.save()
        return api_response(
            success=True,
            message="Vehículo eliminado correctamente",
        )
