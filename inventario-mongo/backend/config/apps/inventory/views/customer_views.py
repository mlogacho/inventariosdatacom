from rest_framework.views import APIView
from rest_framework import status

from config.apps.inventory.models.customer import Customer
from config.apps.inventory.serializers.customer_serializer import CustomerSerializer
from config.apps.users.permissions.rbac_permission import DRFRBACPermission
from config.utils.api_response import api_response


class CustomerListCreateView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "customer"

    def get(self, request):
        customers = Customer.objects(is_active=True)
        serializer = CustomerSerializer(customers, many=True)
        return api_response(
            success=True,
            message="Clientes listados con éxito",
            data=serializer.data
        )

    def post(self, request):
        serializer = CustomerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
            return api_response(
                success=True,
                message="Cliente creado con éxito",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED
            )
        except Exception as e:
            error_msg = str(e) if "duplicate" in str(e).lower() else "No se pudo crear el cliente"
            return api_response(
                success=False,
                message=error_msg,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CustomerDetailView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "customer"

    def get(self, request, pk):
        try:
            customer = Customer.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(success=False, message="ID de cliente inválido", status_code=status.HTTP_400_BAD_REQUEST)

        if not customer:
            return api_response(success=False, message="Cliente no encontrado", status_code=status.HTTP_404_NOT_FOUND)

        serializer = CustomerSerializer(customer)
        return api_response(success=True, message="Detalle de cliente obtenido", data=serializer.data)

    def put(self, request, pk):
        try:
            customer = Customer.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(success=False, message="ID de cliente inválido", status_code=status.HTTP_400_BAD_REQUEST)

        if not customer:
            return api_response(success=False, message="Cliente no encontrado", status_code=status.HTTP_404_NOT_FOUND)

        serializer = CustomerSerializer(customer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(success=True, message="Cliente actualizado con éxito", data=serializer.data)

    def delete(self, request, pk):
        try:
            customer = Customer.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(success=False, message="ID de cliente inválido", status_code=status.HTTP_400_BAD_REQUEST)

        if not customer:
            return api_response(success=False, message="Cliente no encontrado", status_code=status.HTTP_404_NOT_FOUND)

        customer.is_active = False
        customer.save()
        return api_response(success=True, message="Cliente eliminado correctamente")

