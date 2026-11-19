#!/usr/bin/env python3
"""P0: classify add-on release impediments without Actions, Docker or network."""
import argparse
import json
from pathlib import Path

GENERIC = {"no_arm64_emulator", "no_qemu", "no_actions", "no_external_docker", "no_external_runner", "no_terminal", "no_github_dns"}

def classify(registry, addon, decision, reason="", evidence="", alternative="", affected_step="", authorized=False):
    ids = {entry["id"] for entry in registry["addons"]}
    if addon not in ids:
        return "ERRO_DE_CADASTRO", 2
    if decision == "prepared":
        return ("PRONTO_PARA_GATES_PERTINENTES" if authorized else "PREPARADO_AGUARDANDO_AUTORIZACAO"), 0
    if reason in GENERIC:
        return "DESVIO_DE_PROCEDIMENTO", 3
    if not all((reason.strip(), evidence.strip(), alternative.strip(), affected_step.strip())):
        return "BLOQUEIO_NAO_COMPROVADO", 3
    return "BLOQUEIO_ESPECIFICO_DOCUMENTADO", 0

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--addon", required=True)
    p.add_argument("--decision", choices=("prepared", "blocked"), required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--evidence", default="")
    p.add_argument("--alternative", default="")
    p.add_argument("--affected-step", default="")
    p.add_argument("--authorized", action="store_true", help="Registra autorização já existente, não cria autorização")
    p.add_argument("--registry", type=Path, default=Path(__file__).resolve().parents[1] / ".github/addon-registry.json")
    args = p.parse_args()
    status, code = classify(json.loads(args.registry.read_text(encoding="utf-8")), args.addon, args.decision, args.reason, args.evidence, args.alternative, args.affected_step, args.authorized)
    print(json.dumps({"status": status, "note": "Consulte CONTRIBUTING.md; resultados não aprovam testes, publicação ou instalação"}, ensure_ascii=False))
    return code

if __name__ == "__main__":
    raise SystemExit(main())
