#!/bin/bash
set -euo pipefail
RUNNER_API_PROBE_BOOT_STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || true)"
export RUNNER_API_PROBE_BOOT_STARTED_AT
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
for path in /data /data/factory-runner /data/factory-runner/workspaces /data/factory-runner/preparations /data/factory-runner/executions /data/factory-runner/audit.jsonl /data/factory-runner-authority; do
    if [ -L "$path" ]; then
        echo "[ERROR] Caminho privado com symlink; início recusado" >&2
        exit 1
    fi
done
# Validate isolated service directories and derive immutable owner identity
# configuration from the explicitly configured HA user ID and HTTPS origin.
# This never generates signing keys/passwords or opens the publication gate.
AUTHORITY_ROOT="/data/factory-runner-authority"
if [ ! -e "$AUTHORITY_ROOT" ]; then
    install -d -m 0711 -o root -g root "$AUTHORITY_ROOT"
fi
env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/nonexistent \
    /usr/bin/python3 -I /app/owner_bootstrap.py "$AUTHORITY_ROOT"

# Run the synthetic isolation probe only after persistent authority layout validation succeeds.
/usr/bin/python3 -I -u /app/isolation_backend_probe.py || echo "[ISOLATION-BACKEND] ERROR: diagnostic unavailable; execution remains blocked"
/usr/bin/python3 -I -u /app/bounded_stream_probe.py || echo "[BOUNDED-STREAM] ERROR: diagnostic unavailable; project execution remains blocked"

# A private HA volume may start at 0700 root. Grant the service group search
# only (no listing/write), without changing options.json ownership or mode.
chgrp runner /data
chmod g=x /data
install -d -m 0710 -o runner -g publisher /data/factory-runner
install -d -m 2710 -o runner -g publisher /data/factory-runner/workspaces
install -d -m 2750 -o runner -g publisher /data/factory-runner/preparations
install -d -m 0700 -o runner -g runner /data/factory-runner/executions
if [ -e /data/factory-runner/audit.jsonl ]; then
    chown runner:runner /data/factory-runner/audit.jsonl
    chmod 0600 /data/factory-runner/audit.jsonl
fi

# Separate publisher credential. Never reuse the read-only workspace token.
GITHUB_PUBLISH_TOKEN="$(jq -r '.github_publish_token // empty' "$OPTIONS_FILE")"
PUBLISH_TOKEN_FILE="$AUTHORITY_ROOT/publisher/github-token"
if [ -L "$PUBLISH_TOKEN_FILE" ]; then
    echo "[PUBLISHER] BLOCKED: token path is a symlink" >&2
    exit 1
fi
if [ -n "$GITHUB_PUBLISH_TOKEN" ]; then
    if [ -e "$PUBLISH_TOKEN_FILE" ]; then
        TOKEN_META="$(stat -c '%u:%h' "$PUBLISH_TOKEN_FILE")"
        if [ ! -f "$PUBLISH_TOKEN_FILE" ] || [ "$TOKEN_META" != "$(id -u publisher):1" ]; then
            echo "[PUBLISHER] BLOCKED: existing token file is unsafe" >&2
            exit 1
        fi
    fi
    TOKEN_TMP="$(mktemp "$AUTHORITY_ROOT/publisher/.github-token.XXXXXX")"
    printf '%s' "$GITHUB_PUBLISH_TOKEN" > "$TOKEN_TMP"
    chown publisher:publisher "$TOKEN_TMP"
    chmod 0600 "$TOKEN_TMP"
    mv -f "$TOKEN_TMP" "$PUBLISH_TOKEN_FILE"
elif [ -e "$PUBLISH_TOKEN_FILE" ]; then
    TOKEN_META="$(stat -c '%u:%h' "$PUBLISH_TOKEN_FILE")"
    if [ ! -f "$PUBLISH_TOKEN_FILE" ] || [ "$TOKEN_META" != "$(id -u publisher):1" ]; then
        echo "[PUBLISHER] BLOCKED: existing token file is unsafe" >&2
        exit 1
    fi
    rm -f "$PUBLISH_TOKEN_FILE"
fi
unset GITHUB_PUBLISH_TOKEN

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
SERVICE_PIDS=()
APPROVAL_SOCKET="$AUTHORITY_ROOT/consent-ipc/approval.sock"
if jq -e '(.owner_password // "") != "" or (.owner_password_confirm // "") != ""' "$OPTIONS_FILE" >/dev/null; then
    if [ ! -f "$AUTHORITY_ROOT/approval-config/runtime.json" ]; then
        echo "[OWNER-SETTINGS] BLOCKED: configure HA identity and HTTPS Ingress before submitting the one-time password" >&2
        exit 1
    fi
