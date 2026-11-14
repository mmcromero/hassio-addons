#!/usr/bin/env bash
set -euo pipefail

# Ambiente CI isolado. Não acessa o Home Assistant nem publica imagem.
name="pager-ci-smoke-$$"
volume="pager-ci-data-$$"
image="pager-virtual:ci"
cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker volume create "$volume" >/dev/null
start() {
  docker run --detach --platform linux/arm64 --name "$name" \
    -v "$volume:/data" -e PORT=8095 -e HOST=0.0.0.0 "$image" >/dev/null
  for i in $(seq 1 45); do
    if docker exec "$name" node --input-type=module -e "
      const r = await fetch('http://127.0.0.1:8095/api/health');
      if (!r.ok) process.exit(2);
    " >/dev/null 2>&1; then return; fi
    sleep 2
  done
  docker logs "$name" >&2 || true
  echo 'Pager não iniciou em ARM64' >&2
  exit 1
}

start
docker exec -w /app "$name" node --input-type=module -e "
  import db from './src/db.js';
  const now = Date.now();
  db.prepare('INSERT INTO restaurantes (id, nome, slug, created_at) VALUES (?, ?, ?, ?)')
    .run('rest-ci', 'Restaurante CI', 'rest-ci', now);
  db.prepare('INSERT INTO pedidos (id, restaurante_id, numero, token, status, created_at) VALUES (?, ?, ?, ?, ?, ?)')
    .run('pedido-ci', 'rest-ci', 54321, 'token-ci-persistente', 'preparo', now);
  db.close();
"
docker rm -f "$name" >/dev/null

# Reinicia a imagem ARM64 com o MESMO volume, simulando ciclo de vida do add-on.
start
docker exec -w /app "$name" node --input-type=module -e "
  import db from './src/db.js';
  if (db.pragma('integrity_check', {simple:true}) !== 'ok') process.exit(2);
  const pedido = db.prepare('SELECT restaurante_id, numero, token, status FROM pedidos WHERE id=?').get('pedido-ci');
  if (!pedido || pedido.restaurante_id !== 'rest-ci' || pedido.numero !== 54321 ||
      pedido.token !== 'token-ci-persistente' || pedido.status !== 'preparo') process.exit(3);
  const rest = db.prepare('SELECT id FROM restaurantes WHERE id=?').get('rest-ci');
  if (!rest) process.exit(4);
  db.close();
"
echo 'Pager ARM64: inicialização, gravação, reinício e SQLite persistente aprovados.'
