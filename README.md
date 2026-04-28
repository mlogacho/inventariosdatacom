# Sistema de Trazabilidad de Activos — DataCom S.A.

Sistema integral de gestión y trazabilidad de inventario diseñado para DataCom S.A. Permite registrar, rastrear y auditar el ciclo de vida completo de equipos, herramientas y materiales desde su ingreso hasta su instalación en clientes, con generación de actas en PDF y cumplimiento ISO 27001 / ISO 9001.

---

## Características principales

- **Trazabilidad completa**: cada movimiento de un activo queda registrado de forma inmutable (colección append-only).
- **Máquina de estados por tipo de ítem**: equipos, herramientas y materiales tienen flujos de estado independientes y estrictamente validados.
- **Gestión de instalaciones (Facilities)**: planificación, inicio, finalización y cancelación de órdenes de trabajo con asignación de técnicos, vehículos y activos.
- **Generación de Actas en PDF**: el acta RE-SIGC-SI-AS-1.0 se genera a partir de un template Word y se convierte a PDF con LibreOffice.
- **Control de acceso por roles (RBAC)**: autenticación JWT personalizada con throttling y seguridad ISO 27001.
- **Frontend de escritorio/web**: interfaz construida con Flet, tema oscuro estilo JetBrains.

---

## Arquitectura

```
┌──────────────────────┐        HTTP / REST        ┌──────────────────────┐
│   Frontend (Flet)    │ ◄───────────────────────► │   Backend (Django)   │
│   Puerto 8081        │                            │   Puerto 8000        │
└──────────────────────┘                            └──────────┬───────────┘
                                                               │ MongoEngine
                                                    ┌──────────▼───────────┐
                                                    │   MongoDB 7          │
                                                    │   Replica Set rs0    │
                                                    │   Puerto 27017       │
                                                    └──────────────────────┘
```

### Capas del backend

```
Views (DRF ViewSets)
    └── Services (lógica de negocio)
            └── Repositories (acceso a datos)
                    └── Models (MongoEngine Documents)
```

---

## Stack tecnológico

| Capa | Tecnología | Versión |
|------|-----------|---------|
| Backend framework | Django + Django REST Framework | 5.0.4 / 3.15.1 |
| Base de datos | MongoDB + MongoEngine | 7 / 0.28.2 |
| Autenticación | JWT personalizado (PyJWT) | 2.8.0 |
| Hashing de contraseñas | Argon2 (ISO 27001 A.10.1) | 23.1.0 |
| Generación de reportes | python-docx + LibreOffice | 1.1.2 |
| Frontend | Flet | 0.19.0 |
| Contenedores | Docker + Docker Compose | — |

---

## Estructura del proyecto

```
trazabilidad_activos/
│
├── inventario-mongo/                  # Backend Django
│   ├── docker-compose.yml             # Orquestación de servicios
│   ├── .env.example                   # Plantilla de variables de entorno
│   └── backend/
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── manage.py
│       ├── seed_database.py           # Script de datos iniciales
│       └── config/
│           ├── settings/
│           │   ├── base.py            # Configuración principal
│           │   ├── dev.py             # Overrides de desarrollo
│           │   └── mongo.py           # Conexión MongoDB
│           ├── urls.py                # Router principal
│           └── apps/
│               ├── base/              # Documento base, health check
│               ├── users/             # Gestión de usuarios y JWT
│               └── inventory/
│                   ├── models/        # Item, Movement, Facility, …
│                   ├── views/         # Endpoints REST
│                   ├── services/      # Lógica de negocio + generación PDF
│                   ├── repositories/  # Acceso a MongoDB
│                   └── assets/        # Template Word del acta
│
└── flet_inventario/                   # Frontend Flet
    ├── Dockerfile
    ├── requirements.txt
    ├── .env                           # URL del backend
    ├── main.py                        # Punto de entrada
    ├── core/                          # Cliente HTTP, sesión, tema
    ├── services/                      # Capa de llamadas a la API
    ├── components/                    # Widgets reutilizables
    └── views/                         # Pantallas de la aplicación
        ├── items/
        ├── facilities/
        ├── movements/
        ├── customers/
        ├── stores/
        ├── suppliers/
        ├── users/
        └── vehicles/
```

