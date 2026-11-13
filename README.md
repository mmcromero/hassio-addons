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

## Regras de manutenção

- Branch isolada, validação automática, revisão em PR e depois merge.
- Versão independente por add-on, registrada em `CHANGELOG.md`.
- Preferir tags fixas em vez de `:latest`.
- A CI **não instala nem publica** add-ons no HA; o Supervisor compila o Dockerfile depois da inclusão do repositório.
- Segredos, bancos e sessões nunca entram no Git.
- Não migrar os add-ons antigos para este repositório sem uma decisão específica.

Veja [CONTRIBUTING.md](CONTRIBUTING.md) e o guia individual da Evolution API.
