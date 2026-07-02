#!/bin/bash
# ============================================================
# deploy_inventarios.sh
# Sistema de Inventarios DataCom — Script de despliegue
# Ejecutar como root o con sudo en el servidor 10.11.121.101
# ============================================================

set -euo pipefail

# ─── Colores ───────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

container_exists() {
    docker inspect "$1" >/dev/null 2>&1
}

connect_container_network() {
    local network_name="$1"
    local container_name="$2"
    local alias_name="$3"

    container_exists "$container_name" || return 0

    if docker inspect -f '{{json .NetworkSettings.Networks}}' "$container_name" | grep -q "\"$network_name\""; then
        return 0
    fi

    warn "Conectando $container_name a red $network_name (alias: $alias_name)"
    docker network connect --alias "$alias_name" "$network_name" "$container_name"
}

post_deploy_autoheal() {
    local network_name="inventarios_datacom_net"
    log "Auto-heal post-deploy: validando red Docker interna"

    if ! docker network inspect "$network_name" >/dev/null 2>&1; then
        err "Red esperada '$network_name' no existe. Revisa docker-compose.yml"
    fi

    connect_container_network "$network_name" "inv_dc_backend" "backend"
    connect_container_network "$network_name" "inv_dc_frontend" "frontend"
    connect_container_network "$network_name" "inv_dc_mongo" "mongo"

    docker exec inv_dc_backend python - <<'PY'
import socket
socket.gethostbyname("mongo")
print("backend->mongo DNS OK")
PY

    docker exec inv_dc_frontend python - <<'PY'
import requests
r = requests.get("http://backend:8000/api/health/", timeout=8)
print(f"frontend->backend health={r.status_code}")
if r.status_code != 200:
    raise SystemExit(1)
PY
}

# ─── Configuración ─────────────────────────────────────────
APP_DIR="/opt/inventarios_datacom"
REPO_URL="https://github.com/mlogacho/inventariosdatacom.git"
BACKEND_HOST_PORT="127.0.0.1:8060"
FRONTEND_HOST_PORT="127.0.0.1:8061"
DOMAIN="inventarios.datacom.ec"
DB_NAME="inventarios_datacom"
COMPOSE_PROJECT="inventarios_datacom"
CRM_API_BASE_URL="http://10.11.121.101:8088"
PUBLIC_IP_URL="http://10.11.121.101:8070"

# Puertos ya en uso por otras apps (NO usar):
# 8081 WebISO | 8090 Prospeccion | 8088 CRM | 8082 Tickets
# 8005 DAIA   | 8030 ACTAS       | 8010 FastAPI

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   Inventarios DataCom — Despliegue en producción     ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ─── 0. Verificar prerequisitos ────────────────────────────
log "Verificando prerequisitos..."

# Docker
if ! command -v docker &>/dev/null; then
    err "Docker no está instalado. Instálalo con: curl -fsSL https://get.docker.com | sh"
fi

# Docker Compose (plugin v2 o standalone)
if docker compose version &>/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose &>/dev/null; then
    DC="docker-compose"
else
    err "Docker Compose no está instalado."
fi
log "Docker Compose: $DC"

# Git
if ! command -v git &>/dev/null; then
    err "Git no está instalado. Instálalo con: apt-get install -y git"
fi

# Python3
if ! command -v python3 &>/dev/null; then
    err "Python3 no está instalado."
fi

# Nginx
if ! command -v nginx &>/dev/null; then
    warn "Nginx no encontrado, se omitirá la configuración del proxy."
    NGINX_AVAILABLE=false
else
    NGINX_AVAILABLE=true
fi

# Nota operativa: en actualizaciones, estos puertos pueden estar ocupados por
# contenedores de Inventarios en ejecución. Se informa y se continúa.
if ss -tlnp 2>/dev/null | grep -q ":8061 " ; then
    warn "Puerto 8061 detectado en uso. Se asume despliegue existente y se actualizará en sitio."
