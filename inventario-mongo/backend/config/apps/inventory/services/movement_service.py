from datetime import datetime, timezone
import logging
from config.apps.inventory.models.movement import Movement, OperationType

logger = logging.getLogger(__name__)


def registrarMovimiento(
    item_id,
    estado_anterior,
    estado_nuevo,
    usuario_id,
    observaciones="",
    instalacion_id=None,
    op_type_override=None,
    module_source="API",
):
    """
    Registra un movimiento de inventario (append-only).

    op_type_override permite que traceability_service pase el tipo ya
    calculado; si es None se infiere aquí para retrocompatibilidad.
    """
    if op_type_override:
        op_type = op_type_override
    else:
        op_type = _infer_op_type(estado_anterior, estado_nuevo)

    origen         = {"estado": estado_anterior, "ot_id": instalacion_id or "---"}
    destino        = {"estado": estado_nuevo,    "ot_id": instalacion_id or "---"}
    estado_ant_dict = {"estado": estado_anterior}
    estado_nue_dict = {"estado": estado_nuevo}

    try:
        movement = Movement(
            item=item_id,
            tipo_movimiento=op_type,
            fecha=datetime.now(timezone.utc),
            responsable=usuario_id,
            origen=origen,
            destino=destino,
            estado_anterior=estado_ant_dict,
            estado_nuevo=estado_nue_dict,
            notes=observaciones,
            ot_id=instalacion_id,
            module_source=module_source,
        )
        movement.save()
        return movement
    except Exception as e:
        logger.error("Error al registrar movimiento: %s", str(e))
        raise


def _infer_op_type(estado_anterior: str, estado_nuevo: str) -> str:
    """Inferencia de tipo de operación para retrocompatibilidad."""
    if estado_nuevo == "STOCK" and estado_anterior in (
        "REINGRESO_BODEGA", "INGRESO_BODEGA", "---"
    ):
        return OperationType.ENTRADA
    if estado_nuevo in ("RESERVADO", "RESERVADA"):
        return OperationType.RESERVA
    if estado_nuevo == "INSTALADO_CLIENTE":
        return OperationType.INSTALACION
    if estado_nuevo == "DEVOLUCION_PROVEEDOR":
        return OperationType.SALIDA
    if estado_nuevo in ("OBSOLETO", "OBSOLETA"):
        return OperationType.BAJA
    if estado_nuevo == "REINGRESO_BODEGA":
        return OperationType.RETORNO
    if estado_nuevo == "SALIDA_INSTALACION":
        return OperationType.SALIDA
    if estado_nuevo == "EN_USO":
        return OperationType.SALIDA_HERRAMIENTA
    if estado_nuevo in ("CONSUMIDO", "PARCIALMENTE_USADO"):
        return OperationType.CONSUMO
    if estado_nuevo == "STOCK" and estado_anterior in ("EN_USO", "EN_MANTENIMIENTO"):
        return OperationType.RETORNO_HERRAMIENTA
    if estado_nuevo == "STOCK" and estado_anterior == "PARCIALMENTE_USADO":
        return OperationType.RETORNO_PARCIAL
    return OperationType.AJUSTE
