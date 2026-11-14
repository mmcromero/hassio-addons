# CONTINUIDADE — Home Assistant, Evolution API e n8n

> **ATUALIZAÇÃO PRIORITÁRIA — 14/11/2026.** Comece por [ESTADO-ATUAL-UMDOISLAB.md](ESTADO-ATUAL-UMDOISLAB.md) e [PROTOCOLO-DE-CONTINUIDADE-UMDOISLAB.md](PROTOCOLO-DE-CONTINUIDADE-UMDOISLAB.md). Os registros abaixo sobre workflow v1.1 são históricos. A operação observada tem **n8n v1.6 publicado**, **Central 0.3.0 instalada**, Evolution add-on **0.1.0**. O validador automático de contatos foi discutido e está **adiado**. Não retornar à v1.1, recriar fluxos antigos, alterar o HA ou reabrir decisões antigas por interpretação deste texto.


**Atualizado em:** 2026-11-13  
**Repositório:** https://github.com/mmcromero/hassio-addons  
**Situação (13/11/2026):** Evolution API instalada, instância `umdoislab` pareada e classificação v1.1 homologada em produção pelo proprietário; ver [passagem de bastão](PASSAGEM-DE-BASTAO-UMDOISLAB-2026-11-13.md).

> **LEITURA PRIORITÁRIA — ESTADO MAIS RECENTE:** [PASSAGEM-DE-BASTAO-UMDOISLAB-2026-11-13.md](PASSAGEM-DE-BASTAO-UMDOISLAB-2026-11-13.md). Este arquivo registra também o histórico inicial; as etapas de instalação/QR descritas abaixo **já foram concluídas** pelo proprietário. Não tratá-las como próximas ações. O webhook em produção é `/webhook/umdoislab-atendimento-inicial` e a classificação v1.1 teve execução **Success** com quatro nós. O próximo incremento é resposta sugerida sem envio automático.

## Como retomar em outro chat

> Atue no modo `/pair` do projeto `mmcromero/hassio-addons`. Leia primeiro `docs/PASSAGEM-DE-BASTAO-UMDOISLAB-2026-11-13.md`, depois `docs/CONTINUIDADE.md`, `docs/ARQUITETURA-AUTOMACOES.md` e `evolution-api/DOCS.md`. O proprietário já confirmou o pareamento e o recebimento de eventos em produção no n8n v1.1. Próxima tarefa: preservar o JSON efetivo da v1.1 e preparar respostas sugeridas sem envio automático. Não alterar Raspberry Pi nem workflows sem autorização.

Esse parágrafo pode ser copiado como mensagem inicial. Documentos no Git são a fonte da verdade para decisões deste projeto; informações sobre estado de execução precisam de evidências atuais.

## Ambiente conhecido (informação fornecida pelo proprietário)

- Home Assistant OS no Raspberry Pi 4, `aarch64`, **8 GB de RAM**.
- O Raspberry controla a automação da casa, hospeda **n8n** na porta **5678** e **Jellyfin**; existem outros serviços e dispositivos conectados. Não presumir que os serviços de inventários antigos estejam todos ativos.
- Uso doméstico leve: luzes e automações simples; Jellyfin usado ocasionalmente, normalmente em Direct Play.
- O proprietário trabalha em casa e pretende usar WhatsApp para automatizar atividades de **microempresa artesanal (Umdoislab)**. Baixo volume estimado de conversas, **sem medição real ainda**; envio de comandos poderá ser mais frequente que mensagens de clientes.
- Objetivo imediato: construir uma infraestrutura confiável, **não** definir todos os workflows de negócio antes da homologação.
- **Prioridade:** Home Assistant e funções da residência não devem ficar indisponíveis por causa da Evolution API.

**Não confirmado atualmente:** consumo de CPU/RAM, armazenamento livre, carga real do n8n, saúde de longo prazo, backups, persistência e reconexão após reinício. Instalação e QR **foram confirmados depois**; consultar a passagem de bastão.

## Histórico validado em GitHub

