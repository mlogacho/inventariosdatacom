"""
Servicio de Trazabilidad y Ciclo de Vida.

State machine diferenciada por tipo_item:
  - equipo/general → flujo original (STOCK → RESERVADO → SALIDA_INSTALACION …)
  - herramienta    → STOCK → RESERVADA → EN_USO → STOCK/EN_MANTENIMIENTO
  - material       → STOCK → RESERVADO → CONSUMIDO/PARCIALMENTE_USADO → STOCK

ISO 9001 8.1 — Planificación y control operacional.
ISO 27001 A.12.4.1 — Registro de auditoría.
"""
import logging

from config.apps.inventory.models.item import Item
from config.apps.inventory.models.movement import OperationType
from config.apps.users.models.user import User

logger = logging.getLogger(__name__)


# ── Mapas de transiciones por tipo de ítem ───────────────────────────────────

_TRANSITIONS_EQUIPO = {
    "INGRESO_BODEGA":       ["STOCK"],
    "STOCK":                ["RESERVADO", "DEVOLUCION_PROVEEDOR", "OBSOLETO"],
    "RESERVADO":            ["SALIDA_INSTALACION", "STOCK"],
    "SALIDA_INSTALACION":   ["INSTALADO_CLIENTE", "REINGRESO_BODEGA", "RESERVADO"],
    "INSTALADO_CLIENTE":    ["REINGRESO_BODEGA", "ACTIVO_EN_CAMPO"],
    "REINGRESO_BODEGA":     ["STOCK"],
    "DEVOLUCION_PROVEEDOR": [],
    "OBSOLETO":             [],
    "ACTIVO_EN_CAMPO":      [],
}

_TRANSITIONS_HERRAMIENTA = {
    "STOCK":            ["RESERVADA", "EN_MANTENIMIENTO", "OBSOLETA"],
    "RESERVADA":        ["EN_USO", "STOCK"],      # STOCK al cancelar instalación
    "EN_USO":           ["STOCK", "EN_MANTENIMIENTO", "RESERVADA"],
    "EN_MANTENIMIENTO": ["STOCK", "OBSOLETA"],
    "OBSOLETA":         [],
}

_TRANSITIONS_MATERIAL = {
    "STOCK":              ["RESERVADO", "OBSOLETO"],
    "RESERVADO":          ["CONSUMIDO", "PARCIALMENTE_USADO", "STOCK"],
    "PARCIALMENTE_USADO": ["STOCK"],   # auto-transición tras liquidación
    "CONSUMIDO":          [],
    "OBSOLETO":           [],
}


class AssetStateMachine:

    @staticmethod
    def _map(tipo_item: str) -> dict:
        if tipo_item == "herramienta":
            return _TRANSITIONS_HERRAMIENTA
        if tipo_item == "material":
            return _TRANSITIONS_MATERIAL
        return _TRANSITIONS_EQUIPO   # equipo / general / None

    @staticmethod
    def is_transition_allowed(current_state: str, next_state: str, tipo_item: str = "equipo") -> bool:
        if current_state == next_state:
            return True
        allowed = AssetStateMachine._map(tipo_item).get(current_state, [])
        return next_state in allowed

    @staticmethod
    def auto_next(state: str) -> str | None:
        """Retorna el estado al que debe transicionar automáticamente, o None."""
        auto = {
            "INGRESO_BODEGA":     "STOCK",
            "REINGRESO_BODEGA":   "STOCK",
            "PARCIALMENTE_USADO": "STOCK",
        }
        return auto.get(state)
        
    @staticmethod
    def get_path(current: str, target: str, tipo: str) -> list:
        """Determina la ruta de estados necesaria para llegar al destino."""
        if current == target: return []
        
        # Caminos lineales comunes
        paths = {
            "equipo": {
                ("STOCK", "SALIDA_INSTALACION"): ["RESERVADO", "SALIDA_INSTALACION"],
                ("SALIDA_INSTALACION", "STOCK"): ["REINGRESO_BODEGA"], # auto-next a STOCK
            },
            "herramienta": {
                ("STOCK", "EN_USO"): ["RESERVADA", "EN_USO"],
            }
        }
        
        return paths.get(tipo, {}).get((current, target), [target])


