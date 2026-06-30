# Changelog

Todas las modificaciones relevantes del proyecto se registran en este archivo.

## [2026-06-30] - Fix definitivo SSO ERP (sin pantalla de acceso manual)

### Corregido
- Se evita el bloqueo de `POST /api/users/sso-login/` cuando el cliente envia `Authorization` local expirado.
- `JWTAuthentication` deja pasar endpoints `AllowAny` aunque exista cabecera `Bearer` invalida/expirada.

### Cambiado
- Cliente HTTP de Flet permite desactivar `Authorization` por endpoint.
- `users/login/` y `users/sso-login/` ahora se envian sin token local heredado.
- Vista de login ajustada a flujo SSO-only:
  - no se muestra formulario manual;
  - si token ERP es valido, acceso directo;
  - si token ERP es invalido/expirado, redireccion a ERP DataCom.

### Despliegue
- Commit aplicado en servidor: `d9991fb`
- Verificacion operativa:
  - `http://10.11.121.101:8070/` -> 200
  - `http://10.11.121.101:8070/api/health/` -> 200

## [2026-06-30] - Deploy v2 con rollback automatico

### Agregado
- Script `deploy_inventarios_v2.sh` para despliegue transaccional en servidor.

### Caracteristicas
- Backup previo de:
  - `inventario-mongo/docker-compose.yml`
  - `inventario-mongo/backend/.env.dev`
  - `flet_inventario/.env`
  - `/etc/nginx/sites-available/inventarios_datacom`
- Rollback automatico en error:
  - restaura commit previo
  - restaura archivos de configuracion
  - reconstruye stack Docker
  - recarga Nginx cuando aplica
- Validaciones post-deploy con reintentos:
  - `http://127.0.0.1:8060/api/health/`
  - `http://127.0.0.1:8070/`
  - `http://127.0.0.1:8070/api/health/`

## [2026-06-30] - SSO obligatorio + CRM endpoint interno + continuidad operativa

### Cambiado
- Acceso web de Inventarios ajustado a modo SSO obligatorio desde ERP DataCom.
- Se retiro el acceso manual por usuario/contrasena en la pantalla de login.
- Se agrego mensaje de acceso restringido cuando no existe `sso_token` en URL.

### Corregido
- Integracion CRM para SSO corregida en entorno servidor mediante:
  - `CRM_API_BASE_URL=http://10.11.121.101:8088`
- Se elimina dependencia de resolucion DNS externa para `crm.datacom.ec` desde contenedor de Inventarios.

### Operacion
- Publicacion temporal de acceso por continuidad en:
  - `http://10.11.121.101:8070`
- Validaciones posteriores al ajuste:
  - Frontend via 8070: 200
  - API health via 8070: 200
  - `POST /api/users/sso-login/` responde flujo esperado (token invalido/expirado cuando corresponde).

## [2026-06-30] - Integracion ERP SSO + clientes CRM activos

### Agregado
- Endpoint `POST /api/users/sso-login/` para intercambio de `sso_token` ERP por JWT local de Inventarios.
- Endpoint `GET /api/inventory/crm/customers/` para obtener clientes activos desde CRM.
- Servicio backend para validacion online de token ERP y consulta de clientes en CRM.

### Cambiado
- Login web de Inventarios ahora intenta autologin cuando llega `sso_token` en URL.
- Selector de cliente en flujo de descarga/instalacion muestra `nombre | RUC | ciudad`.

### Comportamiento operativo
- Si CRM no esta en linea, Inventarios informa claramente la indisponibilidad de CRM.

## [2026-06-30] - Recuperacion de acceso/login

### Contexto
- Se reporto "dejo de funcionar" en login web por URL temporal, con frontend y API activos.

### Corregido
- Se normalizo el acceso del usuario admin en backend.
- Se valido autenticacion end-to-end en:
  - backend directo (127.0.0.1:8060)
  - Nginx temporal (127.0.0.1:8070)

### Verificado
- API health backend: 200
- API health via Nginx temporal: 200
- Login API backend: success true
- Login API Nginx temporal: success true

### Impacto
- Servicio restaurado sin interrupciones a otros sistemas del servidor.

## [2026-06-30] - Inventario-only + despliegue productivo

### Agregado
- Regla centralizada de alcance de inventarios en backend:
  - origen de ingreso fijo: Matriz: Oficinas Cumbaya
  - bodegas permitidas: Bodega General Conocoto, Mini Bodega Cumbaya
- Validaciones en serializador de items para exigir bodega valida en equipos.
- Campo origen_ingreso en modelo Item.
- Auto-bootstrap de bodegas permitidas cuando se consultan bodegas.

### Cambiado
- API de inventario reducida al alcance operativo actual.
- Gestion de bodegas restringida para evitar altas/renombres/eliminaciones fuera de alcance.
- Sidebar y ruteo frontend simplificados a modulos de inventario.

### Removido
- Modulos fuera de alcance en navegacion principal frontend.
- Endpoints de proveedores, vehiculos e instalaciones del router principal de inventario.

### Despliegue
- Commit desplegado: fdaa7e5
- Servidor: 10.11.121.101
- Ruta de despliegue: /opt/inventarios_datacom
- Verificacion post-despliegue:
  - frontend por puerto temporal: 200 (http://127.0.0.1:8070/)
  - api health por puerto temporal: 200 (http://127.0.0.1:8070/api/health/)