---

## Requisitos previos

- [Docker](https://docs.docker.com/get-docker/) ≥ 24
- [Docker Compose](https://docs.docker.com/compose/) ≥ 2.20
- (Opcional, para desarrollo local) Python 3.12+

---

## Instalación y puesta en marcha

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd trazabilidad_activos
```

### 2. Configurar variables de entorno del backend

```bash
cp inventario-mongo/.env.example inventario-mongo/backend/.env.dev
```

Editar `inventario-mongo/backend/.env.dev` con los valores apropiados (ver sección [Variables de entorno](#variables-de-entorno)).

### 3. Configurar variables de entorno del frontend

Editar `flet_inventario/.env`:

```env
API_BASE_URL=http://localhost:8000/api
```

> En producción, reemplazar `localhost` por el hostname o IP del servidor backend.

### 4. Levantar los servicios

```bash
cd inventario-mongo
docker compose up --build
```

Los tres servicios se inician en orden:
1. **mongo** — espera a que el replica set `rs0` esté activo.
2. **backend** — Django en `http://localhost:8000`.
3. **frontend** — Flet web en `http://localhost:8081`.

### 5. Cargar datos iniciales (opcional)

```bash
docker compose exec backend python seed_database.py
```

El script crea usuarios de prueba, categorías, subcategorías, bodegas y artículos de ejemplo.

---

## Carga de datos en la base de datos

### Opción A — Script de seed (datos de ejemplo)

El archivo `inventario-mongo/backend/seed_database.py` puebla la base de datos con un conjunto completo de datos de demostración. Ejecutarlo dentro del contenedor:

```bash
cd inventario-mongo
docker compose exec backend python seed_database.py
```

> **Advertencia:** el script elimina todos los datos existentes (ítems, movimientos, instalaciones, catálogos, vehículos) antes de insertar los nuevos. Los **usuarios se conservan**.

Lo que crea el seed:

| Colección | Cantidad | Detalle |
|-----------|----------|---------|
| Usuarios | 3 | `admin` / `tecnico` / `administrativo` (solo si no existen) |
| Categorías | 8 | Equipos de Red, Servidores, Energía, Videovigilancia, Telefonía IP, Herramientas, Materiales, Activos de Oficina |
| Subcategorías | 17 | Routers, Switches, Firewalls, APs, Racks, NAS, UPS, PDU, Cámaras, DVR/NVR, Teléfonos, Herramientas Manuales/Eléctricas, Cableado, Consumibles, Mobiliario, Equipos de Computación |
| Bodegas | 3 | Norte (Quito), Sur (Guayaquil), Austro (Cuenca) |
| Clientes | 5 | Corporación Alpha, Banco Meridional, Hospital Metropolitano, Municipio de Guayaquil, Universidad Técnica Nacional |
| Proveedores | 5 | TechGlobal, Cisco, HP Enterprise, Hikvision, APC Schneider |
| Vehículos | 3 | Toyota Hilux, Chevrolet NHR, Hyundai H1 |
| Ítems | 33 | Equipos, herramientas y materiales con trazabilidad inicial |
| Movimientos | ≥ 27 | Un movimiento `INGRESO_BODEGA → STOCK` por cada equipo creado |

**Credenciales de prueba creadas por el seed:**

| Usuario | Contraseña | Rol |
|---------|-----------|-----|
| `admin` | `admin123` | admin |
| `tecnico` | `tecnico123` | tecnico |
| `administrativo` | `admin123` | administrativo |

---

### Opción B — API REST (producción / datos reales)

Todo dato real debe ingresarse a través de la API. El flujo recomendado es el siguiente:

#### 1. Autenticarse y obtener el token

```bash
curl -X POST http://localhost:8000/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

Respuesta:
```json
{ "token": "<JWT>", "user": { "username": "admin", "rol": "admin" } }
```

Usar ese token en todos los demás requests:
```
Authorization: Bearer <JWT>
```

#### 2. Crear catálogos maestros (orden obligatorio)

Los ítems dependen de subcategorías, que a su vez dependen de categorías. Respetar el orden:

**a) Categoría**
```bash
curl -X POST http://localhost:8000/api/inventory/categories/ \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"nombre_categoria": "Equipos de Red"}'
```

**b) Subcategoría** (requiere el `id` de la categoría)
```bash
curl -X POST http://localhost:8000/api/inventory/subcategories/ \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"categoria": "<id_categoria>", "nombre": "Switches"}'
```

**c) Bodega**
```bash
curl -X POST http://localhost:8000/api/inventory/stores/ \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"nombre_bodega": "Bodega Principal", "ubicacion": {"ciudad": "Quito", "sector": "Norte"}}'
```

**d) Cliente**
```bash
curl -X POST http://localhost:8000/api/inventory/customers/ \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"nombre_cliente": "Empresa XYZ", "sucursal": "Matriz", "ubicacion": {"ciudad": "Quito"}}'
```

**e) Proveedor**
```bash
curl -X POST http://localhost:8000/api/inventory/suppliers/ \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"nombre_proveedor": "Distribuidor ABC", "ubicacion": {"pais": "Ecuador", "ciudad": "Quito"}}'
```

**f) Vehículo**
```bash
curl -X POST http://localhost:8000/api/inventory/vehicles/ \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"marca": "Toyota", "modelo": "Hilux", "placa": "ABC-1234", "anio": 2023}'
```

#### 3. Registrar un ítem (activo)

Los tipos válidos para `tipo_item` son: `equipo`, `herramienta`, `material`, `general`.  
Los valores de `criticidad` son: `alta`, `media`, `baja`.

```bash
curl -X POST http://localhost:8000/api/inventory/items/ \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "codigo": "SW-001",
    "nombre": "Switch Cisco Catalyst 9200",
    "subcategoria": "<id_subcategoria>",
    "tipo_item": "equipo",
    "marca": "Cisco",
    "modelo": "Catalyst 9200",
    "serial": "FDO2248A01Z",
    "criticidad": "alta",
    "ubicacion_actual_id": "<id_bodega>"
  }'
```

Los equipos ingresan en estado `INGRESO_BODEGA`. Las herramientas y materiales ingresan directamente en `STOCK`.

#### 4. Cambiar el estado de un ítem (transición)

El sistema valida que la transición sea permitida según la máquina de estados.

```bash
curl -X POST http://localhost:8000/api/inventory/items/<id_item>/transition/ \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "next_state": "STOCK",
    "notes": "Ingreso verificado y aprobado."
  }'
