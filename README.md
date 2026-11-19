# Add-ons Home Assistant — mmcromero

> **P0 — PUBLICAÇÃO UNIVERSAL (19/11/2026):** todo executor, independentemente do cargo ou produto, deve seguir o [procedimento único de publicação e testes proporcionais](CONTRIBUTING.md) antes de fechar/publicar um add-on ou declarar impedimento. **Build ARM64 externo, QEMU e Actions não são gates rotineiros.** O build e a execução reais pelo Supervisor, quando aplicáveis, são verificados na homologação no Home Assistant. Publicação no GitHub não comprova instalação ou homologação. Bloqueios reais de segurança permanecem válidos.

Repositório central para add-ons do Home Assistant OS, incluindo Raspberry Pi 4 (`aarch64`).

## Instalar na loja do Home Assistant

Em **Configurações → Add-ons/Apps → Loja → ⋮ → Repositórios**, adicione:

`https://github.com/mmcromero/hassio-addons`

Atualize a loja. Apenas add-ons integrados à `main` ficam disponíveis pela URL acima.

## Estrutura permanente

```text
hassio-addons/
├── repository.yaml
├── README.md
├── CONTRIBUTING.md
├── .gitignore
├── .github/workflows/validate-addons.yml
└── evolution-api/
    ├── config.yaml
    ├── Dockerfile
    ├── run.sh
    ├── README.md
    ├── DOCS.md
    └── CHANGELOG.md
```

Cada futuro add-on ganha uma **pasta na raiz**, com `config.yaml`, `Dockerfile` (para build local), documentação e versão independentes. Não crie outro `repository.yaml` em subpastas.

## Catálogo ativo na `main` (levantamento 19/11/2026)

| Diretório | Nome de exibição | Versão conferida | Arquitetura |
|---|---|---|---|
| `evolution-api/` | Fábrica de Softwares - Evolution API WhatsApp | 0.1.0 | aarch64 |
| `pager-virtual/` | Pager Virtual (*novo título preparado na fonte; aguarda exportação controlada*) | 0.1.20-rc.11 | aarch64, amd64 |
| `umdoislab-central/` | Fábrica de Softwares - 12Labs Central de Atendimento | 0.4.0 | aarch64 |
| `factory-runner/` | Fábrica de Softwares - Factory Runner | 0.1.0-rc.2 | aarch64, amd64 |

O cadastro verificável dos quatro add-ons está em [`.github/addon-registry.json`](.github/addon-registry.json). As quatro pastas possuem os mesmos arquivos `icon.png` e `logo.png` copiados da identidade atual do Kanban, sem alteração de seus bytes. O nome do Avisaqui deve ser publicado pelo exportador oficial, para preservar `SOURCE_PROVENANCE.json` e a correspondência com a fonte privada.

**Fora deste catálogo:** Artesão Digital usa `mmcromero/fabricacao-e-orcamentos-ha`; Kanban usa `mmcromero/fabrica-de-ideias-kanban`. Não remova essas lojas do Home Assistant sem verificar instalação, versões e preservação dos dados. O catálogo Git não mostra quais lojas estão cadastradas no Raspberry.


## Continuidade e arquitetura de automações

- **[CONTINUIDADE.md](docs/CONTINUIDADE.md)** — estado real, evidências, roteiro de homologação e instruções para retomar em outro chat.
- **[ARQUITETURA-AUTOMACOES.md](docs/ARQUITETURA-AUTOMACOES.md)** — decisão de manter n8n principal no Raspberry e usar processamento externo no computador apenas quando necessário.

Atualize esses documentos quando uma etapa for **confirmada por evidências** ou uma decisão mudar. Não confunda proposta, CI e homologação real.

## Regra de publicação da loja — decisão do proprietário 18/11/2026

**Este repositório é a distribuição de add-ons (ResAddon), não a fonte de desenvolvimento do PG Virtual.** A `main` pública recebe pacotes instaláveis e candidatos RC para teste no Home Assistant, quando exportados da RC privada, conferidos e autorizados para publicação do lote. O Avisaqui é distribuído **somente na pasta `pager-virtual/`**, preservando `repository.yaml`, outros add-ons e o restante da árvore. A URL de loja usada pela instalação existente é `https://github.com/mmcromero/hassio-addons`, que consulta esta `main` sem sufixo de branch; publicar apenas em uma branch RC alternativa não atualiza essa instalação. Uma publicação aqui **não homologa** código nem autoriza integrar a `main` privada `mmcromero/pager-virtual`, que permanece protegida até homologação.

**Laboratório de protótipos:** `mmcromero/fabrica-de-ideias-prototipos:main` também pode receber protótipos navegáveis dos diversos projetos, limitados à pasta `projetos/<id>/` e seu registro no catálogo. Não confundir demonstração com fonte privada ou add-on compilado. Publicação não executa Actions nem instala apps no HA.

## Regras de manutenção

- Para pacotes autorizados da loja, publicar somente a pasta do add-on afetado na `main` após conferir integridade, versão, escopo e proveniência. Branch/PR são opcionais conforme revisão necessária. Não usar Actions sem autorização específica.
- Versão independente por add-on, registrada em `CHANGELOG.md`.
- Preferir tags fixas em vez de `:latest`.
- A CI **não instala nem publica** add-ons no HA; quando a configuração usa Dockerfile sem imagem pré-compilada, o Supervisor pode compilar no dispositivo-alvo durante a instalação/atualização. O procedimento universal define os testes e exceções. Ausência de emulação ARM64 não constitui, por si só, impedimento técnico.
- Segredos, bancos e sessões nunca entram no Git.
- Não migrar os add-ons antigos para este repositório sem uma decisão específica.

Veja [CONTRIBUTING.md](CONTRIBUTING.md) e o guia individual da Evolution API.


## Factory Runner (integração em desenvolvimento)

O candidato `factory-runner/0.1.0-rc.1` foi preparado em branch isolada
com registro no catálogo e build ARM64 manual, **sem publicação na main**.
O pacote permanece em modo de contenção: autenticação obrigatória e
operações privilegiadas bloqueadas. Consulte
[`factory-runner/README.md`](factory-runner/README.md) e
[`factory-runner/DOCS.md`](factory-runner/DOCS.md).
