#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "ERRO: configure github_read_token na aba Configuração do app."
  exit 2
fi

SOURCE_DIR="$(mktemp -d /tmp/design-system-source-XXXXXX)"
LOG="/tmp/design-system-lab-validation.log"
cleanup() { rm -rf -- "$SOURCE_DIR"; }
trap cleanup EXIT

export GIT_ASKPASS=/app/git-askpass.sh
export GIT_TERMINAL_PROMPT=0

echo "Buscando mmcromero/design-system:desenvolvimento com credencial somente leitura..."
git clone --quiet --depth 1 --single-branch --branch desenvolvimento \
  https://github.com/mmcromero/design-system.git "$SOURCE_DIR"
unset GIT_ASKPASS GIT_TERMINAL_PROMPT GITHUB_TOKEN

SOURCE_SHA="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
echo "SOURCE_SHA=$SOURCE_SHA"
echo "Branch: desenvolvimento"
echo "SHA validado: $SOURCE_SHA"

export DS_BROWSER_TOOLS=/opt/browser-tools
export DS_PLAYWRIGHT_BROWSERS_PATH=/opt/pw-cache
export DS_PLAYWRIGHT_READY=1

cd "$SOURCE_DIR"
: > "$LOG"
bash scripts/validate-lote-e.sh "$SOURCE_SHA" 2>&1 | tee "$LOG"

EVIDENCE_DIR="$(sed -n 's/^Evidências: //p' "$LOG" | head -n 1)"
if [[ -z "$EVIDENCE_DIR" ]]; then
  echo "ERRO: o validador terminou sem informar o diretório de evidências."
  exit 3
fi
DEMO_DIR="$EVIDENCE_DIR/checkout/apps/demo/dist"
test -s "$DEMO_DIR/index.html"
echo "EVIDENCE_DIR=$EVIDENCE_DIR"
echo "DEMO_DIR=$DEMO_DIR"
echo "VALIDATION_RESULT=PASS"