```

Cada transición genera automáticamente un movimiento en la colección `movimientos`.

#### 5. Crear una instalación (Facility)

```bash
curl -X POST http://localhost:8000/api/inventory/facilities/ \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "codigo_instalacion": "OT-2024-001",
    "cliente": "<id_cliente>",
    "tecnico": "<id_usuario_tecnico>",
    "direccion_instalacion": "Av. Amazonas N35-17, Quito",
    "fecha_programada": "2024-12-01T08:00:00Z",
    "items_planificados": [
      {"item_id": "<id_item>", "destino_final": "cliente"}
    ],
    "servicios": [
      {"detalle": "Instalación de red LAN", "descripcion": "Configuración y tendido de cableado estructurado Cat6"}
    ]
  }'
```

#### 6. Crear un usuario

```bash
curl -X POST http://localhost:8000/api/users/ \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "nuevo_tecnico",
    "password": "ContraseñaSegura123",
    "rol": "tecnico"
  }'
```

Roles disponibles: `admin`, `tecnico`, `administrativo`.

---

### Opción C — Desde la interfaz gráfica (Flet)

Todos los catálogos y operaciones también pueden gestionarse directamente desde el frontend en `http://localhost:8081`. La interfaz guía el flujo de creación con formularios validados y proporciona retroalimentación visual del estado de cada activo.

---

### Colecciones MongoDB y su propósito

| Colección | Modelo | Descripción |
|-----------|--------|-------------|
| `usuarios` | User | Cuentas de acceso con roles y contraseñas Argon2 |
| `categorias` | Category | Clasificación principal de activos |
| `subcategorias` | SubCategory | Clasificación secundaria ligada a una categoría |
| `bodegas` | Store | Almacenes físicos donde residen los activos |
| `clientes` | Customer | Empresas o entidades que reciben los servicios |
| `proveedores` | Supplier | Empresas que suministran los activos |
| `vehiculos` | Vehicle | Vehículos usados en instalaciones de campo |
| `items` | Item | Activos individuales con estado y trazabilidad |
| `movimientos` | Movement | Registro inmutable de cada cambio de estado (append-only) |
| `instalaciones` | Facility | Órdenes de trabajo con sus activos y servicios asociados |

