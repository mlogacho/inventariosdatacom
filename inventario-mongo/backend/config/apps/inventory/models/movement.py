"""
Modelo de Movimiento — Trazabilidad de ítems del inventario.

ISO 27001 A.12.4.1 — Audit logging: registro inmutable de cada movimiento.
ISO 9001 8.5.1 — Control de producción: campos completos para trazabilidad.

V-03 Fix: tipo_movimiento con enum explícito (no StringField libre).
V-17 Fix: Campos adicionales de trazabilidad (ip_address, notes, module_source).
V-18 Fix: Índices compuestos para consultas eficientes por ítem y usuario.

IMPORTANTE: Esta colección es APPEND-ONLY.
No existen endpoints DELETE ni UPDATE sobre movimientos.
"""
import mongoengine as me
from datetime import datetime, timezone
from config.apps.base.base_document import BaseDocument
from config.apps.inventory.models.item import Item
from config.apps.users.models.user import User


class OperationType(object):
    """
    Tipos de operación válidos para movimientos de inventario.
    ISO 9001 8.1 — Planificación y control operacional.
    """
    ENTRADA       = "ENTRADA"        # Ingreso de ítem al sistema o bodega
    SALIDA        = "SALIDA"         # Egreso de ítem del sistema o bodega
    AJUSTE        = "AJUSTE"         # Corrección de estado o ubicación
    TRANSFERENCIA = "TRANSFERENCIA"  # Traslado entre bodegas
    BAJA          = "BAJA"           # Ítem dado de baja definitivamente
    RESERVA       = "RESERVA"        # Asignación a una OT (equipos/herramientas)
    INSTALACION   = "INSTALACION"    # Instalación permanente en cliente (equipo)
    RETORNO       = "RETORNO"        # Reingreso a bodega desde campo
    # Tipos específicos para herramientas y materiales
    SALIDA_HERRAMIENTA  = "SALIDA_HERRAMIENTA"   # Herramienta sale a instalación (EN_USO)
    RETORNO_HERRAMIENTA = "RETORNO_HERRAMIENTA"  # Herramienta regresa a bodega
    CONSUMO             = "CONSUMO"              # Material consumido totalmente
    RETORNO_PARCIAL     = "RETORNO_PARCIAL"      # Sobrante de material regresa a bodega

    ALL = [
        ENTRADA, SALIDA, AJUSTE, TRANSFERENCIA, BAJA,
        RESERVA, INSTALACION, RETORNO,
        SALIDA_HERRAMIENTA, RETORNO_HERRAMIENTA,
        CONSUMO, RETORNO_PARCIAL,
    ]


class Movement(BaseDocument):
    """
    Registro inmutable de movimiento de un ítem de inventario.

    Cada instancia representa un evento de trazabilidad.
    Una vez creado, NO debe modificarse ni eliminarse.
    """

    # ── Ítem afectado ──────────────────────────────────────────
    item = me.ReferenceField(
        Item,
        required=True,
        reverse_delete_rule=me.DENY,  # Previene borrar ítems con movimientos
    )

    # ── Tipo de operación (V-03: enum explícito) ───────────────
    tipo_movimiento = me.StringField(
        required=True,
        choices=OperationType.ALL,
        help_text="Tipo de operación: ENTRADA, SALIDA, AJUSTE, TRANSFERENCIA, BAJA",
    )

    # ── Origen y destino del movimiento ───────────────────────
    origen = me.DictField(required=True)
    destino = me.DictField(required=True)

    # ── Instantáneas de estado para trazabilidad (V-17) ───────
    # Captura el estado ANTES del movimiento
    estado_anterior = me.DictField(required=True)
    # Captura el estado DESPUÉS del movimiento
    estado_nuevo = me.DictField(required=True)

    # ── Timestamp del evento ──────────────────────────────────
    fecha = me.DateTimeField(default=lambda: datetime.now(timezone.utc))

    # ── Actor del movimiento ──────────────────────────────────
    responsable = me.ReferenceField(User, required=True)

    # ── Campos de auditoría adicionales (V-17) ────────────────
    # IP de origen de la solicitud (ISO 27001 A.12.4.1)
    ip_address = me.StringField(max_length=45, default="")

    # Módulo o contexto que originó el cambio (auditoría)
    module_source = me.StringField(max_length=100, default="API")

    # Notas opcionales del operador (contexto del movimiento)
    notes = me.StringField(max_length=500, default="")

    # ── Campos numéricos para trazabilidad cuantitativa (V-26) ──
    # ISO 9001 8.5.1 — Control de producción
    previous_quantity = me.IntField(default=0)
    new_quantity = me.IntField(default=0)
    delta = me.IntField(default=0)

    # ── Vinculación a OT (V-40) ────────────────────────────────
    ot_id = me.StringField(required=False)

    # ── Metadatos MongoDB ─────────────────────────────────────
    meta = {
        "collection": "movimientos",
        "ordering": ["-fecha"],
        # V-18 Fix: Índices compuestos para consultas eficientes
        "indexes": [
            ("item", "-fecha"),          # Historial por ítem (más frecuente)
            ("responsable", "-fecha"),   # Historial por usuario (auditoría)
            "-fecha",                    # Listado cronológico general
            "tipo_movimiento",           # Filtro por tipo de operación
        ],
    }

    def clean(self):
        """
        Validación a nivel de documento (ISO 9001 8.6).
        Verifica que el tipo de movimiento sea válido antes de guardar.
        """
        if self.tipo_movimiento not in OperationType.ALL:
            raise me.ValidationError(
                f"tipo_movimiento '{self.tipo_movimiento}' no válido. "
                f"Valores permitidos: {', '.join(OperationType.ALL)}"
            )
