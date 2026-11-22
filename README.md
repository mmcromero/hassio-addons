# Add-ons Home Assistant — mmcromero

> **AMBIENTE COMPARTILHADO — FONTE CENTRAL (19/11/2026):** antes de perguntar sobre Raspberry Pi, Home Assistant, apps instalados, repositórios da loja, ARM64 ou homologação, consulte o [inventário operacional central](https://github.com/mmcromero/hassio-addons/blob/main/docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md). Não copie a lista de apps para outros projetos; confirme no Supervisor apenas dados voláteis ou decisões críticas. Essa referência não autoriza remover, reiniciar, atualizar ou instalar apps.


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

## Catálogo publicado na `main` — manifests conferidos em 20/11/2026

| Diretório | Nome na loja | Versão | Arquitetura |
|---|---|---|---|
| `evolution-api/` | Fábrica de Softwares - Evolution API WhatsApp | 0.1.0 | aarch64 |
| `pager-virtual/` | Pager Virtual | 0.1.20-rc.11 | aarch64, amd64 |
| `umdoislab-central/` | Fábrica de Softwares - WhatsApp Umdoislab | 0.5.0-rc.1 | aarch64 |
| `factory-runner/` | Fábrica de Softwares - Factory Runner | 0.1.0-rc.19 | aarch64, amd64 |
| `instagram-central/` | Fábrica de Softwares - Central Instagram | 0.1.6 | aarch64 |

O registro [`.github/addon-registry.json`](.github/addon-registry.json) reúne os **cinco** add-ons. Os arquivos `icon.png` e `logo.png` preservam os mesmos blobs de identidade já utilizados no catálogo (SHA `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a` e `7e500016222b0a5bf395be8ed17447edeb3e2af9`).

**Central WhatsApp original:** a distribuição `0.5.0-rc.1` foi publicada no [commit `45d7ec6`](https://github.com/mmcromero/hassio-addons/commit/45d7ec6e28f60ec6f1ef1e3ebc86baf8b44cfbe3), preservando o `slug: umdoislab_central`. **Não equivale à atualização do app instalado no Raspberry.** A homologação depende do Supervisor.

**Duplicação corrigida no catálogo:** a candidata experimental `umdoislab-central-lab/` (`umdoislab_central_lab`) foi retirada da lista pública, conforme a decisão de manter um só aplicativo. O histórico permanece no Git; esta operação **não desinstala add-ons nem remove dados no Home Assistant**, cuja instalação atual não foi comprovada nesta revisão.

**Fora deste catálogo:** Artesão Digital usa `mmcromero/fabricacao-e-orcamentos-ha`; Kanban usa `mmcromero/fabrica-de-ideias-kanban`. Não remova essas lojas do Home Assistant sem verificar instalação, versões e preservação dos dados. O catálogo Git não mostra quais lojas estão cadastradas no Raspberry.

## Continuidade e arquitetura de automações

- **Projeto privado WhatsApp:** `mmcromero/whatsapp-automacoes` (fonte, workflows, histórico e documentação de desenvolvimento). O acesso requer permissão GitHub.
- **Distribuição pública:** este repositório mantém apenas pacotes instaláveis necessários para o Home Assistant e a documentação genérica da loja. Não versionar aqui workflows, segredos ou regras de negócio do WhatsApp.

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


## Padrão para revisão de interfaces

Consulte [UX-STD-001 v0.1 — Organização de telas com prioridade para celular](docs/ux/UX-STD-001_v0.1.md) antes de criar ou revisar telas. A referência reúne agrupamento por tarefa, abas, detalhes sob demanda e critérios de aceite. O [AGENTS.md](AGENTS.md) registra sua aplicação ao escopo de interfaces. Disponibilidade documental não comprova aplicação às telas existentes.
