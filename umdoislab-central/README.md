# Central WhatsApp Umdoislab — distribuição Home Assistant

Este diretório distribui o **aplicativo único e original** da Central WhatsApp pelo catálogo `mmcromero/hassio-addons`.
A fonte de desenvolvimento e testes permanece privada em `mmcromero/whatsapp-automacoes`, [PR #10](https://github.com/mmcromero/whatsapp-automacoes/pull/10), Issue #7.

## Identidade do pacote

| Campo | Valor |
|---|---|
| Nome na loja | Fábrica de Softwares - WhatsApp Umdoislab |
| Versão candidata | `0.5.0-rc.3` |
| Pasta | `umdoislab-central/` |
| Slug original preservado | `umdoislab_central` |
| Arquitetura | `aarch64` |
| Ingress | Ativo, porta interna `8099`; sem porta pública de host |
| Inicialização | Manual |
| Persistência existente | `/data/central.sqlite3` |

**Atenção:** a presença do pacote na loja não comprova instalação ou homologação. A instalação correta é **Atualizar** a Central existente, nunca criar uma nova.

## O que foi corrigido na RC3

A RC2 já corrigiu o ID de `sendText` com vínculo PN/LID. A RC3 corrige **outra falha real**: uma saída com ID verificado na Evolution, mas sem vínculo com o robô, era marcada `uncertain` e transformava a conversa em atendimento `human` sem prova de intervenção. Agora essa situação entra em `pending / origin_review`: a automação fica bloqueada até revisão, sem falsificar atendimento humano. Mensagem do robô com ID confirmado continua classificada `bot` e não bloqueia a conversa. O histórico e os dados continuam preservados.

**Após atualizar a mesma instalação original:** se a conversa de teste já estava em `human` por causa da classificação antiga, abra-a no painel e use **Marcar como resolvido**. A RC3 não converte automaticamente históricos `human`, pois alguns podem representar atendimento real. A ação libera o estado após revisão, sem apagar dados. O Gateway n8n permanece na versão aprovada, sem modificar o Comercial.

## O que foi incluído

A versão candidata inclui a estrutura de contas isoladas (apenas Umdoislab ativa), resolução de instância, política, histórico, saída autenticada PN/LID, outbox e reconciliação conservadora. O envio automático de recuperação permanece **desligado**; a entrada HTTP ainda não ativa enfileiramento automático. Não há nova conta, número, interface com abas ou webhook da Evolution.

O Dockerfile copia os módulos Python presentes em [`SOURCE_PROVENANCE.json`](SOURCE_PROVENANCE.json); a UI `static/index.html`, `icon.png` e `logo.png` têm os mesmos hashes da distribuição anterior. Imagens e `panel_icon` são coisas diferentes.

## Integração compartilhada ChatGPT / Home Assistant / n8n

Os túneis MCP do ChatGPT são infraestrutura compartilhada do Raspberry Pi, não componentes instalados dentro desta Central:

- O túnel HA-MCP permite ao agente consultar o Home Assistant e executar operações de escrita no escopo de um projeto/add-on incluído em missão autorizada pelo proprietário; a capacidade efetiva deve ser verificada na sessão.
- O túnel n8n MCP permite ao conector ChatGPT acessar as ferramentas explicitamente habilitadas no MCP HTTP do n8n.
- Ambos são duas entradas da mesma integração OpenAI Tunnel for HA-MCP, executadas no Home Assistant. O túnel n8n já foi migrado do CMD Windows para o Raspberry, preservando o Tunnel ID original.

**Não confundir esses túneis com o webhook Evolution → n8n, o transporte da Central ou o Gateway de atendimento.** A falha de um túnel MCP não prova falha no atendimento WhatsApp. Não modificar webhook ativo, Evolution, Gateway, worker, credenciais comerciais ou banco da Central para recuperar o túnel.

Antes de qualquer intervenção, consultar o [manual operacional central dos túneis](../docs/HA-MCP-ACESSO-SOMENTE-LEITURA.md) e o [inventário do Raspberry](../docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md). Não reinstalar a integração, não criar novos Tunnel IDs e não registrar segredos no Git. O acesso HA-MCP tem leitura e escrita habilitadas pelo proprietário desde 25/11/2026, limitadas ao escopo autorizado da missão. Isso não concede permissão para alterar a Central, Evolution, Gateway, workers ou workflows n8n por consequência. As permissões do MCP n8n devem ser verificadas separadamente.

## Segurança e configuração

As opções `bridge_secret`, `evolution_webhook_secret`, `evolution_url`, `evolution_instance`, `evolution_api_key` e `auto_test_sender` pertencem ao Supervisor. Segredos não devem ser gravados aqui. `evolution_webhook_secret` foi acrescentado com default vazio e schema de senha.

O pacote usa `/data` do **mesmo slug original**, mantendo o banco legado. Não modificar webhook ativo do n8n/Evolution por causa desta atualização nem ativar worker até ensaio específico.

## Testes e processo

Evidência histórica: **230 PASS** na RC1/M002 e **16 PASS isolados** no helper PN/LID da RC2 (outros SHAs). Na RC3, **7 PASS isolados** de SQL/estados e **7 regressões versionadas** para a fonte; a suíte completa da branch ainda não foi executada. A compilação, boot e homologação real no ARM64 após a atualização RC3 dependem do operador do Home Assistant. Não atribuir os PASS históricos ao código RC3.

A rotina oficial é [`../CONTRIBUTING.md`](../CONTRIBUTING.md) (P0). O Supervisor poderá compilar o Dockerfile no Raspberry durante a **atualização autorizada**. O plano de homologação H01–H11 está no repositório privado, em `docs/WA-MULTI-001-HOMOLOGACAO-P0-PLANO.md`.

**Não apagar ou substituir este diretório**: ele é o canal oficial de atualização do aplicativo já existente. Não usar o antigo pacote experimental `umdoislab-central-lab` como atualização.
