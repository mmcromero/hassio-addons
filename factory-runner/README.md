# Fábrica de Software — Factory Runner

**Versão:** 0.1.0-rc.1 (modo restrito / pré-homologação)

Add-on Home Assistant para a infraestrutura da Fábrica de Software.
Neste candidato, a API é protegida e **não executa correções automáticas nem publica pacotes**.
O código-fonte de desenvolvimento permanece no repositório privado
`mmcromero/orquestrador-projetos-base`; esta pasta é uma distribuição isolada.

> **Não instalar como substituto operacional** do runner anterior: o fechamento de pacotes
> e a correção de Issues respondem `403` por projeto até homologação de autorização,
> isolamento e recuperação funcional.

## Estado desta versão

- `GET /api/status`: exige token e retorna status restrito.
- `POST /api/fechar-pacote` e `POST /api/corrigir-issue`: exigem token e retornam `403` após validação.
- Não inclui chaves reais; sem push, merge, publicação ou execução de código gerado por IA.
- Porta 9876 desabilitada no host por padrão; bind apenas em localhost no container.
- Log sanitizado em `/data/factory-runner/audit.jsonl`.

Veja [DOCS.md](DOCS.md) e [CHANGELOG.md](CHANGELOG.md).

**Origem:** `mmcromero/orquestrador-projetos-base:fix/factory-runner-sec-20261118`.
**Destino:** `mmcromero/hassio-addons:factory-runner/`.