def _resolve_op_type(current_state: str, next_state: str, tipo_item: str) -> str:
    """Determina el tipo de movimiento de kardex según la transición."""
    if tipo_item == "herramienta":
        if next_state == "RESERVADA":
            return OperationType.RESERVA
        if next_state == "EN_USO":
            return OperationType.SALIDA_HERRAMIENTA
        if next_state in ("STOCK",) and current_state in ("EN_USO", "EN_MANTENIMIENTO"):
            return OperationType.RETORNO_HERRAMIENTA
        if next_state == "EN_MANTENIMIENTO":
            return OperationType.RETORNO_HERRAMIENTA
        if next_state == "OBSOLETA":
            return OperationType.BAJA

    elif tipo_item == "material":
        if next_state == "RESERVADO":
            return OperationType.RESERVA
        if next_state == "CONSUMIDO":
            return OperationType.CONSUMO
        if next_state == "PARCIALMENTE_USADO":
            return OperationType.CONSUMO
        if next_state == "STOCK" and current_state == "PARCIALMENTE_USADO":
            return OperationType.RETORNO_PARCIAL
        if next_state == "STOCK" and current_state == "RESERVADO":
            return OperationType.ENTRADA
        if next_state == "OBSOLETO":
            return OperationType.BAJA

    else:  # equipo / general
        if next_state in ("STOCK",) and current_state in ("REINGRESO_BODEGA", "INGRESO_BODEGA"):
            return OperationType.ENTRADA
        if next_state == "RESERVADO":
            return OperationType.RESERVA
        if next_state == "INSTALADO_CLIENTE":
            return OperationType.INSTALACION
        if next_state in ("DEVOLUCION_PROVEEDOR",):
            return OperationType.SALIDA
        if next_state in ("OBSOLETO",):
            return OperationType.BAJA
        if next_state == "REINGRESO_BODEGA":
            return OperationType.RETORNO
        if next_state == "SALIDA_INSTALACION":
            return OperationType.SALIDA

    return OperationType.AJUSTE


def process_asset_transition(
    *,
    item: Item,
    next_state: str,
    user: User,
    ot_id: str = None,
    notes: str = "",
    ip_address: str = "",
    module_source: str = "Trazabilidad",
    cantidad_delta: int = 0,       # cambio en cantidad para materiales (negativo = consumo)
):
    """
    Procesa un cambio de estado de un activo validando la state machine
    correspondiente al tipo_item del activo.
    """
    tipo = item.tipo_item or "general"
    current_state = item.estado or "STOCK"

    # Normalización de género para estados de reserva/baja según tipo de ítem
    if next_state in ("RESERVADO", "RESERVADA"):
        next_state = "RESERVADA" if tipo == "herramienta" else "RESERVADO"
    if next_state in ("OBSOLETO", "OBSOLETA"):
        next_state = "OBSOLETA" if tipo == "herramienta" else "OBSOLETO"

    # Determinamos si es un cambio real de estado o de OT
    is_same_state = (current_state == next_state)
    is_ot_change = (getattr(item, 'ot_id', None) != ot_id)
    is_removal = (next_state in ("STOCK", "REINGRESO_BODEGA"))
    
    # Registramos movimiento si cambia estado, cambia la OT o es una eliminación (ISO 9001 Trazabilidad)
    should_record_movement = (not is_same_state) or is_ot_change or is_removal

    if not AssetStateMachine.is_transition_allowed(current_state, next_state, tipo):
        raise ValueError(
            f"Transición no permitida para {tipo}: {current_state} → {next_state}"
        )

    # ── Vínculo con OT ───────────────────────────────────────────────────────
    # Si no se provee OT pero el ítem ya tenía una (ej. está RESERVADO), la usamos
    # para que el movimiento de retorno quede registrado en la instalación correcta.
    effective_ot = ot_id or item.ot_id

    if next_state in ("RESERVADO", "RESERVADA") and not effective_ot:
        raise ValueError(
            "El campo 'OT' es obligatorio para marcar un activo como RESERVADO/RESERVADA."
        )

    op_type = _resolve_op_type(current_state, next_state, tipo)

    if should_record_movement:
        from config.apps.inventory.services.movement_service import registrarMovimiento
        registrarMovimiento(
            item_id=str(item.id),
            estado_anterior=current_state,
            estado_nuevo=next_state,
            usuario_id=str(user.id),
            instalacion_id=effective_ot, 
            observaciones=notes,
            op_type_override=op_type,
            module_source=module_source,
        )

    # Si el ítem vuelve a STOCK, debemos desvincularlo de la instalación (OT)
    # y eliminarlo de las listas de la instalación para mantener consistencia.
    if next_state in ("STOCK", "REINGRESO_BODEGA"):
        # Usamos effective_ot para encontrar la instalación de la cual estamos removiendo
        if effective_ot:
            from config.apps.inventory.models.facility import Facility
            facility = Facility.objects(codigo_instalacion=effective_ot, is_active=True).first()
            if facility:
                # Si es material, restauramos la cantidad antes de removerlo de la lista
                if tipo == "material":
                    match = next((c for c in (facility.consumibles or []) if str(c.get("item_id")) == str(item.id)), None)
                    if match:
                        qty_to_restore = match.get("cantidad_reservada") or match.get("cantidad", 0)
                        item.cantidad = (item.cantidad or 0) + qty_to_restore
                        logger.info(f"Restaurando {qty_to_restore} de {item.codigo} al quitar de {facility.codigo_instalacion}")

                # Remover de las listas de la instalación
                facility.items_planificados = [it for it in (facility.items_planificados or []) if str(it.get("item_id")) != str(item.id)]
                facility.herramientas = [h for h in (facility.herramientas or []) if str(h.get("item_id")) != str(item.id)]
                facility.consumibles = [c for c in (facility.consumibles or []) if str(c.get("item_id")) != str(item.id)]
                facility.save()
        
        item.ot_id = None # Limpiar vínculo definitivo en el ítem
    else:
        item.ot_id = effective_ot

    item.estado = next_state

    # Actualizar cantidad para materiales (Opción A)
    if cantidad_delta != 0 and tipo == "material":
        item.cantidad = max(0, (item.cantidad or 0) + cantidad_delta)

    item.save()

    # Transiciones automáticas
    auto = AssetStateMachine.auto_next(next_state)
    if auto:
        return process_asset_transition(
            item=item,
            next_state=auto,
            user=user,
            ot_id=None,
            notes="Transición automática del sistema.",
            ip_address=ip_address,
            module_source="Sistema",
        )

    return item


