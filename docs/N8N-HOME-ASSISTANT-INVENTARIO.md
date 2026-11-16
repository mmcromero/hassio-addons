# n8n no Home Assistant — inventário e passagem de bastão

**Consolidado em:** 16/11/2026 (BRT)  
**Repositório:** `mmcromero/hassio-addons`  
**Objetivo:** permitir que outro desenvolvedor ou chatbot comece **outras automações no mesmo n8n**, sem reconstruir toda a história da Umdoislab nem confundir os dois add-ons que desenvolvemos com a instalação do n8n.

> **ATENÇÃO À FONTE:** conferido nos documentos/código do GitHub; alguns estados vieram de capturas e relatos anteriores do proprietário. **Não houve acesso ao Supervisor, arquivos de configuração reais ou banco do n8n nesta auditoria.** Onde a fonte não comprova um dado, este documento registra `NÃO VERIFICADO`, não um palpite.

## 1. Resposta rápida para uma nova equipe

- O **n8n principal** foi instalado no **Home Assistant OS em Raspberry Pi 4 (8 GB, ARM64)**, conforme histórico confirmado pelo proprietário. O acesso de rede documentado foi `http://homeassistant.local:5678`. Esse é endereço **local de referência**, não link público garantido nem hostname verificado em 16/11.
- **Versão do aplicativo n8n:** `2.47.3` foi a última versão citada nos documentos de 13/11/2026. **Não foi reconfirmada** no ambiente atual.
- O n8n é **um serviço separado** dos add-ons desenvolvidos no repositório: (1) `evolution-api` e (2) `umdoislab-central`. **Este repositório não contém uma receita verificada para recriar a instalação do n8n.**
- O n8n recebeu webhooks de WhatsApp, executou regras de filtragem e depois passou a integrar Gemini + Central de Atendimento. Esse caso de uso é apenas **um conjunto de workflows**; o n8n pode hospedar outras automações independentes.
- **Não reutilizar o webhook do atendimento** para automações novas; criar workflow e caminho próprios quando necessário. Não apagar, despublicar ou importar sobre o fluxo existente como teste.

## 2. Componentes distintos

