#!/bin/bash
# deploy_inventarios_v2.sh
# Deploy transaccional de Inventarios DataCom con rollback automatico.

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

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
    fail "Red esperada '$network_name' no existe. Revisa docker-compose.yml"
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

APP_DIR="/opt/inventarios_datacom"
REPO_URL="https://github.com/mlogacho/inventariosdatacom.git"
BRANCH="main"
DOMAIN="inventarios.datacom.ec"
DB_NAME="inventarios_datacom"
COMPOSE_PROJECT="inventarios_datacom"
CRM_API_BASE_URL="http://10.11.121.101:8088"
PUBLIC_IP_URL="http://10.11.121.101:8070"

INV_COMPOSE_DIR="$APP_DIR/inventario-mongo"
INV_COMPOSE_FILE="$INV_COMPOSE_DIR/docker-compose.yml"
BACKEND_ENV="$APP_DIR/inventario-mongo/backend/.env.dev"
FRONTEND_ENV="$APP_DIR/flet_inventario/.env"
NGINX_SITE="/etc/nginx/sites-available/inventarios_datacom"

if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  fail "Docker Compose no instalado"
fi

for bin in docker git python3 curl; do
  command -v "$bin" >/dev/null 2>&1 || fail "Falta dependencia: $bin"
done

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="/home/datacomerp/backups/inventarios_v2_${TS}"
mkdir -p "$BACKUP_DIR"

PRE_COMMIT=""
if [ -d "$APP_DIR/.git" ]; then
  PRE_COMMIT="$(git -C "$APP_DIR" rev-parse HEAD || true)"
fi

echo "$PRE_COMMIT" > "$BACKUP_DIR/pre_commit.txt"

backup_file() {
  local src="$1"
  local dst="$2"
  if [ -f "$src" ]; then
    cp -f "$src" "$dst"
  fi
}

log "Creando respaldo inicial en $BACKUP_DIR"
backup_file "$INV_COMPOSE_FILE" "$BACKUP_DIR/docker-compose.yml.bak"
backup_file "$BACKEND_ENV" "$BACKUP_DIR/backend.env.dev.bak"
backup_file "$FRONTEND_ENV" "$BACKUP_DIR/frontend.env.bak"
backup_file "$NGINX_SITE" "$BACKUP_DIR/inventarios_datacom.nginx.bak"

ROLLBACK_DONE=0
rollback() {
  if [ "$ROLLBACK_DONE" -eq 1 ]; then
    return
  fi
  ROLLBACK_DONE=1

  warn "Iniciando rollback..."

  if [ -n "$PRE_COMMIT" ] && [ -d "$APP_DIR/.git" ]; then
    warn "Restaurando codigo al commit previo: $PRE_COMMIT"
    git -C "$APP_DIR" reset --hard "$PRE_COMMIT" || true
  fi

  if [ -f "$BACKUP_DIR/backend.env.dev.bak" ]; then
    cp -f "$BACKUP_DIR/backend.env.dev.bak" "$BACKEND_ENV" || true
  fi
  if [ -f "$BACKUP_DIR/frontend.env.bak" ]; then
    cp -f "$BACKUP_DIR/frontend.env.bak" "$FRONTEND_ENV" || true
  fi
  if [ -f "$BACKUP_DIR/docker-compose.yml.bak" ]; then
    cp -f "$BACKUP_DIR/docker-compose.yml.bak" "$INV_COMPOSE_FILE" || true
  fi
  if [ -f "$BACKUP_DIR/inventarios_datacom.nginx.bak" ]; then
    cp -f "$BACKUP_DIR/inventarios_datacom.nginx.bak" "$NGINX_SITE" || true
  fi

  if [ -d "$INV_COMPOSE_DIR" ]; then
    (cd "$INV_COMPOSE_DIR" && $DC -p "$COMPOSE_PROJECT" up -d --build) || true
  fi

  if command -v nginx >/dev/null 2>&1; then
    nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
  fi

  warn "Rollback finalizado. Revisa estado manualmente."
}

on_err() {
  warn "Fallo detectado en despliegue. Ejecutando rollback automatico."
  rollback
  exit 1
}
trap on_err ERR

log "Paso 1/6 - Sincronizando repositorio"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  git clone "$REPO_URL" "$APP_DIR"
  git -C "$APP_DIR" checkout "$BRANCH"
fi

log "Paso 2/6 - Generando archivos de entorno"
DJANGO_SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")"