# ── Sincronización de equipos (flujo original, sin cambios) ──────────────────

def sync_facility_assets(
    *,
    facility,
    next_facility_status: str,
    user: User,
    ip_address: str = "",
    item_destinations: list = None,
):
    """
    Sincroniza equipos (items_planificados) al cambiar el estado de la instalación.
    Herramientas y consumibles se sincronizan con sync_facility_tools /
    sync_facility_materials o a través del endpoint de cierre.
    """
    if next_facility_status not in ("planificada", "en_proceso", "finalizada", "cancelada"):
        raise ValueError(f"Estado de instalación no soportado: {next_facility_status}")

    status_map = {
        "planificada": "RESERVADO",
        "en_proceso":  "SALIDA_INSTALACION",
        "finalizada":  "INSTALADO_CLIENTE",
        "cancelada":   "STOCK",
    }
    target_base_state = status_map[next_facility_status]
    errors = []
    
    # --- Paso A: Sincronizar ítems actuales ---
    current_ids = []
    for it_req in facility.items_planificados:
        item_id = str(it_req["item_id"])
        current_ids.append(item_id)
        
        item_obj = Item.objects(id=item_id).first()
        if not item_obj:
            errors.append(f"Ítem ID {item_id} no encontrado.")
            continue

        current_state = item_obj.estado or "STOCK"
        tipo = item_obj.tipo_item or "equipo"
        
        # Determinar el estado final deseado
        final_state = target_base_state
        if next_facility_status == "finalizada":
            destino = "cliente"
            if item_destinations:
                d_match = next((d for d in item_destinations if str(d.get("item_id")) == item_id), None)
                if d_match: destino = d_match.get("destino", "cliente")
            if destino == "bodega": final_state = "REINGRESO_BODEGA"
        elif next_facility_status == "cancelada":
            final_state = "REINGRESO_BODEGA" if current_state == "SALIDA_INSTALACION" else "STOCK"

        # Obtener ruta de estados
        path = AssetStateMachine.get_path(current_state, final_state, tipo)
        for step in path:
            try:
                process_asset_transition(
                    item=item_obj,
                    next_state=step,
                    user=user,
                    ot_id=facility.codigo_instalacion,
                    notes=f"Sync automático (Paso: {step}): {facility.codigo_instalacion} → {next_facility_status}",
                    ip_address=ip_address,
                    module_source="MODULO_INSTALACIONES",
                )
            except Exception as e:
                errors.append(f"Error en ítem {item_obj.codigo} al pasar a {step}: {str(e)}")
                break

    # --- Paso B: Limpiar ítems removidos (Huérfanos) ---
    # Buscamos ítems que tienen esta OT pero ya no están en la lista
    orphans = Item.objects(ot_id=facility.codigo_instalacion, id__nin=current_ids)
    for orphan in orphans:
        try:
            target = "REINGRESO_BODEGA" if orphan.estado == "SALIDA_INSTALACION" else "STOCK"
            process_asset_transition(
                item=orphan,
                next_state=target,
                user=user,
                ot_id=facility.codigo_instalacion,
                notes=f"Retorno automático: Ítem removido de instalación {facility.codigo_instalacion}",
                ip_address=ip_address,
                module_source="MODULO_INSTALACIONES",
            )
        except Exception as e:
            logger.error(f"Error removiendo huérfano {orphan.codigo}: {e}")

    if errors:
        raise ValueError("\n".join(errors))

    return True


# ── Sincronización de herramientas ────────────────────────────────────────────