---

## Variables de entorno

### Backend (`inventario-mongo/backend/.env.dev`)

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `DJANGO_SECRET_KEY` | Clave secreta Django (≥ 50 caracteres en producción) | `cambiar-en-produccion-clave-muy-larga` |
| `DJANGO_DEBUG` | Modo debug | `True` / `False` |
| `DJANGO_SETTINGS_MODULE` | Módulo de settings activo | `config.settings.dev` |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos, separados por coma | `localhost,127.0.0.1,backend` |
| `DJANGO_LANGUAGE_CODE` | Idioma | `es-ec` |
| `DJANGO_TIME_ZONE` | Zona horaria | `America/Guayaquil` |
| `MONGO_DB_HOST` | URI completa de MongoDB (preferida) | `mongodb://mongo:27017/inventario_db?directConnection=true` |
| `MONGO_DB_NAME` | Nombre de la base de datos | `inventario_db` |
| `MONGO_HOST` | Host MongoDB (alternativa a URI) | `mongo` |
| `MONGO_PORT` | Puerto MongoDB | `27017` |
| `CORS_ALLOWED_ORIGINS` | Orígenes CORS permitidos | `http://localhost:8081,http://127.0.0.1:8081` |
| `LOG_LEVEL` | Nivel de logging | `INFO` |

> **Producción**: establecer `DJANGO_DEBUG=False`, generar una `DJANGO_SECRET_KEY` única y configurar `CORS_ALLOWED_ORIGINS` con el dominio real.

### Frontend (`flet_inventario/.env`)

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `API_BASE_URL` | URL base de la API REST del backend | `http://localhost:8000/api` |

---

## API REST — Endpoints principales

Todos los endpoints requieren el header:
```
Authorization: Bearer <token>
```

### Autenticación

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/users/login/` | Obtener token JWT |

### Usuarios

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/users/` | Listar usuarios |
| POST | `/api/users/` | Crear usuario |
| GET/PUT/DELETE | `/api/users/<id>/` | Detalle, actualizar, eliminar |

### Inventario — Ítems

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/inventory/items/` | Listar ítems (filtros: estado, tipo, búsqueda) |
| POST | `/api/inventory/items/` | Registrar nuevo ítem |
| GET/PUT/DELETE | `/api/inventory/items/<id>/` | Detalle, actualizar, eliminar |
| POST | `/api/inventory/items/<id>/transition/` | Cambiar estado con validación de máquina de estados |

### Inventario — Movimientos

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/inventory/movements/` | Listar movimientos (filtros: tipo, OT, fechas) |
| GET | `/api/inventory/movements/stats/` | Estadísticas de movimientos |
| GET | `/api/inventory/movements/<item_id>/history/` | Historial de un ítem |

### Instalaciones (Facilities)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET/POST | `/api/inventory/facilities/` | Listar / crear instalaciones |
| GET/PUT | `/api/inventory/facilities/<id>/` | Detalle / actualizar |
| POST | `/api/inventory/facilities/<id>/start/` | Iniciar instalación |
| POST | `/api/inventory/facilities/<id>/finish/` | Finalizar instalación |
| POST | `/api/inventory/facilities/<id>/close/` | Cerrar instalación |
| POST | `/api/inventory/facilities/<id>/cancel/` | Cancelar instalación |
| GET | `/api/inventory/facilities/<id>/report/` | Descargar acta en PDF |

### Catálogos

| Ruta | Descripción |
|------|-------------|
| `/api/inventory/categories/` | Categorías |
| `/api/inventory/subcategories/` | Subcategorías |
| `/api/inventory/stores/` | Bodegas |
| `/api/inventory/customers/` | Clientes |
| `/api/inventory/suppliers/` | Proveedores |
| `/api/inventory/vehicles/` | Vehículos |

---

## Máquina de estados de ítems

### Equipos (`tipo_item = equipo`)

