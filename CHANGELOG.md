# Changelog

Todas las modificaciones relevantes del proyecto se registran en este archivo.

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
