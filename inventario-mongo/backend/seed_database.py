"""
Script de Poblamiento de Base de Datos (Seeder) — Proyecto Antigravity

Acciones:
1. Elimina todas las colecciones excepto usuarios (se conservan).
2. Crea catálogos maestros: Categorías, Subcategorías, Bodegas, Clientes, Proveedores, Vehículos.
3. Crea ítems de ejemplo con trazabilidad inicial vía servicio centralizado.

USO:
    python seed_database.py
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from config.settings.mongo import init_mongo
init_mongo()

from config.apps.users.models.user import User
from config.apps.inventory.models.category import Category
from config.apps.inventory.models.subcategory import SubCategory
from config.apps.inventory.models.store import Store
from config.apps.inventory.models.customer import Customer
from config.apps.inventory.models.supplier import Supplier
from config.apps.inventory.models.item import Item
from config.apps.inventory.models.movement import Movement
from config.apps.inventory.models.facility import Facility
from config.apps.inventory.models.vehicle import Vehicle


def seed():
    print("--- INICIANDO POBLAMIENTO DE DATOS ---")

    # ──────────────────────────────────────────
    # 1. LIMPIEZA (sin tocar usuarios)
    # ──────────────────────────────────────────
    print("Eliminando datos existentes (usuarios conservados)...")
    Facility.objects.delete()
    Movement.objects.delete()
    Item.objects.delete()
    Vehicle.objects.delete()
    Store.objects.delete()
    Customer.objects.delete()
    Supplier.objects.delete()
    SubCategory.objects.delete()
    Category.objects.delete()

    # ──────────────────────────────────────────
    # 2. USUARIOS (ISO 27001 A.9.2)
    # ──────────────────────────────────────────
    print("Creando usuarios por defecto...")

    def create_user_if_not_exists(username, password, rol):
        user = User.objects(username=username).first()
        if not user:
            user = User(username=username, rol=rol)
            user.set_password(password)
            user.save()
            print(f"  Usuario creado: {username} ({rol})")
        return user

    admin = create_user_if_not_exists("admin", "admin123", "admin")
    tecnico = create_user_if_not_exists("tecnico", "tecnico123", "tecnico")
    administrativo = create_user_if_not_exists("administrativo", "admin123", "administrativo")

    print(f"Usando admin '{admin.username}' para trazabilidad de los ítems.")

    # ──────────────────────────────────────────
    # 3. CATEGORÍAS Y SUBCATEGORÍAS
    # ──────────────────────────────────────────
    print("Creando catálogos de categorías...")

    cat_redes    = Category(nombre_categoria="Equipos de Red").save()
    cat_serv     = Category(nombre_categoria="Servidores y Almacenamiento").save()
    cat_energia  = Category(nombre_categoria="Energía y UPS").save()
    cat_camara   = Category(nombre_categoria="Videovigilancia").save()
    cat_telefon  = Category(nombre_categoria="Telefonía IP").save()
    cat_herramientas = Category(nombre_categoria="Herramientas").save()
    cat_materiales = Category(nombre_categoria="Materiales").save()
    cat_oficina  = Category(nombre_categoria="Activos de Oficina").save()

    sub_router   = SubCategory(categoria=cat_redes,   nombre="Routers").save()
    sub_switch   = SubCategory(categoria=cat_redes,   nombre="Switches").save()
    sub_fw       = SubCategory(categoria=cat_redes,   nombre="Firewalls").save()
    sub_ap       = SubCategory(categoria=cat_redes,   nombre="Access Points").save()
    sub_rack     = SubCategory(categoria=cat_serv,    nombre="Racks y Gabinetes").save()
    sub_nas      = SubCategory(categoria=cat_serv,    nombre="NAS / Almacenamiento").save()
    sub_ups      = SubCategory(categoria=cat_energia, nombre="UPS").save()
    sub_pdu      = SubCategory(categoria=cat_energia, nombre="PDU").save()
    sub_cam      = SubCategory(categoria=cat_camara,  nombre="Cámaras IP").save()
    sub_dvr      = SubCategory(categoria=cat_camara,  nombre="DVR / NVR").save()
    sub_tel      = SubCategory(categoria=cat_telefon, nombre="Teléfonos IP").save()

    # Nuevas subcategorías solicitadas
    sub_h_manual    = SubCategory(categoria=cat_herramientas, nombre="Herramientas Manuales").save()
    sub_h_electrica = SubCategory(categoria=cat_herramientas, nombre="Herramientas Eléctricas").save()
    sub_m_cableado  = SubCategory(categoria=cat_materiales,   nombre="Cableado y Conectividad").save()
    sub_m_consumo   = SubCategory(categoria=cat_materiales,   nombre="Consumibles").save()
    sub_o_mueble    = SubCategory(categoria=cat_oficina,      nombre="Mobiliario").save()
    sub_o_computo   = SubCategory(categoria=cat_oficina,      nombre="Equipos de Computación").save()

    # ──────────────────────────────────────────
    # 4. BODEGAS
    # ──────────────────────────────────────────
    print("Creando bodegas...")

    bodega_norte = Store(
        nombre_bodega="Bodega Principal — Norte",
        ubicacion={"ciudad": "Quito", "sector": "Carcelén Industrial"}
    ).save()
    bodega_sur = Store(
        nombre_bodega="Centro de Distribución — Sur",
        ubicacion={"ciudad": "Guayaquil", "sector": "Durán"}
    ).save()
    bodega_cuenca = Store(
        nombre_bodega="Sucursal Austro",
        ubicacion={"ciudad": "Cuenca", "sector": "Parque Industrial"}
    ).save()

    # ──────────────────────────────────────────
    # 5. CLIENTES
    # ──────────────────────────────────────────
    print("Creando clientes...")

    Customer(nombre_cliente="Corporación Alpha S.A.",       sucursal="Matriz Quito",    ubicacion={"ciudad": "Quito"}).save()
    Customer(nombre_cliente="Banco Meridional",             sucursal="Agencia Norte",   ubicacion={"ciudad": "Quito"}).save()
    Customer(nombre_cliente="Hospital Metropolitano",       sucursal="Sede Principal",  ubicacion={"ciudad": "Quito"}).save()
    Customer(nombre_cliente="Municipio de Guayaquil",       sucursal="Dep. Tecnología", ubicacion={"ciudad": "Guayaquil"}).save()
    Customer(nombre_cliente="Universidad Técnica Nacional", sucursal="Campus Sur",      ubicacion={"ciudad": "Cuenca"}).save()

    # ──────────────────────────────────────────
    # 6. PROVEEDORES
    # ──────────────────────────────────────────
    print("Creando proveedores...")

    Supplier(nombre_proveedor="TechGlobal S.A.",       ubicacion={"pais": "Ecuador", "ciudad": "Quito"}).save()
    Supplier(nombre_proveedor="Cisco Systems Ecuador", ubicacion={"pais": "Ecuador", "ciudad": "Quito"}).save()
    Supplier(nombre_proveedor="HP Enterprise Andes",   ubicacion={"pais": "Ecuador", "ciudad": "Guayaquil"}).save()
    Supplier(nombre_proveedor="Hikvision Ecuador",     ubicacion={"pais": "Ecuador", "ciudad": "Quito"}).save()
    Supplier(nombre_proveedor="APC by Schneider",      ubicacion={"pais": "Ecuador", "ciudad": "Quito"}).save()

    # ──────────────────────────────────────────
    # 7. VEHÍCULOS
    # ──────────────────────────────────────────
    print("Creando vehículos...")

    Vehicle(marca="Toyota",    modelo="Hilux 4x4",  placa="PBX-0312", anio=2022).save()
    Vehicle(marca="Chevrolet", modelo="NHR Furgón", placa="PCA-1187", anio=2021).save()
    Vehicle(marca="Hyundai",   modelo="H1 Van",     placa="PCB-4421", anio=2023).save()

    # ──────────────────────────────────────────
    # 8. ÍTEMS CON TRAZABILIDAD INICIAL
    # ──────────────────────────────────────────
    print("Creando ítems y trazabilidad...")

    from config.apps.inventory.services.traceability_service import process_asset_transition

    items_data = [
        # Routers
        {"codigo": "RT-001", "nombre": "Router Cisco ISR 4331",      "sub": sub_router, "serial": "SN-CSC-4331-001", "crit": "alta",  "bodega": bodega_norte},
        {"codigo": "RT-002", "nombre": "Router Cisco ISR 4351",      "sub": sub_router, "serial": "SN-CSC-4351-002", "crit": "alta",  "bodega": bodega_sur},
        {"codigo": "RT-003", "nombre": "Router MikroTik CCR2004",    "sub": sub_router, "serial": "SN-MKT-2004-003", "crit": "media", "bodega": bodega_norte},
        # Switches
        {"codigo": "SW-101", "nombre": "Switch Cisco Catalyst 9200", "sub": sub_switch, "serial": "SN-CSC-9200-101", "crit": "alta",  "bodega": bodega_norte},
        {"codigo": "SW-102", "nombre": "Switch Cisco Catalyst 9300", "sub": sub_switch, "serial": "SN-CSC-9300-102", "crit": "alta",  "bodega": bodega_norte},
        {"codigo": "SW-103", "nombre": "Switch HP ProCurve 2920",    "sub": sub_switch, "serial": "SN-HP-2920-103",  "crit": "media", "bodega": bodega_sur},
        {"codigo": "SW-104", "nombre": "Switch MikroTik CRS328",     "sub": sub_switch, "serial": "SN-MKT-328-104",  "crit": "media", "bodega": bodega_cuenca},
        # Firewalls
        {"codigo": "FW-001", "nombre": "Firewall Fortinet FortiGate 60F", "sub": sub_fw, "serial": "SN-FTN-60F-001", "crit": "alta",  "bodega": bodega_norte},
        {"codigo": "FW-002", "nombre": "Firewall Cisco ASA 5506-X",       "sub": sub_fw, "serial": "SN-CSC-5506-002","crit": "alta",  "bodega": bodega_sur},
        # Access Points
        {"codigo": "AP-201", "nombre": "AP Ubiquiti UniFi U6 Pro",   "sub": sub_ap, "serial": "SN-UBQ-U6P-201", "crit": "baja",  "bodega": bodega_norte},
        {"codigo": "AP-202", "nombre": "AP Ubiquiti UniFi U6 Lite",  "sub": sub_ap, "serial": "SN-UBQ-U6L-202", "crit": "baja",  "bodega": bodega_norte},
        {"codigo": "AP-203", "nombre": "AP Cisco Aironet 2800",      "sub": sub_ap, "serial": "SN-CSC-2800-203","crit": "media", "bodega": bodega_sur},
        # Racks
        {"codigo": "RK-501", "nombre": "Rack Gabinete 42U Open Frame","sub": sub_rack, "serial": "SN-RK-42U-501", "crit": "baja",  "bodega": bodega_norte},
        {"codigo": "RK-502", "nombre": "Rack Gabinete 22U Cerrado",   "sub": sub_rack, "serial": "SN-RK-22U-502", "crit": "baja",  "bodega": bodega_cuenca},
        # NAS
        {"codigo": "NS-301", "nombre": "NAS Synology DS923+",        "sub": sub_nas, "serial": "SN-SYN-923-301", "crit": "alta",  "bodega": bodega_norte},
        {"codigo": "NS-302", "nombre": "NAS QNAP TS-464",            "sub": sub_nas, "serial": "SN-QNP-464-302", "crit": "media", "bodega": bodega_sur},
        # UPS
        {"codigo": "UP-401", "nombre": "UPS APC Smart-UPS 3000VA",   "sub": sub_ups, "serial": "SN-APC-3K-401", "crit": "alta",  "bodega": bodega_norte},
        {"codigo": "UP-402", "nombre": "UPS APC Back-UPS 1500VA",    "sub": sub_ups, "serial": "SN-APC-1K5-402","crit": "media", "bodega": bodega_norte},
        {"codigo": "UP-403", "nombre": "UPS Eaton 5PX 2200VA",       "sub": sub_ups, "serial": "SN-ETN-2K2-403","crit": "alta",  "bodega": bodega_sur},
        # PDU
        {"codigo": "PD-601", "nombre": "PDU APC AP8853 0U Rack",     "sub": sub_pdu, "serial": "SN-APC-PD-601", "crit": "baja",  "bodega": bodega_norte},
        # Cámaras
        {"codigo": "CM-701", "nombre": "Cámara IP Hikvision DS-2CD2143G2", "sub": sub_cam, "serial": "SN-HKV-2143-701", "crit": "media", "bodega": bodega_norte},
        {"codigo": "CM-702", "nombre": "Cámara IP Hikvision DS-2CD2347G2", "sub": sub_cam, "serial": "SN-HKV-2347-702", "crit": "media", "bodega": bodega_norte},
        {"codigo": "CM-703", "nombre": "Cámara Dahua IPC-HFW2849S",        "sub": sub_cam, "serial": "SN-DAH-2849-703", "crit": "baja",  "bodega": bodega_sur},
        # DVR / NVR
        {"codigo": "NV-801", "nombre": "NVR Hikvision DS-7608NI-K2",  "sub": sub_dvr, "serial": "SN-HKV-7608-801", "crit": "media", "bodega": bodega_norte},
        {"codigo": "NV-802", "nombre": "DVR Dahua XVR5108H",           "sub": sub_dvr, "serial": "SN-DAH-5108-802", "crit": "baja",  "bodega": bodega_sur},
        # Telefonía
        {"codigo": "TL-901", "nombre": "Teléfono IP Yealink T54W",    "sub": sub_tel, "serial": "SN-YLK-T54-901", "crit": "baja",  "bodega": bodega_norte},
        {"codigo": "TL-902", "nombre": "Teléfono IP Cisco 8841",       "sub": sub_tel, "serial": "SN-CSC-8841-902","crit": "baja",  "bodega": bodega_norte},
        {"codigo": "TL-903", "nombre": "Teléfono IP Polycom VVX 411", "sub": sub_tel, "serial": "SN-PLY-411-903", "crit": "baja",  "bodega": bodega_cuenca},

        # Herramientas
        {"codigo": "HM-001", "nombre": "Juego de Destornilladores Pro", "sub": sub_h_manual, "serial": "SN-HM-001", "crit": "baja", "bodega": bodega_norte},
        {"codigo": "HE-001", "nombre": "Taladro Percutor Bosch 600W", "sub": sub_h_electrica, "serial": "SN-HE-001", "crit": "media", "bodega": bodega_norte},
        # Materiales
        {"codigo": "MT-001", "nombre": "Bobina Cable UTP Cat6 305m", "sub": sub_m_cableado, "serial": "SN-MT-001", "crit": "media", "bodega": bodega_sur},
        {"codigo": "MT-002", "nombre": "Caja Conectores RJ45 x100", "sub": sub_m_consumo, "serial": "SN-MT-002", "crit": "baja", "bodega": bodega_norte},
        # Oficina
        {"codigo": "OF-001", "nombre": "Silla Ergonómica Ejecutiva", "sub": sub_o_mueble, "serial": "SN-OF-001", "crit": "baja", "bodega": bodega_cuenca},
        {"codigo": "OF-002", "nombre": "Laptop Dell Latitude 5420", "sub": sub_o_computo, "serial": "SN-OF-002", "crit": "alta", "bodega": bodega_norte},
    ]

    for data in items_data:
        cat_name = data["sub"].categoria.nombre_categoria.lower()
        t_item = "equipo"
        if "herramienta" in cat_name: t_item = "herramienta"
        elif "material" in cat_name: t_item = "material"

        # Herramientas y materiales no tienen INGRESO_BODEGA en su state machine
        estado_inicial = "INGRESO_BODEGA" if t_item == "equipo" else "STOCK"

        item = Item(
            codigo=data["codigo"],
            nombre=data["nombre"],
            subcategoria=data["sub"],
            serial=data["serial"],
            criticidad=data["crit"],
            tipo_item=t_item,
            estado=estado_inicial,
            ubicacion_actual_id=data["bodega"].id,
        ).save()

        item = Item.objects(id=item.id).first()

        # Solo los equipos requieren la transición INGRESO_BODEGA → STOCK
        if t_item == "equipo":
            process_asset_transition(
                item=item,
                next_state="STOCK",
                user=admin,
                notes="Ingreso inicial — compra de activos.",
                ip_address="127.0.0.1",
                module_source="SEEDER",
            )

    # ──────────────────────────────────────────
    # RESUMEN
    # ──────────────────────────────────────────
    print()
    print("=" * 45)
    print("  POBLAMIENTO COMPLETADO EXITOSAMENTE")
    print("=" * 45)
    print(f"  Categorías:    {Category.objects.count()}")
    print(f"  SubCategorías: {SubCategory.objects.count()}")
    print(f"  Bodegas:       {Store.objects.count()}")
    print(f"  Clientes:      {Customer.objects.count()}")
    print(f"  Proveedores:   {Supplier.objects.count()}")
    print(f"  Vehículos:     {Vehicle.objects.count()}")
    print(f"  Ítems:         {Item.objects.count()}")
    print(f"  Movimientos:   {Movement.objects.count()}")
    print(f"  Usuarios:      {User.objects.count()} (conservados, sin cambios)")
    print("=" * 45)


if __name__ == "__main__":
    try:
        seed()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nERROR DURANTE EL POBLAMIENTO: {e}")
