"""
Modelo de Ítem — Gestión de activos individuales del inventario.

Opción A (stock por cantidad) implementada: campo `cantidad` para
materiales/consumibles. Tipo de ítem diferencia la state machine.

ISO 27001 A.8 — Gestión de activos.
ISO 9001  8.1 — Planificación operacional.
"""
import mongoengine as me
from config.apps.base.base_document import BaseDocument
from config.apps.inventory.models.subcategory import SubCategory

# ── Conjuntos de estados válidos por tipo de ítem ────────────────────────────
ESTADOS_EQUIPO = [
    "INGRESO_BODEGA",       # transitorio automático → STOCK
    "STOCK",                # disponible en bodega
    "RESERVADO",            # asignado a instalación planificada
    "SALIDA_INSTALACION",   # en tránsito hacia cliente
    "INSTALADO_CLIENTE",    # instalado permanentemente
    "REINGRESO_BODEGA",     # transitorio automático → STOCK
    "DEVOLUCION_PROVEEDOR", # TERMINAL
    "OBSOLETO",             # TERMINAL
    "ACTIVO_EN_CAMPO",      # TERMINAL
]

ESTADOS_HERRAMIENTA = [
    "STOCK",            # disponible en bodega
    "RESERVADA",        # asignada a instalación planificada
    "EN_USO",           # salió a instalación en curso
    "EN_MANTENIMIENTO", # no disponible, en reparación
    "OBSOLETA",         # TERMINAL
]

ESTADOS_MATERIAL = [
    "STOCK",              # disponible en bodega
    "RESERVADO",          # asignado a instalación planificada
    "CONSUMIDO",          # TERMINAL — consumido totalmente
    "PARCIALMENTE_USADO", # transitorio → STOCK tras liquidación
    "OBSOLETO",           # TERMINAL
]

# Set unificado sin duplicados (preservando orden)
ALL_ESTADOS = list(dict.fromkeys(
    ESTADOS_EQUIPO + ESTADOS_HERRAMIENTA + ESTADOS_MATERIAL
))


class Item(BaseDocument):
    """
    Representa un activo individual del inventario.

    - tipo_item diferencia la lógica de estados y la state machine.
    - cantidad aplica a materiales/consumibles (Opción A).
    - Para equipos y herramientas, cantidad = 1 siempre.
    """
    codigo = me.StringField(required=True, unique=True)
    nombre = me.StringField(required=True)

    subcategoria = me.ReferenceField(
        SubCategory,
        required=True,
        reverse_delete_rule=me.DENY
    )

    # Clasificación funcional — controla la state machine aplicable
    tipo_item = me.StringField(
        choices=["equipo", "herramienta", "material", "general"],
        default="general"
    )

    marca  = me.StringField()
    modelo = me.StringField()
    serial = me.StringField()

    estado = me.StringField(
        choices=ALL_ESTADOS,
        default="STOCK"
    )

    # Cantidad disponible en bodega.
    # Materiales: unidades/metros/etc. disponibles actualmente.
    # Equipos y herramientas: siempre 1.
    cantidad = me.IntField(default=1, min_value=0)

    criticidad = me.StringField(
        choices=["alta", "media", "baja"],
        default="media",
    )

    ubicacion_actual_id = me.ObjectIdField(required=False)

    # Vinculación a Orden de Trabajo / Instalación activa
    ot_id = me.StringField(required=False)

    is_active = me.BooleanField(default=True)

    meta = {
        "collection": "items",
        "indexes": [
            "codigo", "estado", "is_active",
            "criticidad", "ot_id", "tipo_item",
        ],
    }

    def clean(self):
        if self.estado and self.estado not in ALL_ESTADOS:
            raise me.ValidationError(
                f"Estado '{self.estado}' no válido. "
                f"Permitidos: {', '.join(ALL_ESTADOS)}"
            )
        if self.criticidad and self.criticidad not in ("alta", "media", "baja"):
            raise me.ValidationError(
                f"Criticidad '{self.criticidad}' no válida."
            )
        if self.tipo_item and self.tipo_item not in (
            "equipo", "herramienta", "material", "general"
        ):
            raise me.ValidationError(
                f"tipo_item '{self.tipo_item}' no válido."
            )
