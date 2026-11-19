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

# A conta do Runner não recebe privilégios de root. Apenas a subárvore
# privada do próprio add-on é administrada; nunca alterar /data/options.json.
for path in /data /data/factory-runner /data/factory-runner/workspaces /data/factory-runner/preparations /data/factory-runner/audit.jsonl; do
    if [ -L "$path" ]; then
        echo "[ERROR] Caminho privado com symlink; início recusado" >&2
        exit 1
    fi
done
# A private HA volume may start at 0700 root. Grant the service group search
# only (no listing/write), without changing options.json ownership or mode.
chgrp runner /data
chmod g=x /data
install -d -m 0700 -o runner -g runner /data/factory-runner
for folder in workspaces preparations; do
    install -d -m 0700 -o runner -g runner "/data/factory-runner/$folder"
done
if [ -e /data/factory-runner/audit.jsonl ]; then
    chown runner:runner /data/factory-runner/audit.jsonl
    chmod 0600 /data/factory-runner/audit.jsonl
fi

# No host TCP port; subprocesses inherit a non-root UID.
export RUNNER_BIND_HOST=127.0.0.1
# Non-mutating startup diagnostic; run under the same non-root UID as the API.
# A BLOCKED probe does not disable API/status: /api/prepare still fails closed.
su-exec runner python3 -I -u /app/runtime_probe.py
exec su-exec runner python3 -u /app/server.py
