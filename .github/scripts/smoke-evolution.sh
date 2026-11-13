#!/usr/bin/env bash
set -Eeuo pipefail

WORK="$(mktemp -d)"
NAME="evolution-ci-smoke"
cleanup() {
  docker logs "$NAME" 2>&1 | tail -100 || true
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

mkdir -p "$WORK/data"
printf '%s\n' '{"api_key":"ci_dummy_key_only","server_url":"http://127.0.0.1:18080","webhook_url":""}' > "$WORK/data/options.json"

start() {
  docker run -d --name "$NAME" --platform linux/arm64 \
    --publish 127.0.0.1:18080:8080 --mount "type=bind,src=$WORK/data,dst=/data" \
    evolution-api:test >/dev/null
}
wait_ready() {
  for i in $(seq 1 180); do
    if [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null || echo false)" != true ]; then
      echo "Falha: container encerrou"
      return 1
    fi
    if docker exec "$NAME" sh -c 'pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1' 2>/dev/null; then
      HTTP="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 3 http://127.0.0.1:18080/manager || true)"
      if [ "$HTTP" != "000" ] && [ "$HTTP" -lt 500 ]; then
        echo "OK: PostgreSQL pronto e HTTP /manager respondeu $HTTP"
        return 0
      fi
    fi
    sleep 3
  done
  echo "Falha: API ou PostgreSQL indisponível em 540 s"
  return 1
}
start
wait_ready
docker exec "$NAME" sh -c "su-exec postgres psql -h /data/postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='evolution'\" postgres | grep -qx 1"
test -f "$WORK/data/postgres/PG_VERSION"
test -f "$WORK/data/postgres-password"
test -d "$WORK/data/instances"
echo "OK: banco, senha e sessões em /data"

docker stop --time 60 "$NAME" >/dev/null
docker rm "$NAME" >/dev/null
start
wait_ready
echo "OK: restart com dados persistentes"
