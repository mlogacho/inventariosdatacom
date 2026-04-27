from config.apps.inventory.models.facility import Facility


ALLOWED_FACILITY_STATES = [
    "planificada",
    "en_proceso",
    "finalizada",
    "cancelada",
]

# Transiciones válidas entre estados de instalación.
# PLANIFICADO → EN_PROCESO → FINALIZADO (orden estricto, sin saltos).
# La cancelación se trata por separado ya que es válida desde planificada o en_proceso.
_FACILITY_TRANSITIONS = {
    "planificada": ["en_proceso"],
    "en_proceso":  ["finalizada"],
    "finalizada":  [],   # TERMINAL
    "cancelada":   [],   # TERMINAL
}


def validate_facility_transition(current_state: str, next_state: str) -> None:
    """
    Valida que la transición de estado de una instalación sea legal.
    Lanza ValueError con mensaje descriptivo si la transición no está permitida.
    """
    if next_state == "cancelada":
        if current_state in ("planificada", "en_proceso"):
            return
        raise ValueError(
            f"No se puede cancelar una instalación en estado '{current_state}'."
        )

    allowed = _FACILITY_TRANSITIONS.get(current_state, [])
    if next_state not in allowed:
        if not allowed:
            raise ValueError(
                f"La instalación está en estado terminal '{current_state}'. "
                "No se permiten más cambios de estado."
            )
        raise ValueError(
            f"Transición inválida: '{current_state}' → '{next_state}'. "
            f"Solo se permite avanzar a: {', '.join(allowed)}."
        )


def soft_delete_facility(facility: Facility) -> None:
    facility.is_active = False
    facility.save()


def change_facility_status(facility: Facility, new_status: str) -> None:
    if new_status not in ALLOWED_FACILITY_STATES:
        raise ValueError(f"Estado no permitido: {new_status}")
    validate_facility_transition(facility.estado, new_status)
    facility.estado = new_status
    facility.save()