def sync_facility_tools(
    *,
    facility,
    next_facility_status: str,
    user: User,
    ip_address: str = "",
):
    """
    Sincroniza herramientas al cambiar estado de instalación.
    - planificada → RESERVADA
    - en_proceso  → EN_USO
    - cancelada   → STOCK (desde RESERVADA o EN_USO)
    El retorno al finalizar se gestiona en FacilityCloseView.
    """
    state_map = {
        "planificada": "RESERVADA",
        "en_proceso":  "EN_USO",
        "cancelada":   "STOCK",
    }
    next_state = state_map.get(next_facility_status)
    if not next_state:
        return True  # finalizada → lo maneja el endpoint /close/

    errors = []
    # --- Paso A: Sincronizar herramientas actuales ---
    current_ids = []
    for herr in facility.herramientas:
        item_id = herr.get("item_id")
        if not item_id: continue
        current_ids.append(str(item_id))
        
        item_obj = Item.objects(id=item_id).first()
        if not item_obj:
            errors.append(f"Herramienta ID {item_id} no encontrada.")
            continue
        
        current = item_obj.estado or "STOCK"
        target = next_state
        if next_facility_status == "cancelada" and current == "EN_USO":
            target = "STOCK"

        path = AssetStateMachine.get_path(current, target, "herramienta")
        for step in path:
            try:
                process_asset_transition(
                    item=item_obj,
                    next_state=step,
                    user=user,
                    ot_id=facility.codigo_instalacion if next_facility_status != "cancelada" else None,
                    notes=f"Sync herramienta (Paso: {step}): {facility.codigo_instalacion} → {next_facility_status}",
                    ip_address=ip_address,
                    module_source="MODULO_INSTALACIONES",
                )
            except Exception as e:
                errors.append(f"Error en herramienta {item_obj.codigo} al pasar a {step}: {e}")
                break

    # --- Paso B: Limpiar herramientas removidas ---
    orphans = Item.objects(ot_id=facility.codigo_instalacion, tipo_item="herramienta", id__nin=current_ids)
    for orphan in orphans:
        try:
            process_asset_transition(
                item=orphan,
                next_state="STOCK",
                user=user,
                ot_id=None,
                notes=f"Retorno automático: Herramienta removida de instalación {facility.codigo_instalacion}",
                ip_address=ip_address,
                module_source="MODULO_INSTALACIONES",
            )
        except Exception as e:
            logger.error(f"Error removiendo herramienta huérfana {orphan.codigo}: {e}")

    if errors:
        raise ValueError("\n".join(errors))
    return True


# ── Sincronización de materiales ──────────────────────────────────────────────

def sync_facility_materials(
    *,
    facility,
    next_facility_status: str,
    user: User,
    ip_address: str = "",
):
    """
    Sincroniza materiales al cambiar estado de instalación.
    - planificada → RESERVADO + descuenta cantidad del stock
    - cancelada   → STOCK + restaura cantidad
    La liquidación al finalizar se gestiona en FacilityCloseView.
    """
    state_map = {
        "planificada": "RESERVADO",
        "cancelada":   "STOCK",
    }
    next_state = state_map.get(next_facility_status)
    if not next_state:
        return True  # en_proceso y finalizada → lo maneja otro flujo

    errors = []
    for cons in facility.consumibles:
        item_id = cons.get("item_id")
        if not item_id:
            continue
        item_obj = Item.objects(id=item_id).first()
        if not item_obj:
            errors.append(f"Material con ID {item_id} no encontrado.")
            continue
 
        current    = item_obj.estado or "STOCK"
        
        # Validar STOCK al planificar
        if next_facility_status == "planificada" and current != "STOCK":
            errors.append(
                f"El material {item_obj.codigo} no está disponible (Estado actual: {current})."
            )
            continue
        cant_reservada = int(cons.get("cantidad_reservada") or cons.get("cantidad") or 0)

        if not AssetStateMachine.is_transition_allowed(current, next_state, "material"):
            logger.warning(
                "Material %s: transición %s → %s omitida.",
                item_obj.codigo, current, next_state
            )
            continue

        # delta de cantidad: negativo al reservar, positivo al cancelar
        if next_facility_status == "planificada":
            delta = -cant_reservada
        else:  # cancelada
            delta = cant_reservada

        process_asset_transition(
            item=item_obj,
            next_state=next_state,
            user=user,
            ot_id=facility.codigo_instalacion if next_facility_status != "cancelada" else None,
            notes=f"Sync material: instalación {facility.codigo_instalacion} → {next_facility_status}",
            ip_address=ip_address,
            module_source="MODULO_INSTALACIONES",
            cantidad_delta=delta,
        )

    if errors:
        raise ValueError("\n".join(errors))
    return True
