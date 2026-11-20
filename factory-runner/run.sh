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

# Multi-project GitHub sync is opt-in and operates on the approved profiles.
# The old workspace_sync_project is ignored; no project is selected by hand.
RUNNER_WORKSPACE_SYNC_ENABLED="$(jq -r '.workspace_sync_enabled // false' "$OPTIONS_FILE")"
RUNNER_GITHUB_READ_TOKEN="$(jq -r '.github_read_token // empty' "$OPTIONS_FILE")"
RUNNER_WORKSPACE_AUTO_PREPARE="$(jq -r '.workspace_auto_prepare // false' "$OPTIONS_FILE")"
export RUNNER_WORKSPACE_SYNC_ENABLED RUNNER_GITHUB_READ_TOKEN RUNNER_WORKSPACE_AUTO_PREPARE

# No host TCP port; subprocesses inherit a non-root UID.
export RUNNER_BIND_HOST=127.0.0.1
# Non-mutating startup diagnostic; run under the same non-root UID as the API.
# A BLOCKED probe does not disable API/status: /api/prepare still fails closed.
env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/nonexistent su-exec runner python3 -I -u /app/runtime_probe.py
# A observacao de perfil nao modifica AppArmor nem substitui isolamento.
env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/nonexistent su-exec runner python3 -I -u /app/controlled_worker.py --task diagnose | sed 's/^/[WORKER] /' || echo "[WORKER] diagnostic blocked"
# Synthetic Git/manifest check: no project access, no inherited token, no host mounts.
# Diagnostics stay available if this check is blocked on the HA platform.
env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/nonexistent su-exec runner python3 -I -u /app/declarative_runtime_probe.py || echo "[DECLARATIVE] readiness probe unavailable; API still fail-closed"
# Full synthetic API check: temporary local Git checkouts, ephemeral loopback
# listener and test-only bearer; never touches project workspaces or real token.
env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/nonexistent su-exec runner python3 -I -u /app/factory_e2e_probe.py || echo "[E2E] WARN: functional probe unavailable; API stays policy-gated"
exec su-exec runner python3 -u /app/server.py
