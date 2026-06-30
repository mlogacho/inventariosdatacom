# Inventarios DataCom

Sistema de gestion de inventarios y trazabilidad de activos para DataCom.

Estado actual del alcance funcional:
- Gestion de activos (items)
- Trazabilidad de movimientos (append-only)
- Gestion de bodegas restringida al flujo operativo actual
- Dashboard y vistas operativas de inventario

## Reglas de negocio activas

1. Origen de ingreso obligatorio:
- Matriz: Oficinas Cumbaya

2. Bodegas permitidas para ingreso:
- Bodega General Conocoto
- Mini Bodega Cumbaya

3. Para items tipo equipo:
- Debe registrarse una bodega de ingreso valida (una de las dos permitidas).

4. Bodegas operativas protegidas:
- No se permite eliminar las dos bodegas permitidas del alcance.

## Arquitectura

- Frontend: Flet
- Backend: Django + DRF
- Base de datos: MongoDB (MongoEngine)
- Despliegue: Docker Compose + Nginx

Puertos de despliegue en servidor:
- Backend interno: 127.0.0.1:8060
- Frontend interno: 127.0.0.1:8061
- Acceso temporal publicado: http://10.11.121.101:8070

## Estructura principal

- inventario-mongo/
- flet_inventario/
- deploy_inventarios.sh

## API principal

Base path:
- /api/inventory/

Endpoints operativos principales:
- /items/
- /movements/
- /stores/
- /categories/
- /subcategories/

Nota: el modulo fue ajustado a modo inventario. Endpoints fuera de alcance operativo fueron retirados del enrutador principal de inventario.

## Despliegue en servidor (actual)

Ruta de despliegue:
- /opt/inventarios_datacom

Proceso recomendado:

Opcion recomendada (v2 con rollback automatico):

```bash
cd /opt/inventarios_datacom
bash deploy_inventarios_v2.sh
```

Comportamiento de `deploy_inventarios_v2.sh`:
- Crea respaldos de `docker-compose.yml`, `.env.dev`, `.env` y sitio Nginx.
- Si falla una etapa critica, ejecuta rollback automatico a estado previo.
- Valida salud con reintentos en `8060` y `8070` para evitar falsos negativos por arranque.
- Registra carpeta de backup para auditoria y recuperacion manual.

1. Actualizar codigo:

```bash
cd /opt/inventarios_datacom
git checkout main
git pull --ff-only origin main
```

2. Levantar stack:

```bash
cd /opt/inventarios_datacom/inventario-mongo
docker compose up -d --build
```

3. Verificar estado:

```bash
docker compose ps
curl -s -o /dev/null -w "frontend_8070:%{http_code}\n" http://127.0.0.1:8070/
curl -s -o /dev/null -w "api_8070:%{http_code}\n" http://127.0.0.1:8070/api/health/
```

Esperado:
- frontend_8070:200
- api_8070:200

## Frontend (menu actual)

Modulos activos en navegacion principal:
- Dashboard
- Activos
- Movimientos
- Bodegas

## Seguridad y acceso

- Autenticacion con JWT local emitido por Inventarios
- Permisos con RBAC en backend
- Backend publicado detras de Nginx

### Acceso ERP SSO (WebISO)

- Inventarios opera en modo SSO obligatorio desde ERP DataCom.
- El formulario de usuario/contrasena local fue retirado de la vista de acceso.
- Inventarios acepta `sso_token` generado por ERP DataCom y realiza autologin.
- Validacion online del token contra CRM DataCom en:
	- `/api/core/user-permissions/`
- Si la URL no incluye `sso_token`, se muestra mensaje de acceso restringido desde ERP.
- Si CRM no esta en linea, se informa claramente en pantalla.

### Integracion CRM activa en produccion

- Base URL CRM usada por Inventarios (entorno servidor):
	- `CRM_API_BASE_URL=http://10.11.121.101:8088`
- Endpoints CRM consumidos por Inventarios:
	- `POST /api/api-token-auth/`
	- `GET /api/core/user-permissions/`
	- `GET /api/clients/clients/`

### Clientes para descargas

- La seleccion de clientes se obtiene en tiempo real desde CRM.
- Solo se incluyen clientes activos.
- El selector muestra nombre, RUC y ciudad para facilitar busqueda.

## Estado de produccion

Despliegue aplicado con commit:
- df28db7

Fecha de despliegue:
- 2026-06-30

Hotfix operativo aplicado (mismo dia):
- Inventarios publicado temporalmente por IP y puerto para continuidad:
	- `http://10.11.121.101:8070`
- Correccion de entorno CRM en backend para restablecer validacion SSO.

## Mejora operativa aplicada (2026-06-30)

Se aplico una mejora de continuidad operativa para restaurar el acceso al sistema cuando el backend y el frontend estan en linea pero el login devuelve credenciales invalidas.

Validaciones realizadas:
- Health backend directo: 200
- Health API via Nginx temporal: 200
- Login via backend: exitoso
- Login via Nginx temporal: exitoso

Resultado:
- Acceso recuperado sin afectar otros servicios del servidor.

## Troubleshooting rapido

Si acceso desde ERP cae en mensaje "CRM no esta en linea":

1. Verificar variable en backend:

```bash
grep '^CRM_API_BASE_URL=' /opt/inventarios_datacom/inventario-mongo/backend/.env.dev
```

Esperado:
- `CRM_API_BASE_URL=http://10.11.121.101:8088`

2. Verificar endpoint CRM desde servidor:

```bash
curl -s -o /dev/null -w "crm_token_endpoint:%{http_code}\n" \
	http://10.11.121.101:8088/api/api-token-auth/
```

Esperado:
- `crm_token_endpoint:405` en GET (endpoint existe y espera POST)

Si la pantalla de login muestra credenciales invalidas:

1. Verificar salud API:

```bash
curl -s -o /dev/null -w "api_health:%{http_code}\n" http://127.0.0.1:8060/api/health/
curl -s -o /dev/null -w "api_8070:%{http_code}\n" http://127.0.0.1:8070/api/health/
```

2. Verificar login por API:

```bash
curl -s -X POST http://127.0.0.1:8060/api/users/login/ \
	-H "Content-Type: application/json" \
	--data-binary '{"username":"admin","password":"<password>"}'
```

3. Si health esta OK y login falla, restablecer usuario admin desde el contenedor backend:

```bash
cd /opt/inventarios_datacom/inventario-mongo
docker exec -i inv_dc_backend python manage.py shell <<"PY"
from config.apps.users.models.user import User

u = User.objects(username="admin").first()
if not u:
		u = User(username="admin", rol="admin")
u.rol = "admin"
u.set_password("<nueva_clave>")
u.save()
print("admin_ready")
PY
```

4. Luego de resetear credenciales, probar login en la URL temporal:
- http://10.11.121.101:8070