fi
if [ -f "$AUTHORITY_ROOT/approval-config/runtime.json" ]; then
    env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin su-exec approval python3 -I -u -c 'import sys,runpy;sys.path.insert(0,"/app");runpy.run_path("/app/approval_service.py",run_name="__main__")' &
    SERVICE_PIDS+=("$!")
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
        [ -S "$APPROVAL_SOCKET" ] && break
        sleep 0.1
    done
    if [ ! -S "$APPROVAL_SOCKET" ]; then
        echo "[APPROVAL] BLOCKED: approval IPC did not become ready" >&2
        if jq -e '(.owner_password // "") != "" or (.owner_password_confirm // "") != ""' "$OPTIONS_FILE" >/dev/null; then
            echo "[OWNER-SETTINGS] BLOCKED: enrollment credentials were not processed; correct the approval startup failure" >&2
            exit 1
        fi
    else
        # One-time enrollment is submitted through add-on Settings. The
        # helper calls the root-only approval IPC and clears temporary fields
        # through the Supervisor self-options API before normal services start.
        env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/nonexistent \
            SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN:-}" \
            /usr/bin/python3 -I -c 'import sys,runpy;sys.path.insert(0,"/app");runpy.run_path("/app/owner_settings_enroll.py",run_name="__main__")'
    fi
else
    echo "[APPROVAL] DORMANT: owner identity and HTTPS origin are not configured"
fi

if [ -S "$APPROVAL_SOCKET" ] && [ -f "$AUTHORITY_ROOT/publisher-config/runtime.json" ]; then
    env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin su-exec publisher python3 -I -u -c 'import sys,runpy;sys.path.insert(0,"/app");runpy.run_path("/app/publisher_service.py",run_name="__main__")' &
    SERVICE_PIDS+=("$!")
else
    echo "[PUBLISHER] DORMANT: owner enrollment or pinned runtime configuration is missing"
fi

OWNER_INGRESS_ENABLED="$(jq -r '.owner_ingress_enabled // false' "$OPTIONS_FILE")"
if [ "$OWNER_INGRESS_ENABLED" = "true" ]; then
    if [ -S "$APPROVAL_SOCKET" ] && [ -f "$AUTHORITY_ROOT/owner-ui-config/ingress.json" ]; then
        env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin su-exec owner_ui python3 -I -u -c 'import sys,runpy;sys.path.insert(0,"/app");runpy.run_path("/app/owner_ingress_service.py",run_name="__main__")' &
        SERVICE_PIDS+=("$!")
    else
        echo "[OWNER-UI] BLOCKED: configured owner ingress lacks approval IPC or identity config" >&2
    fi
else
    # Ingress remains available inside HA, but this process serves only a
    # static status page. No owner identity, IPC, consent, or write action.
    env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin su-exec owner_ui python3 -I -u -c 'import sys,runpy;sys.path.insert(0,"/app");sys.argv=["owner_ingress_service.py","--disabled"];runpy.run_path("/app/owner_ingress_service.py",run_name="__main__")' &
    SERVICE_PIDS+=("$!")
fi

su-exec runner python3 -u /app/server.py &
API_PID=$!
# Live API smoke probe inherits only the API token and the sync expectation.
# It exercises reads/preflight only; it never blocks the API or receives GitHub tokens.
(
    export PATH=/usr/sbin:/usr/bin:/sbin:/bin
    export HOME=/nonexistent
    export RUNNER_API_PROBE_EXPECT_WORKSPACES="$RUNNER_WORKSPACE_SYNC_ENABLED"
    export RUNNER_API_PROBE_BOOT_STARTED_AT
    unset RUNNER_GITHUB_READ_TOKEN GITHUB_PUBLISH_TOKEN SUPERVISOR_TOKEN
    exec su-exec runner python3 -I -u /app/runtime_api_probe.py
) &
SERVICE_PIDS+=("$!")
shutdown_services() {
    trap - TERM INT
    kill "$API_PID" 2>/dev/null || true
    for pid in "${SERVICE_PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait "$API_PID" 2>/dev/null || true
    for pid in "${SERVICE_PIDS[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
}
trap shutdown_services TERM INT
set +e
wait "$API_PID"
API_STATUS=$?
set -e
shutdown_services
exit "$API_STATUS"