1. Repositório novo criado: `mmcromero/hassio-addons`.
2. PR **#1** integrado em `main` pelo commit `a1f7978e7420e6de921394724fa6615d0cd4b2c8`.
3. `repository.yaml` na raiz e add-on `evolution-api/` próprio, para ARM64.
4. Imagem `evoapicloud/evolution-api:v2.3.7` (tag fixa); add-on `0.1.0`, experimental.
5. Contêiner inclui PostgreSQL; dados em `/data/postgres`, senha em `/data/postgres-password`, sessões em `/data/instances`.
6. Opções no Supervisor: `api_key`, `server_url` e `webhook_url`.
7. CI #**43432666479**: YAML, build ARM64, inicialização PostgreSQL, HTTP Manager e reinício persistente **aprovados em ambiente de teste**. Isso não testa conexão real com WhatsApp no Raspberry.
8. O Home Assistant reconheceu o repositório e instalou o add-on. Depois, o proprietário homologou a instância `umdoislab`, evento `messages.upsert` e n8n v1.1 com Success; consultar a passagem de bastão.

**Fonte da publicação:** https://github.com/mmcromero/hassio-addons/pull/1  
**CI da validação:** https://github.com/mmcromero/hassio-addons/actions/runs/43432666479

## Próxima tarefa operacional — atualizada em 13/11/2026

A instalação/pareamento e o recebimento de eventos em produção **já foram homologados pelo proprietário**. A versão v1.1 executou os quatro nós e classificou uma pergunta de preço. Ainda **não envia respostas**.

1. Exportar o **JSON real da v1.1 em produção** antes de modificá-la.
2. Preparar v1.2 de respostas sugeridas para revisão, **sem envio automático**.
3. Desenvolver Gemini em workflow separado com dados fictícios, sem ligar ao atendimento real.
4. Manter automação pessoal separada (o JSON entregue é somente simulador).
5. Mais tarde verificar backups, reinício, reconexão, logs sem segredos, carga e prevenção de duplicidade.

Endpoint atual: `POST http://homeassistant.local:5678/webhook/umdoislab-atendimento-inicial`. Para detalhes, evidências e problemas já resolvidos: [passagem de bastão](PASSAGEM-DE-BASTAO-UMDOISLAB-2026-11-13.md).

## Política de mudanças

- Seguir `/pair`: programação assistida, sem Codex, Work ou agentes externos; usar GitHub e ferramentas de leitura/escrita permitidas, sempre por escopo autorizado.
- Trabalhar em branch isolada, manter `main` estável, abrir PR e conferir testes antes de integrar alterações aprovadas.
- Não alterar Home Assistant OS, host, portas, outros add-ons ou dados persistentes sem autorização explícita.
- Não registrar credenciais, QR Code, identificadores de contatos ou backups no Git.
- Diferenciar fatos comprovados por execução, decisões de arquitetura e itens propostos.

## Decisão de arquitetura futura

Consulte [ARQUITETURA-AUTOMACOES.md](ARQUITETURA-AUTOMACOES.md). Resumo: manter **um n8n principal no Raspberry** e fazer automações leves locais. Preparar caminho para delegar mídia/IA/processamento pesado ao computador por serviço autenticado e assíncrono. **Não instalar segundo n8n agora**; avaliar quando houver demanda real. Um segundo n8n independente é opcional no futuro; workers oficiais e Redis compartilhado são complexidade desnecessária neste estágio.


## Interface visual — melhoria futura (13/11/2026)

**Solicitação do proprietário (não implementar agora):** estudar uma identidade visual consistente e agradável para o catálogo de add-ons e, quando viável, para as interfaces dos próprios add-ons, considerando como referência a marca **Fábrica de Ideias**. **Não foi selecionada arte, logo ou paleta definitiva.**

**Evidência histórica (anterior ao pareamento):** após iniciar Evolution API v2.3.7 no Raspberry Pi e autenticar no Manager com a Global API Key, a tela de instâncias abriu normalmente (ainda sem instâncias), mas no canto superior esquerdo a imagem aparece quebrada, exibindo o texto alternativo `Logo`. A causa da falha da imagem ainda **não foi identificada**. Pode estar nos ativos da UI upstream ou em URL/servidor; não presumir causa.

**Encaminhamento:** tratar como backlog de UX, sem bloquear o pareamento do WhatsApp. Antes de modificar a imagem, investigar o caminho HTTP do recurso, se o asset é interno ou remoto, os direitos de uso da marca e a necessidade de customização da imagem base. Priorizar personalização do catálogo do Home Assistant sem criar um fork de manutenção desnecessário. O usuário decidiu **concluir primeiro a configuração do WhatsApp**.

**Estado operacional mais recente:** o proprietário confirmou instância pareada, evento recebido pelo n8n em produção e classificação v1.1 com Success. Consulte a [passagem de bastão](PASSAGEM-DE-BASTAO-UMDOISLAB-2026-11-13.md).
