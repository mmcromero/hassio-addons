# Add-ons Home Assistant — mmcromero

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

## Catálogo

| Add-on | Versão | Arquitetura | Estado |
|---|---|---|---|
| Evolution API — WhatsApp + n8n | 0.1.0 | aarch64 | Candidato, ainda não homologado no Raspberry Pi |
| Pager Virtual | 0.1.0 | aarch64, amd64 | Candidato a testes no Raspberry Pi 4 |

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
- A CI **não instala nem publica** add-ons no HA; o Supervisor compila o Dockerfile depois da inclusão do repositório.
- Segredos, bancos e sessões nunca entram no Git.
- Não migrar os add-ons antigos para este repositório sem uma decisão específica.

Veja [CONTRIBUTING.md](CONTRIBUTING.md) e o guia individual da Evolution API.
