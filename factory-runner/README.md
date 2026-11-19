# Fábrica de Software — Factory Runner

**Estado atual (19/11/2026):** distribuição `0.1.0-rc.4` **PUBLICADA no catálogo** pelo PR #45, merge `350fa3c8a756c405b6766cca53bd25fe84aef9f1`. **Instalação e homologação da RC4 não foram realizadas nesta auditoria.** Não repetir publicação, build ARM64 externo ou testes estáticos já cobertos sem causa técnica concreta.

Add-on Home Assistant para a infraestrutura da Fábrica de Software.
Neste candidato, a API é protegida e **não executa correções automáticas nem publica pacotes**.
O código-fonte de desenvolvimento permanece no repositório privado
`mmcromero/orquestrador-projetos-base`; esta pasta é uma distribuição isolada.

> **Não instalar como substituto operacional** do runner anterior: o fechamento de pacotes
> e a correção de Issues respondem `403` por projeto até homologação de autorização,
> isolamento e recuperação funcional.

## Funcionalidades do modo restrito (descrição funcional; histórico RC2–RC4)

- `GET /api/status`: exige token e informa modo de pré-verificação somente leitura.
- `GET /api/projects`: lista perfis pré-configurados, sem credenciais.
- `POST /api/preflight`: consulta SHA, versão e política dos repositórios locais previamente provisionados; não altera Git.
- `POST /api/prepare`: exportação local com blob aprovado, UID não-root e sandbox Bubblewrap obrigatório; indisponibilidade é 503 auditado, sem fallback. Sem commit/push/publicação.
- Avisaqui é primeiro perfil, mas o Runner possui versão e ciclo próprios.
- `POST /api/fechar-pacote` e `POST /api/corrigir-issue`: exigem token e retornam `403` após validação.
- Não inclui chaves reais; sem push, merge, publicação ou execução de código gerado por IA.
- Porta 9876 desabilitada no host por padrão; bind apenas em localhost no container.
- Log sanitizado em `/data/factory-runner/audit.jsonl`.

Veja [DOCS.md](DOCS.md), [OPERACAO-ESTEIRA.md](OPERACAO-ESTEIRA.md) e [CHANGELOG.md](CHANGELOG.md).

**Origem de desenvolvimento:** `mmcromero/orquestrador-projetos-base:feat/factory-runner-esteira-001` (Issue #2, PR #3).
**Destino:** `mmcromero/hassio-addons:factory-runner/`.
