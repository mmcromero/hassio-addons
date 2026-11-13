# CONTINUIDADE — Home Assistant, Evolution API e n8n

**Atualizado em:** 2026-11-13  
**Repositório:** https://github.com/mmcromero/hassio-addons  
**Situação:** infraestrutura básica publicada; instalação real da Evolution API em andamento no último relato do proprietário. **Não afirmar que concluiu** sem nova evidência.

## Como retomar em outro chat

> Atue no modo `/pair` do projeto `mmcromero/hassio-addons`. Leia primeiro `docs/CONTINUIDADE.md`, `docs/ARQUITETURA-AUTOMACOES.md`, `evolution-api/DOCS.md` e os PRs/Actions recentes. Continue a homologação da Evolution API v0.1.0 no Home Assistant OS sem alterar o Raspberry Pi sem autorização explícita. Não confunda CI verde com instalação ou pareamento real aprovados.

Esse parágrafo pode ser copiado como mensagem inicial. Documentos no Git são a fonte da verdade para decisões deste projeto; informações sobre estado de execução precisam de evidências atuais.

## Ambiente conhecido (informação fornecida pelo proprietário)

- Home Assistant OS no Raspberry Pi 4, `aarch64`, **8 GB de RAM**.
- O Raspberry controla a automação da casa, hospeda **n8n** na porta **5678** e **Jellyfin**; existem outros serviços e dispositivos conectados. Não presumir que os serviços de inventários antigos estejam todos ativos.
- Uso doméstico leve: luzes e automações simples; Jellyfin usado ocasionalmente, normalmente em Direct Play.
- O proprietário trabalha em casa e pretende usar WhatsApp para automatizar atividades de **microempresa artesanal (Umdoislab)**. Baixo volume estimado de conversas, **sem medição real ainda**; envio de comandos poderá ser mais frequente que mensagens de clientes.
- Objetivo imediato: construir uma infraestrutura confiável, **não** definir todos os workflows de negócio antes da homologação.
- **Prioridade:** Home Assistant e funções da residência não devem ficar indisponíveis por causa da Evolution API.

**Não confirmado atualmente:** consumo de CPU/RAM, armazenamento livre, uso simultâneo do Jellyfin, número de sessões, carga real do n8n, instalação concluída, saúde de longo prazo e funcionamento de QR Code.

## Histórico validado em GitHub

1. Repositório novo criado: `mmcromero/hassio-addons`.
2. PR **#1** integrado em `main` pelo commit `a1f7978e7420e6de921394724fa6615d0cd4b2c8`.
3. `repository.yaml` na raiz e add-on `evolution-api/` próprio, para ARM64.
4. Imagem `evoapicloud/evolution-api:v2.3.7` (tag fixa); add-on `0.1.0`, experimental.
5. Contêiner inclui PostgreSQL; dados em `/data/postgres`, senha em `/data/postgres-password`, sessões em `/data/instances`.
6. Opções no Supervisor: `api_key`, `server_url` e `webhook_url`.
7. CI #**43432666479**: YAML, build ARM64, inicialização PostgreSQL, HTTP Manager e reinício persistente **aprovados em ambiente de teste**. Isso não testa conexão real com WhatsApp no Raspberry.
8. O Home Assistant do proprietário **reconheceu o repositório na loja e mostrou o add-on Evolution API WhatsApp 0.1.0, classificado como experimental**. O último relato foi que a instalação estava em andamento.

**Fonte da publicação:** https://github.com/mmcromero/hassio-addons/pull/1  
**CI da validação:** https://github.com/mmcromero/hassio-addons/actions/runs/43432666479

## Próxima tarefa operacional

Antes de propor qualquer novo desenvolvimento, confirmar apenas a etapa atual da instalação no Home Assistant e observar os logs sem segredos.

Sequência de homologação, sem pular etapas:

1. Confirmar conclusão da instalação pelo Supervisor e ausência de conflito da porta 8080.
2. Na UI do add-on, configurar `api_key` forte, `server_url` correto e manter `webhook_url` vazio no primeiro teste.
3. Iniciar; conferir os logs e a saúde do PostgreSQL + Evolution, sem compartilhar tokens nem credenciais.
4. Abrir `http://homeassistant.local:8080/manager` (ou IP/endereço configurado) e validar autenticação.
5. Criar **uma** instância, parear por QR Code e verificar recebimento/envio de texto e mídia.
6. Criar workflow Webhook no n8n e testar entrega controlada de eventos; só depois ativar webhook global.
7. Reiniciar somente o add-on; verificar banco, arquivos e reconexão de sessão.
8. Planejar backup consistente, restauração e monitoramento de consumo de recursos; não fazer mudanças destrutivas sem verificar dados e modelo exatos.
9. Registrar resultados no Git (evidências redigidas sem dados pessoais, tokens, QR, telefone ou conteúdo de conversas).

**Não presumir** que uma mensagem enviada do WhatsApp para o n8n executa automaticamente ações na casa; isso depende dos workflows, autorização e controles de segurança.

## Política de mudanças

- Seguir `/pair`: programação assistida, sem Codex, Work ou agentes externos; usar GitHub e ferramentas de leitura/escrita permitidas, sempre por escopo autorizado.
- Trabalhar em branch isolada, manter `main` estável, abrir PR e conferir testes antes de integrar alterações aprovadas.
- Não alterar Home Assistant OS, host, portas, outros add-ons ou dados persistentes sem autorização explícita.
- Não registrar credenciais, QR Code, identificadores de contatos ou backups no Git.
- Diferenciar fatos comprovados por execução, decisões de arquitetura e itens propostos.

## Decisão de arquitetura futura

Consulte [ARQUITETURA-AUTOMACOES.md](ARQUITETURA-AUTOMACOES.md). Resumo: manter **um n8n principal no Raspberry** e fazer automações leves locais. Preparar caminho para delegar mídia/IA/processamento pesado ao computador por serviço autenticado e assíncrono. **Não instalar segundo n8n agora**; avaliar quando houver demanda real. Um segundo n8n independente é opcional no futuro; workers oficiais e Redis compartilhado são complexidade desnecessária neste estágio.
