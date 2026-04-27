from core.api_client import APIClient


def list_facilities(estado=None):
    params = {}
    if estado and estado != "TODOS":
        params["estado"] = estado
    return APIClient.get("inventory/facilities/", params=params)


def search_facilities(query):
    return APIClient.get("inventory/facilities/", params={"search": query})


def get_facility(facility_id):
    return APIClient.get(f"inventory/facilities/{facility_id}/")


def start_facility(facility_id):
    return APIClient.post(f"inventory/facilities/{facility_id}/start/")


def finish_facility(facility_id, item_destinations):
    """Flujo legacy — solo maneja destinos de equipos."""
    return APIClient.post(
        f"inventory/facilities/{facility_id}/finish/",
        json={"items_planificados": item_destinations},
    )


def close_facility(facility_id, items_planificados, herramientas_cierre, consumibles_cierre):
    """
    Cierre completo: equipos + retorno obligatorio de herramientas
    + liquidación de materiales.
    """
    return APIClient.post(
        f"inventory/facilities/{facility_id}/close/",
        json={
            "items_planificados":   items_planificados,
            "herramientas_cierre":  herramientas_cierre,
            "consumibles_cierre":   consumibles_cierre,
        },
    )


def cancel_facility(facility_id):
    return APIClient.post(f"inventory/facilities/{facility_id}/cancel/")


def update_destinations(facility_id, destinations):
    """Auto-save de destinos de equipos durante EN_PROCESO."""
    return APIClient.patch(
        f"inventory/facilities/{facility_id}/destinations/",
        json={"destinations": destinations},
    )


def get_facility_movements(facility_id):
    return APIClient.get(f"inventory/facilities/{facility_id}/movements/")


def update_facility(facility_id, data):
    """Actualización parcial de la instalación (PUT con partial=True en backend)."""
    return APIClient.put(f"inventory/facilities/{facility_id}/", json=data)
