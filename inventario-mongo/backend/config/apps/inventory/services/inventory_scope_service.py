"""
Reglas de alcance para la operación de inventarios.

Este servicio centraliza restricciones de negocio para el escenario:
- Ingreso de equipos desde Matriz: Oficinas Cumbaya.
- Ingreso permitido solo en dos bodegas operativas.
"""

from bson import ObjectId

from config.apps.inventory.models.store import Store


MATRIX_INGRESO = "Matriz: Oficinas Cumbaya"
ALLOWED_STORE_NAMES = (
    "Bodega General Conocoto",
    "Mini Bodega Cumbaya",
)


def ensure_allowed_stores_exist():
    """Crea las bodegas permitidas si no existen."""
    for name in ALLOWED_STORE_NAMES:
        exists = Store.objects(nombre_bodega=name, is_active=True).first()
        if not exists:
            Store(
                nombre_bodega=name,
                ubicacion={"sede": MATRIX_INGRESO},
                is_active=True,
            ).save()


def get_allowed_stores_queryset():
    ensure_allowed_stores_exist()
    return Store.objects(nombre_bodega__in=ALLOWED_STORE_NAMES, is_active=True)


def is_allowed_store_name(store_name: str) -> bool:
    return store_name in ALLOWED_STORE_NAMES


def get_allowed_store_by_id(store_id):
    """Retorna la bodega si pertenece al conjunto permitido; caso contrario None."""
    try:
        oid = ObjectId(str(store_id))
    except Exception:
        return None

    return Store.objects(
        id=oid,
        nombre_bodega__in=ALLOWED_STORE_NAMES,
        is_active=True,
    ).first()
