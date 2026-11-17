#!/bin/sh
# Docker e este wrapper usam o mesmo bootstrap Node. Sem bashio/s6 na imagem.
# options.json é validado antes de importar SQLite.
set -eu
export DATA_PATH="${DATA_PATH:-/data}"
export PORT="${PORT:-8095}"
cd /app
exec node src/server.js
