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

- Autenticacion con JWT
- Permisos con RBAC en backend
- Backend publicado detras de Nginx

## Estado de produccion

Despliegue aplicado con commit:
- fdaa7e5

Fecha de despliegue:
- 2026-06-30