| Componente | Onde fica | Evidência | Papel |
| --- | --- | --- | --- |
| **Home Assistant OS** | Raspberry Pi 4, 8 GB, ARM64 | Documentação histórica do proprietário | Hospeda Supervisor/add-ons e automação residencial |
| **n8n** | HA, porta 5678 documentada | Documentação de 13/11 + capturas n8n v1.6 | Orquestra workflows; **add-on de origem/slug não identificado nesta auditoria** |
| **Evolution API** | Add-on próprio `evolution-api/`, `0.1.0` na main | [config.yaml](../evolution-api/config.yaml) | Ponte WhatsApp; imagem `evoapicloud/evolution-api:v2.3.7` fixada no código |
| **Central de Atendimento** | Add-on próprio `umdoislab-central/`, `0.4.0` na main | [config.yaml](../umdoislab-central/config.yaml) | Atendimento humano, estados, política, histórico, API interna |
| **Gemini** | Nó do workflow n8n | JSON v1.6/v1.7 versionados | Gera texto de atendimento; credencial protegida no próprio n8n |
| **Workflow v1.7** | [JSON importável](../umdoislab-central/n8n/atendimento-v1.7-handoff-verificado.json) | Arquivo na main; integração PR #11 | Proposta de handoff verificado; **arquivo versionado não comprova publicação no n8n** |
| **Painel de conversas 0.4.1** | [PR #12](https://github.com/mmcromero/hassio-addons/pull/12) | PR consultado em 16/11: **aberto** | Melhoria da Central, **não instalada por estar no PR**, salvo evidência posterior |

**Importante:** versões do aplicativo n8n, do workflow, do add-on Central e da aplicação Evolution API **não são intercambiáveis**. Um PR integrado não instala nada no Raspberry.

## 3. História recuperável e decisões comprovadas

- Instalação e primeiro uso do n8n com Evolution foram registrados em [PASSAGEM-DE-BASTAO-UMDOISLAB-2026-11-13.md](PASSAGEM-DE-BASTAO-UMDOISLAB-2026-11-13.md), agora documento histórico.
- A instância Evolution `umdoislab` usou Baileys e configuração de webhook por instância no Manager; a configuração **global** do add-on não equivale à URL por instância.
- O primeiro webhook validado na fase v1.1 foi `POST /webhook/umdoislab-atendimento-inicial`; **histórico, não usar para novas integrações**.
- O JSON versionado `umdoislab-central/n8n/atendimento-v1.5-whatsapp-real.json` tem nome **interno v1.6**; seu webhook é `/webhook/umdoislab-v15`. A v1.7 usa o **mesmo path**; não publicar as duas simultaneamente.
- O workflow publicado mostrado nas capturas anteriores foi **v1.6**. O proprietário posteriormente recebeu o arquivo v1.7 para instalação, mas **não há comprovação documental aqui de qual workflow está Published em 16/11**.
- A integração de mensagens foi operada com credencial de autenticação HTTP Header para a Central e credencial Gemini no n8n. O nome de exibição da credencial citado no README é `Central Umdoislab`; o nome da credencial Gemini foi descrito como `Gemini — Umdoislab`. **Isso não comprova que existam com esses nomes hoje**. Jamais versionar valores de secrets.
- O projeto deliberou manter **um n8n principal** no Raspberry e evitar instalar outro n8n ou workers/Redis sem necessidade [ARQUITETURA-AUTOMACOES.md](ARQUITETURA-AUTOMACOES.md).

## 4. Dados indispensáveis da **instalação geral do n8n** que ainda faltam

O repositório documenta **uso e integração** do n8n, mas não fornece um inventário de instalação/recuperação completo. **NÃO VERIFICADOS em 16/11/2026:**

1. **Origem do add-on n8n:** repositório de add-ons instalado, nome exato, slug, versão atual e imagem real; se foi instalação por loja ou mecanismo diferente.
2. **Configurações do add-on:** hostname interno/Ingress versus porta mapeada, opções não secretas, ambiente, `WEBHOOK_URL`, `N8N_HOST`, `N8N_PROTOCOL`, timezone e eventual reverse proxy/TLS.
3. **Persistência:** diretório/volume do usuário n8n, localização e tipo real do banco, política de atualização, caminho da configuração e arquivos que precisariam de backup.
4. **Credenciais/criptografia:** existência e forma segura de retenção da chave de criptografia do n8n; nunca registrar o valor, cópia da chave ou tokens no GitHub.
5. **Backup e recuperação:** método, frequência, conteúdo e última restauração testada; nenhuma recuperação do n8n foi homologada nos arquivos lidos.
6. **Workflows e conexões atuais:** inventário real de workflows publicados, proprietários, triggers, nomes/IDs, credenciais usadas (apenas **nomes**, não valores), dependências e conflitos de webhook.
7. **Conectividade:** resolução de `homeassistant.local` nos contêineres, chamadas HTTP para outros add-ons, autenticação e exposição externa da UI/webhooks.
8. **Operação:** reinício/saúde, logs sanitizados, limites de recursos no Pi, política de retenção de execuções e versão instalada atual.

**Portanto, não é seguro afirmar “tudo documentado” nem que a instalação do n8n possa ser restaurada a partir deste Git.** O que existe é um histórico significativo da implementação do atendimento, **não um backup completo do serviço n8n**.

## 5. Como completar a documentação sem expor dados sensíveis

Quando houver acesso autorizado à UI do Home Assistant/n8n, registrar **metadados não secretos**: nome e origem do add-on, slug, versão, portas, URL local, opções com segredos **redigidos**, storage persistente comprovado, status de backup, relação de workflows e seus triggers. Usar evidências sanitizadas, datadas e identificadas como `comprovado na UI`, `confirmado pelo código` ou `não verificado`.

**Nunca pedir senha, token, API key, cookie de sessão, QR do WhatsApp nem `N8N_ENCRYPTION_KEY` em chat ou Git público.** Se a chave de criptografia for necessária para backup/restore, documentar **onde e como** é protegida, nunca seu valor.

Não reinstalar o n8n, migrar dados, atualizar imagem, apagar volumes ou mexer no Home Assistant para realizar inventário. Não presumir tipo de banco ou diretório só porque é comum em n8n.

## 6. Novas automações: procedimento seguro

1. Leia este documento e [ARQUITETURA-AUTOMACOES.md](ARQUITETURA-AUTOMACOES.md) antes de usar o n8n existente.
2. Confirme na interface o nome/versão real do n8n e quais workflows já estão publicados; não reutilize gatilhos nem paths da Umdoislab.
3. Crie workflow isolado, com nome/objetivo/trigger próprios; comece com testes sem efeitos sobre clientes e automação residencial.
4. Reutilize conexões existentes **apenas** com autorização e escopo compatível; não reutilize token do WhatsApp/Central por conveniência.
5. Após cada publicação/alteração importante, atualize inventário de workflows e passagem de bastão, distinguindo arquivo versionado, `Published` e execução testada.

## 7. Prompt pronto para outro chatbot

> Quero criar **novas automações** no meu n8n instalado no Home Assistant do Raspberry Pi 4, independentes da Umdoislab. Consulte `mmcromero/hassio-addons/docs/N8N-HOME-ASSISTANT-INVENTARIO.md` e `docs/ARQUITETURA-AUTOMACOES.md`. Este Git contém os add-ons `evolution-api` e `umdoislab-central`, além dos workflows e histórico da integração WhatsApp, mas **a instalação geral do n8n não está inventariada integralmente**. A versão 2.47.3 e o endereço `http://homeassistant.local:5678` são referências históricas, não verificadas hoje. Não confunda os add-ons da Umdoislab com o add-on do n8n. Preserve os workflows já publicados e não altere Home Assistant, credenciais ou dados sem autorização. Primeiro obtenha apenas os metadados faltantes, sem segredos, e registre-os na documentação. Trabalhe com workflows novos e gatilhos independentes.

## 8. Referências

- [Estado da Umdoislab, separado do n8n geral](ESTADO-ATUAL-UMDOISLAB.md)
- [Histórico da primeira instalação e dos webhooks](PASSAGEM-DE-BASTAO-UMDOISLAB-2026-11-13.md)
- [Decisões da infraestrutura de automações](ARQUITETURA-AUTOMACOES.md)
- [Evolução/instalação do add-on Evolution](../evolution-api/DOCS.md)
- [Configuração da Central e workflows](../umdoislab-central/README.md)
- [Protocolo de atualização da passagem de bastão](PROTOCOLO-DE-CONTINUIDADE-UMDOISLAB.md)
