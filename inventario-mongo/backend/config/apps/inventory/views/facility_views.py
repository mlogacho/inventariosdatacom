"""
Vistas de instalaciones (facilities).

ISO 9001 10.2 — Manejo de errores consistente.
ISO 27001 A.12.4.1 — Trazabilidad de operaciones.
"""
from rest_framework.views import APIView
from rest_framework import status
import logging
from datetime import datetime, timezone

from config.apps.inventory.models.facility import Facility
from config.apps.inventory.serializers.facility_serializer import FacilitySerializer
from config.apps.inventory.services.facility_service import (
    soft_delete_facility,
    validate_facility_transition,
    ALLOWED_FACILITY_STATES,
)
from config.apps.users.permissions.rbac_permission import DRFRBACPermission
from config.apps.users.models.user import User
from config.apps.inventory.models.item import Item
from config.apps.inventory.models.vehicle import Vehicle
from config.utils.api_response import api_response
from config.utils.transaction_manager import mongo_transaction
from config.apps.inventory.services.traceability_service import (
    sync_facility_assets,
    sync_facility_tools,
    sync_facility_materials,
    process_asset_transition,
    AssetStateMachine,
)

logger = logging.getLogger(__name__)


def _get_client_ip(request) -> str:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class FacilityListCreateView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "facility"

    def get(self, request):
        queryset = Facility.objects(is_active=True)

        estado = request.query_params.get("estado")
        if estado:
            if estado not in ALLOWED_FACILITY_STATES:
                return api_response(
                    success=False,
                    message=f"Estado inválido. Valores permitidos: {', '.join(ALLOWED_FACILITY_STATES)}",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(estado=estado)

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(codigo_instalacion__icontains=search)

        tecnico_id = request.query_params.get("tecnico_id")
        if tecnico_id:
            try:
                tecnico = User.objects(id=tecnico_id, is_active=True).first()
            except Exception:
                return api_response(
                    success=False,
                    message="ID de técnico inválido",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            if not tecnico:
                return api_response(
                    success=False,
                    message="Técnico no encontrado",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            queryset = queryset.filter(tecnico=tecnico)

        serializer = FacilitySerializer(queryset, many=True)
        return api_response(
            success=True,
            message="Instalaciones listadas con éxito",
            data=serializer.data,
        )

    @mongo_transaction()
    def post(self, request):
        serializer = FacilitySerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                success=False,
                message="Error de validación",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            facility = serializer.save()
            ip = _get_client_ip(request)

            sync_facility_assets(
                facility=facility, 
                next_facility_status="planificada", 
                user=request.user, 
                ip_address=ip
            )
            sync_facility_tools(
                facility=facility, 
                next_facility_status="planificada", 
                user=request.user, 
                ip_address=ip
            )
            sync_facility_materials(
                facility=facility, 
                next_facility_status="planificada", 
                user=request.user, 
                ip_address=ip
            )

            return api_response(
                success=True,
                message="Instalación creada y recursos reservados exitosamente",
                data=FacilitySerializer(facility).data,
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            # La transacción se revierte automáticamente gracias al decorador
            return api_response(
                success=False,
                message=f"No se pudo completar la operación: {str(e)}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )


class FacilityDetailView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "facility"

    @mongo_transaction()
    def get(self, request, pk):
        try:
            facility = Facility.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de instalación inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not facility:
            return api_response(
                success=False,
                message="Instalación no encontrada",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # --- AUTO-DISCOVERY de ítems por OT (ISO 9001 Trazabilidad) ---
        # Si un ítem se vinculó externamente a esta OT, lo integramos automáticamente.
        discovered = Item.objects(ot_id=facility.codigo_instalacion, is_active=True)
        existing_ids = {str(it.get("item_id")) for it in facility.items_planificados}
        existing_ids.update({str(h.get("item_id")) for h in facility.herramientas})
        existing_ids.update({str(c.get("item_id")) for c in facility.consumibles})

        modified = False
        for di in discovered:
            iid = str(di.id)
            if iid not in existing_ids:
                if di.tipo_item == "equipo":
                    facility.items_planificados.append({"item_id": iid, "destino_final": "cliente"})
                    modified = True
                elif di.tipo_item == "herramienta":
                    facility.herramientas.append({"item_id": iid, "cantidad": 1})
                    modified = True
                elif di.tipo_item == "material":
                    facility.consumibles.append({"item_id": iid, "cantidad": 1, "cantidad_reservada": 1})
                    modified = True
                existing_ids.add(iid)

        if modified:
            facility.save()

        data = FacilitySerializer(facility).data

        # Enriquecer ítems planificados con datos actuales del ítem
        enriched_items = []
        for it in facility.items_planificados:
            try:
                item_obj = Item.objects(id=it.get("item_id")).first()
                if item_obj:
                    enriched_items.append({
                        "item_id": str(item_obj.id),
                        "item": {
                            "id": str(item_obj.id),
                            "nombre": item_obj.nombre,
                            "codigo": item_obj.codigo,
                            "serial": getattr(item_obj, "serial", "—"),
                            "estado": item_obj.estado,
                            "categoria": item_obj.subcategoria.categoria.nombre_categoria if item_obj.subcategoria and item_obj.subcategoria.categoria else "—",
                        },
                        "store_id": it.get("store_id"),
                        "destino_final": it.get("destino_final", "cliente"),
                    })
            except Exception:
                logger.warning("Error enriqueciendo ítem en facility %s", pk)
                enriched_items.append(it)

        data["items_planificados"] = enriched_items

        # Enriquecer herramientas
        enriched_tools = []
        for h in (facility.herramientas or []):
            try:
                item_obj = Item.objects(id=h.get("item_id")).first()
                if item_obj:
                    enriched_tools.append({
                        "item_id": str(item_obj.id),
                        "nombre": item_obj.nombre,
                        "codigo": item_obj.codigo,
                        "cantidad": h.get("cantidad", 1),
                        "estado": item_obj.estado,
                    })
                else:
                    enriched_tools.append(h)
            except Exception:
                enriched_tools.append(h)
        data["herramientas"] = enriched_tools

        # Enriquecer consumibles
        enriched_cons = []
        for c in (facility.consumibles or []):
            try:
                item_obj = Item.objects(id=c.get("item_id")).first()
                if item_obj:
                    enriched_cons.append({
                        "item_id": str(item_obj.id),
                        "nombre": item_obj.nombre,
                        "codigo": item_obj.codigo,
                        "cantidad": c.get("cantidad_reservada") or c.get("cantidad", 1),
                        "unidad": getattr(item_obj, "unidad", c.get("unidad", "unidad")),
                    })
                else:
                    enriched_cons.append(c)
            except Exception:
                enriched_cons.append(c)
        data["consumibles"] = enriched_cons

        # Enriquecer vehículo
        if facility.vehiculo_id:
            try:
                v = Vehicle.objects(id=facility.vehiculo_id).first()
                if v:
                    data["vehiculo"] = {
                        "id": str(v.id),
                        "placa": v.placa,
                        "marca": getattr(v, "marca", ""),
                        "modelo": getattr(v, "modelo", ""),
                    }
            except Exception:
                pass

        return api_response(
            success=True,
            message="Detalle de instalación obtenido",
            data=data,
        )

    @mongo_transaction()
    def put(self, request, pk):
        try:
            facility = Facility.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de instalación inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not facility:
            return api_response(
                success=False,
                message="Instalación no encontrada",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Instalaciones finalizadas/canceladas solo permiten actualizar observaciones
        if facility.estado in ("finalizada", "cancelada"):
            restricted_keys = set(request.data.keys()) - {
                "observaciones", "items_planificados", "herramientas", "consumibles"
            }
            if restricted_keys:
                return api_response(
                    success=False,
                    message=f"Una instalación '{facility.estado}' solo permite actualizar observaciones.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        serializer = FacilitySerializer(facility, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Sincronización automática de recursos añadidos/modificados
        if facility.estado in ("planificada", "en_proceso"):
            try:
                ip = _get_client_ip(request)
                sync_facility_assets(facility=facility, next_facility_status=facility.estado, user=request.user, ip_address=ip)
                sync_facility_tools(facility=facility, next_facility_status=facility.estado, user=request.user, ip_address=ip)
                sync_facility_materials(facility=facility, next_facility_status=facility.estado, user=request.user, ip_address=ip)
            except Exception as sync_err:
                logger.error(f"Error en sync automático post-update: {sync_err}")

        return api_response(
            success=True,
            message="Instalación actualizada y recursos sincronizados",
            data=FacilitySerializer(facility).data,
        )

    @mongo_transaction()
    def delete(self, request, pk):
        try:
            facility = Facility.objects(id=pk, is_active=True).first()
        except Exception:
            return api_response(
                success=False,
                message="ID de instalación inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not facility:
            return api_response(
                success=False,
                message="Instalación no encontrada",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # ── LIBERACIÓN DE RECURSOS ───────────────────────────────────────────
        # Al eliminar una instalación activa, devolvemos todo al STOCK.
        try:
            ip = _get_client_ip(request)
            sync_facility_assets(facility=facility, next_facility_status="cancelada", user=request.user, ip_address=ip)
            sync_facility_tools(facility=facility, next_facility_status="cancelada", user=request.user, ip_address=ip)
            sync_facility_materials(facility=facility, next_facility_status="cancelada", user=request.user, ip_address=ip)
        except Exception as e:
            logger.error(f"Error liberando recursos al eliminar instalación {pk}: {str(e)}")
            # Continuamos con el borrado aunque falle la liberación? 
            # Mejor no, para mantener integridad.
            return api_response(
                success=False,
                message=f"No se pudo liberar el inventario: {str(e)}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        soft_delete_facility(facility)
        return api_response(
            success=True,
            message="Instalación eliminada y recursos devueltos a STOCK",
        )


class FacilityStartView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "facility"

    @mongo_transaction()
    def post(self, request, pk):
        try:
            facility = Facility.objects(id=pk, is_active=True).first()
            if not facility:
                return api_response(
                    success=False,
                    message="Instalación no encontrada",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            validate_facility_transition(facility.estado, "en_proceso")

            ip = _get_client_ip(request)
            sync_facility_assets(
                facility=facility,
                next_facility_status="en_proceso",
                user=request.user,
                ip_address=ip,
            )
            # Herramientas: RESERVADA → EN_USO
            sync_facility_tools(
                facility=facility,
                next_facility_status="en_proceso",
                user=request.user,
                ip_address=ip,
            )

            facility.estado = "en_proceso"
            facility.fecha_inicio = datetime.now(timezone.utc)
            facility.save()

            return api_response(
                success=True,
                message="Instalación iniciada. Ítems en SALIDA A INSTALACIÓN.",
                data={"estado": facility.estado},
            )
        except ValueError as ve:
            return api_response(
                success=False,
                message=str(ve),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("Error al iniciar instalación %s", pk)
            return api_response(
                success=False,
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FacilityFinishView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "facility"

    def post(self, request, pk):
        try:
            facility = Facility.objects(id=pk, is_active=True).first()
            if not facility:
                return api_response(
                    success=False,
                    message="Instalación no encontrada",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            validate_facility_transition(facility.estado, "finalizada")

            # Destinos: [{item_id, destino: "cliente"|"bodega"}, ...]
            item_destinations = request.data.get("items_planificados", [])

            sync_facility_assets(
                facility=facility,
                next_facility_status="finalizada",
                user=request.user,
                ip_address=_get_client_ip(request),
                item_destinations=item_destinations,
            )

            facility.estado = "finalizada"
            facility.fecha_fin = datetime.now(timezone.utc)

            # Persistir destinos finales para el reporte PDF
            for it_record in facility.items_planificados:
                d_match = next(
                    (d for d in item_destinations
                     if str(d.get("item_id")) == str(it_record.get("item_id"))),
                    None,
                )
                if d_match:
                    it_record["destino_final"] = d_match.get("destino", "cliente")

            facility.save()

            return api_response(
                success=True,
                message="Instalación finalizada. Ítems actualizados según destino.",
            )
        except ValueError as ve:
            return api_response(
                success=False,
                message=str(ve),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("Error al finalizar instalación %s", pk)
            return api_response(
                success=False,
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FacilityCancelView(APIView):
    permission_classes = [DRFRBACPermission]
    resource_name = "facility"

    @mongo_transaction()
    def post(self, request, pk):
        try:
            facility = Facility.objects(id=pk, is_active=True).first()
            if not facility:
                return api_response(
                    success=False,
                    message="Instalación no encontrada",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            validate_facility_transition(facility.estado, "cancelada")

            ip = _get_client_ip(request)
            sync_facility_assets(
                facility=facility,
                next_facility_status="cancelada",
                user=request.user,
                ip_address=ip,
            )
            sync_facility_tools(
                facility=facility,
                next_facility_status="cancelada",
                user=request.user,
                ip_address=ip,
            )
            sync_facility_materials(
                facility=facility,
                next_facility_status="cancelada",
                user=request.user,
                ip_address=ip,
            )

            facility.estado = "cancelada"
            facility.save()

            return api_response(
                success=True,
                message="Instalación cancelada. Ítems retornados a STOCK.",
            )
        except ValueError as ve:
            return api_response(
                success=False,
                message=str(ve),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("Error al cancelar instalación %s", pk)
            return api_response(
                success=False,
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FacilityUpdateDestinationsView(APIView):
    """Actualiza los destinos finales de los ítems durante EN_PROCESO (auto-save)."""

    permission_classes = [DRFRBACPermission]
    resource_name = "facility"

    @mongo_transaction()
    def patch(self, request, pk):
        try:
            facility = Facility.objects(id=pk, is_active=True).first()
            if not facility:
                return api_response(
                    success=False,
                    message="Instalación no encontrada",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            if facility.estado != "en_proceso":
                return api_response(
                    success=False,
                    message="Solo se pueden actualizar destinos cuando la instalación está EN PROCESO.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            destinations = request.data.get("destinations", [])

            for it_record in facility.items_planificados:
                d_match = next(
                    (d for d in destinations
                     if str(d.get("item_id")) == str(it_record.get("item_id"))),
                    None,
                )
                if d_match:
                    valid = d_match.get("destino", "cliente")
                    if valid not in ("cliente", "bodega"):
                        valid = "cliente"
                    it_record["destino_final"] = valid

            facility.save()
            return api_response(
                success=True,
                message="Destinos actualizados",
                data={"updated": len(destinations)},
            )

        except Exception as e:
            logger.exception("Error al actualizar destinos de instalación %s", pk)
            return api_response(
                success=False,
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FacilityMovementsView(APIView):
    """Lista todos los movimientos generados por una instalación (por ot_id)."""

    permission_classes = [DRFRBACPermission]
    resource_name = "movement"

    def get(self, request, pk):
        try:
            facility = Facility.objects(id=pk, is_active=True).first()
            if not facility:
                return api_response(
                    success=False,
                    message="Instalación no encontrada",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            from config.apps.inventory.models.movement import Movement
            from config.apps.inventory.serializers.movement_serializer import MovementSerializer

            # Filtramos estrictamente por el código de instalación (OT)
            # Esto asegura que solo vemos los movimientos que fueron parte de este servicio
            queryset = Movement.objects(
                ot_id=facility.codigo_instalacion
            ).order_by("-fecha")
            
            serializer = MovementSerializer(queryset, many=True)
            return api_response(
                success=True,
                message=f"Movimientos de la instalación {facility.codigo_instalacion}",
                data=serializer.data,
            )

        except Exception as e:
            logger.exception("Error al listar movimientos de instalación %s", pk)
            return api_response(
                success=False,
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FacilityReportView(APIView):
    """Genera reporte PDF profesional de la instalación."""

    permission_classes = [DRFRBACPermission]
    resource_name = "facility"

    def get(self, request, pk):
        try:
            facility = Facility.objects(id=pk, is_active=True).first()
            if not facility:
                return api_response(
                    success=False,
                    message="Instalación no encontrada",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            if facility.estado != "finalizada":
                return api_response(
                    success=False,
                    message="El reporte solo está disponible para instalaciones finalizadas.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            from config.apps.inventory.services.report_service import generate_facility_pdf
            from django.http import HttpResponse

            pdf_bytes = generate_facility_pdf(facility)
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = (
                f'attachment; filename="instalacion_{facility.codigo_instalacion}.pdf"'
            )
            return response

        except ImportError:
            return api_response(
                success=False,
                message="El módulo de reportes no está disponible.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Error generando PDF de instalación %s", pk)
            return api_response(
                success=False,
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FacilityCloseView(APIView):
    """
    Cierre completo de instalación (reemplaza el flujo simple de /finish/).

    Payload esperado:
    {
        "items_planificados": [{"item_id": "...", "destino": "cliente|bodega"}],
        "herramientas_cierre": [
            {
                "item_id": "...",
                "retorno": true,
                "estado_retorno": "STOCK|EN_MANTENIMIENTO",
                "bodega_destino_id": "...",   // opcional
                "observaciones": ""
            }
        ],
        "consumibles_cierre": [
            {
                "item_id": "...",
                "cantidad_usada": 3,
                "bodega_retorno_id": ""       // opcional
            }
        ]
    }
    """

    permission_classes = [DRFRBACPermission]
    resource_name = "facility"

    @mongo_transaction()
    def post(self, request, pk):
        try:
            facility = Facility.objects(id=pk, is_active=True).first()
            if not facility:
                return api_response(
                    success=False,
                    message="Instalación no encontrada",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            validate_facility_transition(facility.estado, "finalizada")

            ip                  = _get_client_ip(request)
            item_destinations   = request.data.get("items_planificados", [])
            herramientas_cierre = request.data.get("herramientas_cierre", [])
            consumibles_cierre  = request.data.get("consumibles_cierre", [])

            # ── Validar que todas las herramientas tienen info de cierre ─────
            tool_ids_requeridos = {
                str(h.get("item_id")) for h in facility.herramientas if h.get("item_id")
            }
            tool_ids_provistos = {str(h.get("item_id")) for h in herramientas_cierre}
            faltantes_herr = tool_ids_requeridos - tool_ids_provistos
            if faltantes_herr:
                return api_response(
                    success=False,
                    message=f"Faltan datos de retorno para herramientas: {faltantes_herr}",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # ── Validar que todos los materiales tienen cantidad_usada ───────
            cons_ids_requeridos = {
                str(c.get("item_id")) for c in facility.consumibles if c.get("item_id")
            }
            for cierre in consumibles_cierre:
                if cierre.get("cantidad_usada") is None:
                    return api_response(
                        success=False,
                        message=f"Falta 'cantidad_usada' para material {cierre.get('item_id')}",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
            cons_ids_provistos = {str(c.get("item_id")) for c in consumibles_cierre}
            faltantes_cons = cons_ids_requeridos - cons_ids_provistos
            if faltantes_cons:
                return api_response(
                    success=False,
                    message=f"Faltan datos de liquidación para materiales: {faltantes_cons}",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # ── 1. Equipos (flujo original) ───────────────────────────────────
            sync_facility_assets(
                facility=facility,
                next_facility_status="finalizada",
                user=request.user,
                ip_address=ip,
                item_destinations=item_destinations,
            )
            for it_record in facility.items_planificados:
                d_match = next(
                    (d for d in item_destinations
                     if str(d.get("item_id")) == str(it_record.get("item_id"))),
                    None,
                )
                if d_match:
                    it_record["destino_final"] = d_match.get("destino", "cliente")

            # ── 2. Herramientas — retorno obligatorio ─────────────────────────
            for cierre in herramientas_cierre:
                item_id      = cierre.get("item_id")
                retorno      = cierre.get("retorno", True)
                estado_ret   = cierre.get("estado_retorno", "STOCK")
                observaciones = cierre.get("observaciones", "")

                item_obj = Item.objects(id=item_id, tipo_item="herramienta").first()
                if not item_obj:
                    logger.warning("Herramienta %s no encontrada al cerrar.", item_id)
                    continue

                if not retorno:
                    # Alerta de discrepancia — se deja en EN_USO con nota
                    logger.warning(
                        "DISCREPANCIA: Herramienta %s NO retornó en instalación %s. Obs: %s",
                        item_obj.codigo, facility.codigo_instalacion, observaciones,
                    )
                    # Actualizar observaciones en facility para el reporte
                    for herr in facility.herramientas:
                        if str(herr.get("item_id")) == str(item_id):
                            herr["retorno_registrado"] = False
                            herr["observaciones_retorno"] = f"NO RETORNÓ: {observaciones}"
                    continue

                if estado_ret not in ("STOCK", "EN_MANTENIMIENTO"):
                    estado_ret = "STOCK"

                current = item_obj.estado or "EN_USO"
                if AssetStateMachine.is_transition_allowed(current, estado_ret, "herramienta"):
                    process_asset_transition(
                        item=item_obj,
                        next_state=estado_ret,
                        user=request.user,
                        ot_id=None,
                        notes=f"Retorno al cerrar instalación {facility.codigo_instalacion}. {observaciones}",
                        ip_address=ip,
                        module_source="CIERRE_INSTALACION",
                    )

                for herr in facility.herramientas:
                    if str(herr.get("item_id")) == str(item_id):
                        herr["retorno_registrado"] = True
                        herr["estado_retorno"]     = estado_ret
                        herr["observaciones_retorno"] = observaciones

            # ── 3. Materiales — liquidación parcial o total ───────────────────
            for cierre in consumibles_cierre:
                item_id       = cierre.get("item_id")
                cantidad_usada = int(cierre.get("cantidad_usada", 0))

                item_obj = Item.objects(id=item_id, tipo_item="material").first()
                if not item_obj:
                    logger.warning("Material %s no encontrado al cerrar.", item_id)
                    continue

                cantidad_reservada = 0
                for cons in facility.consumibles:
                    if str(cons.get("item_id")) == str(item_id):
                        cantidad_reservada = int(
                            cons.get("cantidad_reservada") or cons.get("cantidad") or 0
                        )
                        cons["cantidad_usada"] = cantidad_usada
                        break

                cantidad_retorno = max(0, cantidad_reservada - cantidad_usada)
                current = item_obj.estado or "RESERVADO"

                if cantidad_retorno == 0:
                    # Consumo total
                    new_stock = max(0, (item_obj.cantidad or 0))
                    target = "CONSUMIDO" if new_stock == 0 else "STOCK"
                    if AssetStateMachine.is_transition_allowed(current, target, "material"):
                        process_asset_transition(
                            item=item_obj,
                            next_state=target,
                            user=request.user,
                            ot_id=None,
                            notes=f"Consumo total en instalación {facility.codigo_instalacion}.",
                            ip_address=ip,
                            module_source="CIERRE_INSTALACION",
                            cantidad_delta=-cantidad_usada,
                        )
                else:
                    # Consumo parcial — material pasa a PARCIALMENTE_USADO
                    # y auto-transiciona a STOCK tras registrar retorno
                    if AssetStateMachine.is_transition_allowed(current, "PARCIALMENTE_USADO", "material"):
                        process_asset_transition(
                            item=item_obj,
                            next_state="PARCIALMENTE_USADO",
                            user=request.user,
                            ot_id=None,
                            notes=(
                                f"Uso parcial en instalación {facility.codigo_instalacion}. "
                                f"Usado: {cantidad_usada}, retorno: {cantidad_retorno}."
                            ),
                            ip_address=ip,
                            module_source="CIERRE_INSTALACION",
                            cantidad_delta=cantidad_retorno - cantidad_reservada,
                        )

            # ── 4. Cerrar instalación ─────────────────────────────────────────
            facility.estado   = "finalizada"
            facility.fecha_fin = datetime.now(timezone.utc)
            facility.save()

            return api_response(
                success=True,
                message="Instalación cerrada. Herramientas y materiales liquidados.",
            )

        except ValueError as ve:
            return api_response(
                success=False,
                message=str(ve),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("Error al cerrar instalación %s", pk)
            return api_response(
                success=False,
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