fi
if ss -tlnp 2>/dev/null | grep -q ":8060 " ; then
    warn "Puerto 8060 detectado en uso. Se asume despliegue existente y se actualizará en sitio."
fi

# ─── 1. Clonar / actualizar repositorio ────────────────────
log "Paso 1/5 — Repositorio..."

if [ -d "$APP_DIR/.git" ]; then
    warn "El directorio $APP_DIR ya existe. Actualizando..."
    cd "$APP_DIR"
    git fetch origin
    git reset --hard origin/main
    log "Repositorio actualizado."
else
    log "Clonando $REPO_URL en $APP_DIR..."
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
    log "Repositorio clonado."
fi

# ─── 2. Variables de entorno ────────────────────────────────
log "Paso 2/5 — Archivos de configuración..."

# Generar secret key segura
DJANGO_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))" 2>/dev/null \
  || python3 -c "import os,base64; print(base64.b64encode(os.urandom(48)).decode())")

# Backend .env.dev
cat > "$APP_DIR/inventario-mongo/backend/.env.dev" << EOF
# ============================================================
# Generado automáticamente por deploy_inventarios.sh
# ============================================================

# Django Core
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
DJANGO_SETTINGS_MODULE=config.settings.base
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,${DOMAIN},10.11.121.101
DJANGO_LANGUAGE_CODE=es-ec
DJANGO_TIME_ZONE=America/Guayaquil

# MongoDB
MONGO_DB_NAME=${DB_NAME}
MONGO_DB_HOST=mongodb://mongo:27017/${DB_NAME}?directConnection=true
MONGO_HOST=mongo
MONGO_PORT=27017

# CORS (frontend en Docker + acceso directo por IP)
CORS_ALLOWED_ORIGINS=http://${DOMAIN},http://10.11.121.101:8061,http://127.0.0.1:8061

# Integración ERP/CRM (SSO)
CRM_API_BASE_URL=${CRM_API_BASE_URL}

# Logging
LOG_LEVEL=INFO
EOF

# Frontend .env
cat > "$APP_DIR/flet_inventario/.env" << EOF
# URL del backend — dentro de Docker usa el nombre de servicio
API_BASE_URL=http://backend:8000/api
EOF

log "Archivos .env creados."

# ─── 3. Parchear docker-compose.yml ─────────────────────────
log "Paso 3/5 — Configurando puertos (sin interferir apps existentes)..."

cd "$APP_DIR/inventario-mongo"

# Respaldo del compose original
cp -f docker-compose.yml docker-compose.yml.orig

python3 << 'PYEOF'
import re

with open('docker-compose.yml', 'r') as f:
    content = f.read()

# --- Puertos ---
# Backend: 8000 -> 127.0.0.1:8060:8000
content = re.sub(r'- "8000:8000"', '- "127.0.0.1:8060:8000"', content)
# Frontend: 8081:8080 -> 127.0.0.1:8061:8080
content = re.sub(r'- "8081:8080"', '- "127.0.0.1:8061:8080"', content)
# MongoDB: no exponer al host (acceso solo desde la red Docker)
content = re.sub(r'- "27017:27017"', '# Puerto MongoDB no expuesto al host', content)

# --- Renombrar contenedores para evitar conflictos con otros proyectos ---
content = content.replace('container_name: django_backend', 'container_name: inv_dc_backend')
content = content.replace('container_name: flet_frontend', 'container_name: inv_dc_frontend')
content = content.replace('container_name: mongo_db',       'container_name: inv_dc_mongo')

with open('docker-compose.yml', 'w') as f:
    f.write(content)

print("  docker-compose.yml actualizado:")
print("    backend  -> 127.0.0.1:8060")
print("    frontend -> 127.0.0.1:8061")
print("    mongodb  -> solo red interna Docker")
PYEOF

# ─── 4. Construir y levantar contenedores ───────────────────
log "Paso 4/6 — Construyendo e iniciando servicios Docker..."
warn "Esto puede tardar varios minutos (LibreOffice es grande)..."

