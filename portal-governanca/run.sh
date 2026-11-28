#!/bin/bash
set -euo pipefail
OPTIONS_FILE="/data/options.json"
if [ ! -r "$OPTIONS_FILE" ]; then
  echo "[ERROR] Opções do add-on indisponíveis; início recusado" >&2
  exit 1
fi
GITHUB_TOKEN="$(jq -r '.github_token // empty' "$OPTIONS_FILE")"
GITHUB_WRITE_TOKEN="$(jq -r '.github_write_token // empty' "$OPTIONS_FILE")"
N8N_BASE_URL="$(jq -r '.n8n_base_url // empty' "$OPTIONS_FILE")"
N8N_API_KEY="$(jq -r '.n8n_api_key // empty' "$OPTIONS_FILE")"
N8N_INTERNAL_PEER="$(jq -r '.n8n_internal_peer // empty' "$OPTIONS_FILE")"
FACTORY_RUNNER_DISPATCH_TOKEN="$(jq -r '.factory_runner_dispatch_token // empty' "$OPTIONS_FILE")"
# O ledger é persistente e append-only. Preparar o arquivo como root e transferir
# somente sua propriedade ao usuário não-root do BFF, sem alterar seu conteúdo.
LEDGER_PATH="/data/portal-ledger.ndjson"
if [ -L "$LEDGER_PATH" ] || { [ -e "$LEDGER_PATH" ] && [ ! -f "$LEDGER_PATH" ]; }; then
  echo "[ERROR] Caminho do ledger não é um arquivo regular; início recusado" >&2
  exit 1
fi
if [ ! -e "$LEDGER_PATH" ]; then
  : > "$LEDGER_PATH"
fi
chown portal:portal "$LEDGER_PATH"
chmod 0600 "$LEDGER_PATH"
SUPERVISOR_READ_TOKEN="${SUPERVISOR_TOKEN:-}"
# A credencial do Supervisor é entregue somente ao bridge dedicado.
# O papel "default" autoriza leitura de status/info, sem privilégios manager.
if [ -n "$SUPERVISOR_READ_TOKEN" ]; then
  su-exec 65534:65534 env -i \
    PATH=/usr/local/bin:/usr/bin:/bin \
    NODE_ENV=production \
    SUPERVISOR_TOKEN="$SUPERVISOR_READ_TOKEN" \
    node /app/server/supervisor-bridge.mjs &
else
  echo "[WARN] Token Supervisor ausente; inventário HA ficará indisponível" >&2
fi
# Remover aliases e token do shell antes de iniciar o BFF principal.
unset SUPERVISOR_TOKEN HASSIO_TOKEN SUPERVISOR_API SUPERVISOR_READ_TOKEN
# Whitelist explícita: Node principal nunca recebe credenciais do Supervisor.
exec su-exec portal:portal env -i \
  PATH=/usr/local/bin:/usr/bin:/bin \
  NODE_ENV=production \
  PORTAL_MODE=ingress \
  PORTAL_HOST=0.0.0.0 \
  PORT=8099 \
  TZ="${TZ:-UTC}" \
  HA_BRIDGE_URL="http://127.0.0.1:8098" \
  GITHUB_TOKEN="$GITHUB_TOKEN" \
  GITHUB_WRITE_TOKEN="$GITHUB_WRITE_TOKEN" \
  N8N_BASE_URL="$N8N_BASE_URL" \
  N8N_API_KEY="$N8N_API_KEY" \
  N8N_INTERNAL_PEER="$N8N_INTERNAL_PEER" \
  FACTORY_RUNNER_DISPATCH_TOKEN="$FACTORY_RUNNER_DISPATCH_TOKEN" \
  node /app/server/index.mjs
