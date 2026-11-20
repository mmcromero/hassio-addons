# Central WhatsApp Umdoislab — distribuição Home Assistant

Este diretório distribui o **aplicativo único e original** da Central WhatsApp pelo catálogo `mmcromero/hassio-addons`.
A fonte de desenvolvimento e testes permanece privada em `mmcromero/whatsapp-automacoes`, [PR #10](https://github.com/mmcromero/whatsapp-automacoes/pull/10), Issue #7.

## Identidade do pacote

| Campo | Valor |
|---|---|
| Nome na loja | Fábrica de Softwares - WhatsApp Umdoislab |
| Versão candidata | `0.5.0-rc.2` |
| Pasta | `umdoislab-central/` |
| Slug original preservado | `umdoislab_central` |
| Arquitetura | `aarch64` |
| Ingress | Ativo, porta interna `8099`; sem porta pública de host |
| Inicialização | Manual |
| Persistência existente | `/data/central.sqlite3` |

**Atenção:** a presença do pacote na loja não comprova instalação ou homologação. A instalação correta é **Atualizar** a Central existente, nunca criar uma nova.

## O que foi corrigido na RC2

A resposta de `message/sendText` pode identificar o destinatário por um LID e informar o PN exato em `key.remoteJidAlt`. A Central agora registra o ID somente quando esse vínculo é explícito, `fromMe` é `true` e o ID é válido. Quando não há vínculo, a saída permanece não comprovada e não autoriza recuperação automática. O Gateway n8n já publica a observação de ecos, sem alterar o webhook nem o envio comercial nesta atualização.

## O que foi incluído

A versão candidata inclui a estrutura de contas isoladas (apenas Umdoislab ativa), resolução de instância, política, histórico, saída autenticada PN/LID, outbox e reconciliação conservadora. O envio automático de recuperação permanece **desligado**; a entrada HTTP ainda não ativa enfileiramento automático. Não há nova conta, número, interface com abas ou webhook da Evolution.

O Dockerfile copia os módulos Python presentes em [`SOURCE_PROVENANCE.json`](SOURCE_PROVENANCE.json); a UI `static/index.html`, `icon.png` e `logo.png` têm os mesmos hashes da distribuição anterior. Imagens e `panel_icon` são coisas diferentes.

## Segurança e configuração

As opções `bridge_secret`, `evolution_webhook_secret`, `evolution_url`, `evolution_instance`, `evolution_api_key` e `auto_test_sender` pertencem ao Supervisor. Segredos não devem ser gravados aqui. `evolution_webhook_secret` foi acrescentado com default vazio e schema de senha.

O pacote usa `/data` do **mesmo slug original**, mantendo o banco legado. Não modificar webhook ativo do n8n/Evolution por causa desta atualização nem ativar worker até ensaio específico.

## Testes e processo

Baseline anterior: o Codex registrou **230 PASS** na RC1/M002. Para RC2, foi executado **teste dirigido isolado 16/16 PASS** do helper PN/LID. Testes de integração adicionais foram versionados na fonte privada, mas a suíte completa no novo SHA ainda não foi executada. Nenhum teste real ARM64/Ingress da RC2 foi declarado aprovado.

A rotina oficial é [`../CONTRIBUTING.md`](../CONTRIBUTING.md) (P0). O Supervisor poderá compilar o Dockerfile no Raspberry durante a **atualização autorizada**. O plano de homologação H01–H11 está no repositório privado, em `docs/WA-MULTI-001-HOMOLOGACAO-P0-PLANO.md`.

**Não apagar ou substituir este diretório**: ele é o canal oficial de atualização do aplicativo já existente. Não usar o antigo pacote experimental `umdoislab-central-lab` como atualização.