cat > "$BACKEND_ENV" <<EOF
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
DJANGO_SETTINGS_MODULE=config.settings.base
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,${DOMAIN},10.11.121.101
DJANGO_LANGUAGE_CODE=es-ec
DJANGO_TIME_ZONE=America/Guayaquil

MONGO_DB_NAME=${DB_NAME}
MONGO_DB_HOST=mongodb://mongo:27017/${DB_NAME}?directConnection=true
MONGO_HOST=mongo
MONGO_PORT=27017

CORS_ALLOWED_ORIGINS=http://${DOMAIN},http://10.11.121.101:8061,http://127.0.0.1:8061
CRM_API_BASE_URL=${CRM_API_BASE_URL}
LOG_LEVEL=INFO
EOF

cat > "$FRONTEND_ENV" <<EOF
API_BASE_URL=http://backend:8000/api
EOF

log "Paso 3/6 - Ajustando docker-compose para puertos seguros"
python3 <<PYEOF
import re
from pathlib import Path

p = Path("$INV_COMPOSE_FILE")
content = p.read_text(encoding="utf-8")

content = re.sub(r'-\s*"127\.0\.0\.1:8060:8000"', '- "127.0.0.1:8060:8000"', content)
content = re.sub(r'-\s*"127\.0\.0\.1:8061:8080"', '- "127.0.0.1:8061:8080"', content)
content = re.sub(r'-\s*"8000:8000"', '- "127.0.0.1:8060:8000"', content)
content = re.sub(r'-\s*"8081:8080"', '- "127.0.0.1:8061:8080"', content)
content = re.sub(r'-\s*"27017:27017"', '- "27017"', content)

content = content.replace('container_name: django_backend', 'container_name: inv_dc_backend')
content = content.replace('container_name: flet_frontend', 'container_name: inv_dc_frontend')
content = content.replace('container_name: mongo_db', 'container_name: inv_dc_mongo')

p.write_text(content, encoding="utf-8")
PYEOF

log "Paso 4/6 - Levantando stack"
(cd "$INV_COMPOSE_DIR" && $DC -p "$COMPOSE_PROJECT" up -d --build)

log "Paso 5/7 - Auto-heal de conectividad interna"
post_deploy_autoheal

log "Paso 6/7 - Validando salud con reintentos"
curl -s -L --retry 30 --retry-delay 1 --retry-all-errors -o /dev/null http://127.0.0.1:8060/api/health/
curl -s -L --retry 30 --retry-delay 1 --retry-all-errors -o /dev/null http://127.0.0.1:8070/
curl -s -L --retry 30 --retry-delay 1 --retry-all-errors -o /dev/null http://127.0.0.1:8070/api/health/

BACKEND_STATUS="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8060/api/health/)"
FRONT_8070="$(curl -s -L -o /dev/null -w "%{http_code}" http://127.0.0.1:8070/)"
API_8070="$(curl -s -L -o /dev/null -w "%{http_code}" http://127.0.0.1:8070/api/health/)"

[ "$BACKEND_STATUS" = "200" ] || fail "Backend health invalido: $BACKEND_STATUS"
[ "$FRONT_8070" = "200" ] || fail "Frontend 8070 invalido: $FRONT_8070"
[ "$API_8070" = "200" ] || fail "API 8070 invalido: $API_8070"

log "Paso 7/7 - Aplicando y validando Nginx"
if command -v nginx >/dev/null 2>&1; then
cat > "$NGINX_SITE" <<'NGINXEOF'
server {
    listen 80;
    server_name inventarios.datacom.ec;

    location / {
        proxy_pass         http://127.0.0.1:8061;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        proxy_http_version 1.1;
        proxy_set_header   Upgrade    $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_read_timeout 86400;
    }
}

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

ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/inventarios_datacom
nginx -t
systemctl reload nginx
fi

POST_COMMIT="$(git -C "$APP_DIR" rev-parse --short HEAD)"

echo
log "Deploy v2 completado"
echo "  Commit previo: ${PRE_COMMIT:-N/A}"
echo "  Commit actual: ${POST_COMMIT}"
echo "  Frontend dominio: http://inventarios.datacom.ec"
echo "  API dominio: http://inventarios-api.datacom.ec/api"
echo "  Acceso IP temporal: ${PUBLIC_IP_URL}"
echo "  CRM API base (SSO): ${CRM_API_BASE_URL}"
echo "  Backup/rollback dir: ${BACKUP_DIR}"

trap - ERR
