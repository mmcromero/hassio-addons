#!/bin/bash
set -euo pipefail

OPTIONS_FILE="/data/options.json"
if [ ! -r "$OPTIONS_FILE" ]; then
  echo "[ERROR] Opções do add-on indisponíveis; início recusado" >&2
  exit 1
fi

GITHUB_TOKEN="$(jq -r '.github_token // empty' "$OPTIONS_FILE")"

# Home Assistant injects these credentials into every app, including the legacy alias.
# Phase 2 does not use the Supervisor API: remove both token names and its endpoint.
unset SUPERVISOR_TOKEN HASSIO_TOKEN SUPERVISOR_API

# Whitelist the Node process environment. Never inherit Supervisor credentials or
# unrelated container variables into the Portal application process.
exec su-exec portal:portal env -i \
  PATH=/usr/local/bin:/usr/bin:/bin \
  NODE_ENV=production \
  PORTAL_MODE=ingress \
  PORTAL_HOST=0.0.0.0 \
  PORT=8099 \
  TZ="${TZ:-UTC}" \
  GITHUB_TOKEN="$GITHUB_TOKEN" \
  node /app/server/index.mjs
