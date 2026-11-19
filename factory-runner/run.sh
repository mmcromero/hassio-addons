#!/bin/bash
set -euo pipefail
umask 077
echo "[STARTUP] Factory Runner (restricted mode)"
# No wildcard safe.directory and no global Git URL rewrite with credentials.
OPTIONS_FILE="/data/options.json"
if [ -f "$OPTIONS_FILE" ]; then
    export RUNNER_AUTH_TOKEN="$(jq -r '.runner_auth_token // empty' "$OPTIONS_FILE")"
    export GEMINI_API_KEY="$(jq -r '.gemini_api_key // empty' "$OPTIONS_FILE")"
    export GITHUB_TOKEN="$(jq -r '.github_token // empty' "$OPTIONS_FILE")"
    export EVOLUTION_API_KEY="$(jq -r '.evolution_api_key // empty' "$OPTIONS_FILE")"
    export EVOLUTION_API_URL="$(jq -r '.evolution_api_url // empty' "$OPTIONS_FILE")"
fi
# Never source a tracked or templated .env (which may contain placeholders).
if [ -z "${RUNNER_AUTH_TOKEN:-}" ]; then
    echo "[ERROR] Runner auth token missing; refusing startup" >&2
    exit 1
fi
exec python3 -u /app/server.py