$DC -p "$COMPOSE_PROJECT" up -d --build

log "Esperando que los servicios estén listos..."
sleep 20

log "Paso 5/6 — Auto-heal de conectividad interna"
post_deploy_autoheal

# Verificar estado
echo ""
log "Estado de los contenedores:"
$DC -p "$COMPOSE_PROJECT" ps
echo ""

# Paso 6/6 - Health checks de servicios
# Health check del backend
BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8060/api/health/ 2>/dev/null || echo "000")
if [ "$BACKEND_STATUS" = "200" ]; then
    log "Backend API respondiendo OK (HTTP 200)"
else
    warn "Backend no responde aún en /api/health/ (código: $BACKEND_STATUS). Puede necesitar más tiempo."
fi

# Health check vía Nginx temporal (8070), con reintentos para evitar falsos 502
FRONT_8070=$(curl -s -L --retry 25 --retry-delay 1 --retry-all-errors -o /dev/null -w "%{http_code}" http://127.0.0.1:8070/ 2>/dev/null || echo "000")
API_8070=$(curl -s -L --retry 25 --retry-delay 1 --retry-all-errors -o /dev/null -w "%{http_code}" http://127.0.0.1:8070/api/health/ 2>/dev/null || echo "000")
if [ "$FRONT_8070" = "200" ] && [ "$API_8070" = "200" ]; then
    log "Nginx temporal 8070 OK (frontend y api en 200)"
else
    warn "Validacion 8070 incompleta: frontend=$FRONT_8070 api=$API_8070"
fi

# ─── 5. Configurar Nginx ────────────────────────────────────
if [ "$NGINX_AVAILABLE" = "true" ]; then
    log "Paso 5/5 — Configurando Nginx..."

    cat > /etc/nginx/sites-available/inventarios_datacom << 'NGINXEOF'
# ────────────────────────────────────────────────────────────
# inventarios.datacom.ec — Sistema de Inventarios DataCom
# Frontend Flet web (WebSocket)
# ────────────────────────────────────────────────────────────
server {
    listen 80;
    server_name inventarios.datacom.ec;

    location / {
        proxy_pass         http://127.0.0.1:8061;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # WebSocket — requerido por Flet
        proxy_http_version 1.1;
        proxy_set_header   Upgrade    $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_read_timeout 86400;
    }
}

# ────────────────────────────────────────────────────────────
# inventarios-api.datacom.ec — API REST Django (opcional)
# ────────────────────────────────────────────────────────────
server {
    listen 80;
    server_name inventarios-api.datacom.ec;

    location / {
        proxy_pass         http://127.0.0.1:8060;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
NGINXEOF

    ln -sf /etc/nginx/sites-available/inventarios_datacom /etc/nginx/sites-enabled/

    if nginx -t 2>&1; then
        systemctl reload nginx
        log "Nginx recargado correctamente."
    else
        err "Error en configuración de Nginx. Revisa /etc/nginx/sites-available/inventarios_datacom"
    fi
else
    warn "Nginx no disponible. Omitiendo configuración del proxy."
fi

# ─── Resumen ────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║               ✓  DESPLIEGUE COMPLETADO               ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Frontend:  http://inventarios.datacom.ec"
echo "  API REST:  http://inventarios-api.datacom.ec/api"
echo "  Acceso IP temporal: ${PUBLIC_IP_URL}"
echo "  CRM API base (SSO): ${CRM_API_BASE_URL}"
echo ""
echo "  Modo de acceso: SSO desde ERP DataCom (sin login manual local)"
echo ""
echo "  Para cargar datos de ejemplo:"
echo "    docker compose -p ${COMPOSE_PROJECT} -f ${APP_DIR}/inventario-mongo/docker-compose.yml exec backend python seed_database.py"
echo ""
echo "  Para ver logs:"
echo "    docker compose -p ${COMPOSE_PROJECT} -f ${APP_DIR}/inventario-mongo/docker-compose.yml logs -f"
echo ""
echo "  App dir: ${APP_DIR}"
echo ""