```
INGRESO_BODEGA → STOCK → RESERVADO → SALIDA_INSTALACION → INSTALADO_CLIENTE
                   │                          │
                   └──────────────────────────┴→ REINGRESO_BODEGA → STOCK
                                                → DEVOLUCION_PROVEEDOR
                                                → OBSOLETO
                                                → ACTIVO_EN_CAMPO
```

### Herramientas (`tipo_item = herramienta`)

```
STOCK → RESERVADA → EN_USO → STOCK
          │                → EN_MANTENIMIENTO → STOCK
          └──────────────────────────────────→ OBSOLETA
```

### Materiales (`tipo_item = material`)

```
STOCK → RESERVADO → CONSUMIDO
          │       → PARCIALMENTE_USADO → STOCK
          └─────────────────────────────────→ OBSOLETO
```

---

## Tipos de movimiento

| Tipo | Descripción |
|------|-------------|
| `ENTRADA` | Ingreso de ítem al sistema o bodega |
| `SALIDA` | Egreso del sistema o bodega |
| `AJUSTE` | Corrección de estado o ubicación |
| `TRANSFERENCIA` | Traslado entre bodegas |
| `BAJA` | Ítem dado de baja definitivamente |
| `RESERVA` | Asignación a una orden de trabajo |
| `INSTALACION` | Instalación permanente en cliente |
| `RETORNO` | Reingreso a bodega desde campo |
| `SALIDA_HERRAMIENTA` | Herramienta sale a instalación |
| `RETORNO_HERRAMIENTA` | Herramienta regresa a bodega |
| `CONSUMO` | Material consumido totalmente |
| `RETORNO_PARCIAL` | Sobrante de material regresa a bodega |

---

## Generación de actas PDF

El endpoint `/api/inventory/facilities/<id>/report/` genera el acta **RE-SIGC-SI-AS-1.0** en PDF mediante:

1. **python-docx** rellena el template `template_acta_servicio.docx` con los datos de la instalación (cliente, técnico, dirección, servicios, equipos entregados, firmas).
2. **LibreOffice headless** convierte el `.docx` resultante a PDF.
3. El PDF se retorna como respuesta binaria (`application/pdf`).

El template se encuentra en `inventario-mongo/backend/config/apps/inventory/assets/template_acta_servicio.docx`.

---

## Roles de usuario

Los roles se definen en el módulo `config.apps.users.models`. Controlan el acceso a los endpoints a través del sistema RBAC integrado.

---

## Desarrollo local (sin Docker)

### Backend

```bash
cd inventario-mongo/backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Asegurarse de tener MongoDB corriendo localmente en puerto 27017
# con replica set rs0 iniciado

cp ../.env.example .env.dev
# Editar .env.dev con MONGO_DB_HOST=mongodb://localhost:27017/inventario_db?directConnection=true

export DJANGO_SETTINGS_MODULE=config.settings.dev  # Windows: set ...
python manage.py migrate
python manage.py runserver
```

### Frontend

```bash
cd flet_inventario
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Editar .env con API_BASE_URL=http://localhost:8000/api

flet run main.py                   # modo escritorio
flet run --web --port 8081 main.py  # modo web
```

---

## Comandos Docker útiles

```bash
# Levantar en background
docker compose up -d --build

# Ver logs del backend
docker compose logs -f backend

# Acceder al shell del backend
docker compose exec backend python manage.py shell

# Detener todos los servicios
docker compose down

# Detener y eliminar volúmenes (BORRA la base de datos)
docker compose down -v
```

---

## Health check

```
GET /api/health/
```

Retorna `200 OK` con el estado del servidor. No requiere autenticación.

---

## Seguridad

- Contraseñas hasheadas con **Argon2** (ISO 27001 A.10.1).
- JWT con expiración configurable; no se usa `djangorestframework-simplejwt`.
- Rate limiting: 60 req/min anónimos, 300 req/min autenticados, 5 req/min en login.
- Headers de seguridad: HSTS, X-Frame-Options DENY, X-Content-Type-Options, XSS Protection.
- CORS restringido a orígenes configurados explícitamente.
- Colección de movimientos **append-only**: ningún endpoint permite DELETE o UPDATE sobre movimientos (ISO 27001 A.12.4.1).
