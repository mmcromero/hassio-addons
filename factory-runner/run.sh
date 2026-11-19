#!/bin/bash
set -euo pipefail
umask 077

echo "[STARTUP] Factory Runner — modo restrito"

# Segredos vêm somente das opções privadas do Home Assistant.
OPTIONS_FILE="/data/options.json"
if [ ! -r "$OPTIONS_FILE" ]; then
    echo "[ERROR] Configuração do add-on indisponível; início recusado" >&2
    exit 1
fi
RUNNER_AUTH_TOKEN="$(jq -r '.runner_auth_token // empty' "$OPTIONS_FILE")"
export RUNNER_AUTH_TOKEN

if [ "${#RUNNER_AUTH_TOKEN}" -lt 32 ]; then
    echo "[ERROR] Token do runner ausente ou curto; início recusado" >&2
    exit 1
fi

# O serviço permanece acessível somente por localhost do container.
export RUNNER_BIND_HOST=127.0.0.1
exec python3 -u /app/server.py
