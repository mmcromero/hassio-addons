# Add-ons Home Assistant — mmcromero

> **HA-MCP — LEITURA E ESCRITA COM ESCOPO (atualizado em 25/11/2026):** o proprietário confirmou que habilitou escrita para os agentes executarem diagnóstico, correção, publicação/atualização, instalação e acompanhamento operacional no add-on/projeto abrangido pela missão autorizada. Consulte o [manual operacional HA-MCP](docs/HA-MCP-ACESSO-SOMENTE-LEITURA.md) antes de atuar. A autorização não permite alterar serviços alheios, reiniciar Core/host, excluir/restaurar dados, mudar rede ou rotacionar credenciais sem autorização específica. Verifique a capacidade efetiva das ferramentas na sessão; o registro de somente leitura de 22/11 é histórico. O túnel n8n é uma entrada independente e suas ferramentas/permissões devem ser verificadas separadamente. Recuperação após reinício do Core/host ainda pendente.

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
├── artesaos-piloto/
│   ├── config.yaml
│   ├── Dockerfile
│   ├── icon.png
│   ├── logo.png
│   └── aplicação e documentação
└── evolution-api/
    ├── config.yaml
    ├── Dockerfile
    ├── run.sh
    ├── README.md
    ├── DOCS.md
    └── CHANGELOG.md
```

Cada futuro add-on ganha uma **pasta na raiz**, com `config.yaml`, `Dockerfile` (para build local), documentação e versão independentes. Não crie outro `repository.yaml` em subpastas.

## Catálogo publicado na `main` — snapshot histórico de manifests conferidos em 22/11/2026

A tabela abaixo é um snapshot de 22/11/2026, não um indicador ao vivo. Para a versão atual, leia o config.yaml de cada pasta; para versão instalada, consulte o Supervisor.

| Diretório | Nome na loja | Versão | Arquitetura |
|---|---|---|---|
| `evolution-api/` | Fábrica de Ideias - Evolution API WhatsApp | 0.1.0 | aarch64 |
| `pager-virtual/` | Fábrica de Ideias - Avisaqui | 0.1.20-rc.12 | aarch64, amd64 |
| `umdoislab-central/` | Fábrica de Ideias - WhatsApp Umdoislab | 0.5.0-rc.3 | aarch64 |
| `factory-runner/` | Fábrica de Ideias - Factory Runner | 0.1.0-rc.19 | aarch64, amd64 |
| `instagram-central/` | Fábrica de Ideias - Central Instagram | 0.1.38 | aarch64 |
| `editorial-mcp/` | Fábrica de Ideias - Central Editorial MCP | 0.1.4 | aarch64, amd64 |
| `artesaos-piloto/` | Fábrica de Ideias - Artesão Digital | 0.2.0-dev.33 | aarch64 |
| `design-system-lab/` | Fábrica de Ideias - Design System Lab (temporário) | 0.1.0-test.3 | aarch64 |

O registro [`.github/addon-registry.json`](.github/addon-registry.json) reúne os **dez** add-ons. Os arquivos `icon.png` e `logo.png` preservam os mesmos blobs de identidade já utilizados no catálogo (SHA `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a` e `7e500016222b0a5bf395be8ed17447edeb3e2af9`).

**Central WhatsApp original:** a distribuição `0.5.0-rc.1` foi publicada no [commit `45d7ec6`](https://github.com/mmcromero/hassio-addons/commit/45d7ec6e28f60ec6f1ef1e3ebc86baf8b44cfbe3), preservando o `slug: umdoislab_central`. **Não equivale à atualização do app instalado no Raspberry.** A homologação depende do Supervisor.

**Duplicação corrigida no catálogo:** a candidata experimental `umdoislab-central-lab/` (`umdoislab_central_lab`) foi retirada da lista pública, conforme a decisão de manter um só aplicativo. O histórico permanece no Git; esta operação **não desinstala add-ons nem remove dados no Home Assistant**, cuja instalação atual não foi comprovada nesta revisão.

**Fora deste catálogo:** Kanban usa `mmcromero/fabrica-de-ideias-kanban`. O Artesão Digital agora integra este catálogo em `artesaos-piloto/`; a fonte de desenvolvimento continua em `mmcromero/fabricacao_e_orcamentos`.

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
- Migrações entre repositórios exigem decisão explícita do proprietário, preservação integral do pacote e atualização do registro do catálogo.

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


## Design System Lab — homologação temporária

O add-on experimental **design-system-lab/** executa a validação do repositório privado **mmcromero/design-system** diretamente no hardware Home Assistant ARM64. Ele baixa somente a branch **desenvolvimento** usando um token GitHub de leitura informado pelo administrador na configuração protegida do app; nenhum código-fonte privado ou segredo é publicado no catálogo.

O app instala Node.js 22, Playwright/Chromium e dependências de teste no container. A validação executa instalação limpa, builds, Vitest, isolamento/DOM e viewports; após sucesso, disponibiliza a Demo estática pelo Ingress para homologação manual com leitor de tela. Não expõe portas do host, não monta diretórios do Home Assistant e não acessa a API do Supervisor.

O token deve ser Fine-grained PAT restrito ao repositório **design-system**, permissão **Contents: Read-only**. Nunca inserir o token em Issue, chat, log ou Git. A instalação é manual e o app permanece em estágio experimental; sua remoção após a homologação não altera os demais add-ons.


## Cofre de Credenciais — candidata própria (27/11/2026)

A pasta `cofre-credenciais/` contém a distribuição mantida por mmcromero, baseada no wrapper Home Assistant Community App Vaultwarden (MIT) e no servidor Vaultwarden 1.37.5 (AGPL-3.0), com imagem ARM64/AMD64 fixada por digest. A candidata `0.1.0-rc.1` mantém cadastro, convites, Sends, SSO signup e painel administrativo desativados por padrão; a porta 7277 não é publicada no host. O acesso depende de hostname HTTPS dedicado pelo NGINX existente. **Não cadastrar credenciais reais antes de concluir e homologar HTTPS, MFA, backup e restauração.** Consulte `cofre-credenciais/DOCS.md`.
