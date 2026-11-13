#!/bin/sh
set -eu

log() { printf '[evolution-addon] %s\n' "$*"; }
fail() { printf '[evolution-addon] ERRO: %s\n' "$*" >&2; exit 1; }

OPTIONS=/data/options.json
[ -f "$OPTIONS" ] || fail "Supervisor nao forneceu options.json"
command -v jq >/dev/null 2>&1 || fail "jq ausente"

API_KEY=$(jq -r '.api_key // ""' "$OPTIONS")
SERVER_URL=$(jq -r '.server_url // ""' "$OPTIONS")
WEBHOOK_URL=$(jq -r '.webhook_url // ""' "$OPTIONS")
[ -n "$API_KEY" ] || fail "Configure api_key no Home Assistant"
[ -n "$SERVER_URL" ] || fail "Configure server_url no Home Assistant"

mkdir -p /data/postgres /data/instances
chmod 0700 /data/postgres
chown postgres:postgres /data/postgres

# Alpine pode instalar os executaveis versionados fora do PATH.
INITDB=$(find /usr -type f -name initdb 2>/dev/null | head -n 1)
[ -n "$INITDB" ] && [ -x "$INITDB" ] || fail "initdb ausente"
PG_BIN=$(dirname "$INITDB")
for binary in pg_ctl pg_isready; do
  if ! command -v "$binary" >/dev/null 2>&1 && [ ! -x "$PG_BIN/$binary" ]; then
    fail "$binary ausente"
  fi
done

PASSFILE=/data/postgres-password
if [ ! -f "$PASSFILE" ]; then
  umask 077
  od -An -N32 -tx1 /dev/urandom | tr -d ' \n' > "$PASSFILE"
fi
chmod 0600 "$PASSFILE"
chown postgres:postgres "$PASSFILE"
PG_PASS=$(cat "$PASSFILE")
[ -n "$PG_PASS" ] || fail "Senha interna do PostgreSQL vazia"

if [ ! -e /data/postgres/PG_VERSION ]; then
  log "Inicializando PostgreSQL em /data/postgres"
  chown -R postgres:postgres /data/postgres
  su-exec postgres "$INITDB" -D /data/postgres --username=postgres \
    --pwfile="$PASSFILE" --auth-local=peer --auth-host=scram-sha-256
fi

log "Iniciando PostgreSQL em 127.0.0.1:5432"
su-exec postgres "$PG_BIN/pg_ctl" -D /data/postgres -l /data/postgres/server.log \
  -o '-h 127.0.0.1 -p 5432 -k /data/postgres' start || fail "Falha ao iniciar PostgreSQL"

APP_PID=''
shutdown() {
  trap - INT TERM EXIT
  if [ -n "$APP_PID" ]; then
    kill "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
  fi
  su-exec postgres "$PG_BIN/pg_ctl" -D /data/postgres -m fast stop || true
}
trap shutdown INT TERM EXIT

READY=0
n=0
while [ "$n" -lt 60 ]; do
  if pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1 || "$PG_BIN/pg_isready" -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    READY=1
    break
  fi
  n=$((n + 1))
  sleep 1
done
[ "$READY" -eq 1 ] || fail "PostgreSQL nao respondeu"

if ! su-exec postgres psql -h /data/postgres -tAc "SELECT 1 FROM pg_database WHERE datname='evolution'" postgres | grep -qx 1; then
  su-exec postgres createdb -h /data/postgres -O postgres evolution
fi

export SERVER_URL
export AUTHENTICATION_API_KEY="$API_KEY"
export DATABASE_PROVIDER=postgresql
export DATABASE_CONNECTION_URI="postgresql://postgres:${PG_PASS}@127.0.0.1:5432/evolution"
export DATABASE_CONNECTION_CLIENT_NAME=evolution_api
export DATABASE_SAVE_DATA_INSTANCE=true
export DATABASE_SAVE_DATA_NEW_MESSAGE=true
export DATABASE_SAVE_MESSAGE_UPDATE=true
export DATABASE_SAVE_DATA_CONTACTS=true
export DATABASE_SAVE_DATA_CHATS=true
export CACHE_REDIS_ENABLED=false
export CACHE_LOCAL_ENABLED=true
export WEBHOOK_GLOBAL_URL="$WEBHOOK_URL"
if [ -n "$WEBHOOK_URL" ]; then
  export WEBHOOK_GLOBAL_ENABLED=true
  export WEBHOOK_EVENTS_MESSAGES_UPSERT=true
else
  export WEBHOOK_GLOBAL_ENABLED=false
fi

cd /evolution
log "Aplicando migracoes e iniciando Evolution API"
# Preserva a etapa de deploy de banco usada na imagem upstream v2.3.7.
/bin/bash -c '. ./Docker/scripts/deploy_database.sh && exec npm run start:prod' &
APP_PID=$!
wait "$APP_PID"
