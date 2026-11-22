# HOME ASSISTANT / RASPBERRY PI — INVENTÁRIO OPERACIONAL CENTRAL

**Revisão:** 22/11/2026 (consulta direta ao Supervisor via HA-MCP; capturas e verificações históricas de 19–20/11 preservadas)  
**Responsável editorial:** Governança  
**Natureza:** referência compartilhada entre todos os projetos que usam o mesmo Home Assistant. Fonte de código, configurações e credenciais continuam isoladas em seus projetos e no dispositivo. **Não é um backup nem substitui a consulta ao Supervisor.**

## Leitura obrigatória para qualquer equipe

Antes de perguntar ao proprietário sobre apps, infraestrutura, repositórios, publicação, ARM64, n8n ou disponibilidade do laboratório, consultar este inventário, [AGENTS.md](../AGENTS.md), [CONTRIBUTING.md](../CONTRIBUTING.md), [inventário de distribuições](INVENTARIO-DISTRIBUICOES-HA-2026-11-19.md) e manual do subsistema. **Não repetir perguntas respondidas aqui**, mas verificar dados voláteis no Supervisor quando necessário. Se uma decisão depender da versão exata, configuração real, arquivos persistentes ou operação irreversível, não inferir dados ausentes.

## Acesso direto homologado em 22/11/2026

O [manual HA-MCP — acesso somente leitura](HA-MCP-ACESSO-SOMENTE-LEITURA.md) registra instalação, configuração, testes e limites. O plugin pessoal **Home Assistant — Somente leitura** permite consulta direta ao Supervisor e ao Core sem depender do n8n. Resultado observado: 31 apps instalados, 28 em execução, 3 parados e 2 atualizações disponíveis; Core 2026.10.4; HA-MCP 9.2.0, modo somente leitura confirmado. Logs do Supervisor, Instagram e WhatsApp foram consultados com sucesso. Em 22/11, o túnel n8n existente também foi migrado para uma segunda entrada da integração no Raspberry Pi: 5 requisições MCP aceitas/concluídas (HTTP 200), sem erros, retries ou falhas, após interromper o CMD do Windows. A primeira entrada HA-MCP permaneceu saudável. Recuperação de ambos os túneis após reinício do Core/host ainda pendente. Usar consulta atual, quando disponível no chat e autorizada pela função, antes de solicitar dados ao proprietário. Não publicar credenciais nem permitir alterações por essa conexão. O inventário abaixo conserva evidências históricas; não confundir com estado atual.

## 1. Ambiente compartilhado

- **Hardware informado pelo proprietário e documentado anteriormente:** Raspberry Pi 4, 8 GB, arquitetura ARM64/aarch64, Home Assistant OS; não foi exibida nesta captura a versão exata do sistema, kernel, Supervisor, espaço em disco ou endereço de rede.
- É um ambiente **compartilhado** entre automações residenciais, serviços de mídia, n8n, integração WhatsApp, Artesão Digital em contingência, Avisaqui em homologação, Kanban e Factory Runner. Não aplicar automaticamente ao Raspberry o status de produção ou dados descartáveis de um projeto específico.
- Evitar intervenções que afetem serviços alheios. **Não reiniciar, remover, reinstalar, parar ou apagar dados** com base somente neste inventário. Ações sobre HA exigem permissão real e verificação do destino.
- **Catálogo central de distribuições:** https://github.com/mmcromero/hassio-addons ; não confundir distribuição com fonte privada. [Procedimento universal](../CONTRIBUTING.md).

## 2. Aplicativos instalados — evidência de captura da interface

**Fonte:** captura do proprietário em 19/11/2026 da grade de aplicativos instalados no Home Assistant. A captura mostra 29 cartões; os estados abaixo descrevem apenas o instante fotografado. **Não mostra versão de cada instalação, origem do app, ID da instalação, configurações, logs ou saúde de longo prazo.**

| Aplicativo exibido | Estado observado |
|---|---|
| Apache2 | Em execução |
| Artesão Digital — Contingência | Em execução |
| Bazarr | Em execução |
| Duck DNS | Em execução |
| ESPHome Device Builder | Parado — atualização disponível |
| Evolution API — WhatsApp | Em execução |
| Fabrica de Ideias — Kanban | Em execução |
| Fábrica de Software — Factory Runner | Em execução |
| Home Assistant Google Drive Backup | Em execução |
| Jellyfin | Em execução |
| Lidarr | Em execução |
| Lovelace Kindle Screensaver | Parado |
| MariaDB | Em execução |
| Mosquitto broker | Em execução |
| Music Assistant | Em execução |
| n8n | Em execução |
| Nextcloud | Parado |
| NGINX Home Assistant SSL proxy | Em execução — atualização disponível |
| Node-RED | Em execução |
| Pager Virtual | Em execução |
| Prowlarr | Em execução |
| qBittorrent | Em execução |
| Radarr | Em execução |
| Samba NAS2 | Em execução |
| Sonarr | Em execução |
| Studio Code Server | Em execução |
| Tailscale | Em execução |
| Terminal & SSH | Em execução |
| Umdoislab — Central de Atendimento | Em execução |

**Contagem observada:** 29 instalados; 26 em execução e 3 parados. São estados de interface, não testes funcionais ou disponibilidade comprovada por endpoints. **Nunca excluir app parado por esse motivo isolado.**

## 3. Repositórios cadastrados — evidência de outra captura do proprietário

Captura da tela de repositórios da loja em 19/11/2026: **11 entradas**. As três do proprietário são:

1. **Oficial central:** `https://github.com/mmcromero/hassio-addons` — manter.
2. **Artesão Digital:** `https://github.com/mmcromero/fabricacao-e-orcamentos-ha` — manter até migração segura da distribuição e conferência da instalação.
3. **Fábrica de Ideias Kanban:** `https://github.com/mmcromero/fabrica-de-ideias-kanban` — manter enquanto não houver migração aprovada e comprovada.

Oito outras entradas (terceiros): AlexxIT, Expaso, FaserF, alexbelgium, dianlight, Home Assistant Google Drive Backup, Legacy ESPHome versions, Lovelace Kindle Screensaver. **A captura não vincula cada app instalado a seu repositório; não concluir que alguma dessas lojas pode ser removida.** `Local Apps` não aparece na lista de repositórios, e pode ser categoria/local da instalação; origem e uso não verificados.

## 4. Separação de fonte e distribuição

O catálogo central contém quatro diretórios de app: `pager-virtual/`, `evolution-api/`, `umdoislab-central/`, `factory-runner/`. Os manifests do Git e as versões de distribuição estão no [inventário de distribuições](INVENTARIO-DISTRIBUICOES-HA-2026-11-19.md); **não assumir que versões instaladas são iguais às do GitHub.**

- Avisaqui/Pager Virtual: fonte `mmcromero/pager-virtual`; instalação atual aparece em execução; homologação específica permanece independente da publicação Git.
- Artesão Digital: fonte principal `mmcromero/fabricacao_e_orcamentos`; distribuição separada `mmcromero/fabricacao-e-orcamentos-ha`; contingência no Raspberry. **Preservar identidade da instalação e dados.**
- Kanban: repositório `mmcromero/fabrica-de-ideias-kanban` ainda mantém fonte/distribuição; versão do manifesto no Git não comprova a versão instalada.
- Evolution API, Central de Atendimento e Factory Runner: instalados e observados em execução; finalidade e procedimentos detalhados devem ser buscados nos manuais específicos, não presumidos pelo cartão da loja.

## 5. Operação e testes

- Para publicar qualquer pacote pelo `hassio-addons`, seguir [procedimento universal P0](../CONTRIBUTING.md): fechar lote e identificar fonte/HEAD, executar testes proporcionais, verificar versão/manifesto, segredos, arquitetura e proveniência, publicar somente a pasta autorizada, confirmar commit remoto e **separar publicação de instalação e homologação**.
- Ausência de QEMU, máquina ARM64 externa ou GitHub Actions **não é bloqueio automático**. Quando o app usa Dockerfile sem imagem pronta, o Supervisor pode construir no hardware alvo durante a instalação/atualização. O funcionamento real precisa ser verificado após instalação no HA; risco concreto pode exigir testes extras antes.
- Home Assistant Google Drive Backup aparece **em execução**, mas a captura não verifica a rotina, destino, criptografia, restauração ou quais apps estão incluídos. Não presumir que backups cubram todos os dados.
- n8n aparece em execução na captura histórica. O inventário detalhado, integrações WhatsApp e workflows pertencem ao repositório **privado** `mmcromero/whatsapp-automacoes`; sua presença na grade não valida workflows/credenciais.
- **Tailscale, NGINX SSL proxy, Duck DNS, Samba e Terminal & SSH** aparecem em execução, mas a captura não autoriza inferir URL, credencial, conectividade externa ou permissões da equipe.

## 6. Dados ainda não comprovados

- Na captura histórica, versão HA OS, Supervisor, firmware e kernel; uso atual de CPU/RAM/disco, rede e portas efetivas. Em 22/11 o proprietário informou HA OS 18.4 e Supervisor 2026.11.0; o Core 2026.10.4 foi confirmado via HA-MCP.
- Na captura histórica, versão instalada, slug/ID completo e origem de cada app; desde 22/11 esses metadados e logs podem ser consultados diretamente. Persistência, recuperação após reinício e saúde funcional requerem evidência própria.
- Quais lojas de terceiros ainda fornecem apps instalados; se `Local Apps` ainda possui instalações locais.
- Política e sucesso de backups/restore; dependências cruzadas entre serviços; disponibilidade de cada aplicação.

**A próxima verificação deve ser orientada por necessidade real de uma tarefa, sem pedir novamente os dados já registrados.** Para remoção de repositório ou migração, confirmar origem e identidade dos apps afetados e preservar dados; não executar remoção por inferência.

## 7. NGINX Home Assistant SSL proxy — verificação operacional em 20/11/2026

**Origem:** configuração e saídas de comandos fornecidas pelo proprietário no Terminal & SSH do Home Assistant em 20/11/2026. Os dados abaixo comprovam o estado observado naquele momento; não substituem nova leitura do Supervisor quando a tarefa depender de estado atual.

### 7.1 Add-on e opções

| Campo | Valor observado |
|---|---|
| Nome | NGINX Home Assistant SSL proxy |
| Repositório | core |
| Slug | `core_nginx_proxy` |
| Estado | `started` |
| Versão instalada | `4.5.1` |
| Versão mais recente indicada | `4.5.3` |
| Atualização disponível | Sim |
| Domínio | `romeropi.duckdns.org` |
| HSTS | `max-age=31536000; includeSubDomains` |
| Certificado | `fullchain.pem` |
| Chave | `privkey.pem` |
| Cloudflare | `false` |
| SSL no backend | `false` |
| `customize.active` | `true` |
| `customize.default` | `nginx_proxy_default*.conf` |
| `customize.servers` | `nginx_proxy/*.conf` |
| `real_ip_from` | lista vazia |

**Conduta registrada:** não atualizar o add-on como parte de uma tarefa de integração sem necessidade técnica e autorização específicas. A disponibilidade de 4.5.3 não comprova que a atualização foi instalada.

### 7.2 Fragmentos personalizados existentes

O proprietário leu os seguintes arquivos em `/share`:

- `/share/nginx_proxy_default_artesaos.conf`: define redirecionamento e proxy para `/artesaos-piloto/`, upstream `f6379561-artesaos-piloto:8099`.
- `/share/nginx_proxy_default_avisaqui.conf`: define redirecionamento e proxy para `/avisaqui/`, upstream `45c28620-pager-virtual:8095`, com prefixo encaminhado.

A listagem de `/share/nginx_proxy/` retornou **“No such file or directory”**. Portanto, o diretório configurado em `customize.servers` não existia no momento da verificação. Não criar esse diretório nem mover arquivos sem necessidade; os dois fragmentos acima são carregados pelo padrão `customize.default`.

**Preservação obrigatória:** não sobrescrever, renomear ou editar os fragmentos do Artesão Digital e do Avisaqui ao trabalhar na Central Instagram.

### 7.3 Central Instagram — conectividade interna

No Terminal & SSH, em 20/11/2026:

- `getent hosts 45c28620-umdoislab-instagram` resolveu o nome para `fd0c:ac1e:2100::1d`.
- `curl --connect-timeout 5 ... http://45c28620-umdoislab-instagram:8099/` retornou **HTTP 200**.

Isso confirma resolução DNS interna e resposta HTTP do upstream a partir do Terminal & SSH naquele instante. Não comprova acesso externo HTTPS, funcionamento das rotas OAuth/webhook ou comunicação da Meta.

### 7.4 Fragmento Instagram preparado — ainda não carregado/homologado

O proprietário criou:

`/share/nginx_proxy_default_instagram.conf`

- Tamanho observado: 1.575 bytes.
- SHA-256 observado: `cc32ffc8d76292781cf7cc3f4bebe4f64e947438624dbc933968a9e40ae3ae8c`.
- Contém três locations exatas: `/oauth/meta/start` (GET), `/oauth/meta/callback` (GET) e `/webhook/instagram` (GET/POST), todas encaminhadas para `45c28620-umdoislab-instagram:8099`.
- O nome corresponde ao padrão `nginx_proxy_default*.conf` configurado em `customize.default`.

**Estado atualizado em 20/11/2026:** arquivo criado, cópia de segurança criada e NGINX reiniciado com sucesso. O add-on permaneceu `started` na versão 4.5.1. Os testes HTTPS públicos retornaram HTTP 401 em `/oauth/meta/start`, HTTP 503 em `/oauth/meta/callback` e HTTP 503 em `/webhook/instagram` com token de verificação inválido. Esses códigos correspondem às respostas previstas no servidor quando o painel exige autenticação e OAuth/webhook permanecem desativados. Isso confirma que as três rotas públicas chegam à aplicação. OAuth e webhook continuam desativados; não houve autorização Meta nem recebimento real.

**Próxima etapa documentada:** identificar o mecanismo suportado para executar validação de sintaxe dentro do ambiente do add-on `core_nginx_proxy`, sem alterar/reiniciar serviços. O Terminal & SSH não possui o comando `docker` (`docker: command not found`). A CLI informou que `ha addons` está depreciado e recomenda `ha apps`. Não contornar essa limitação com comandos presumidos; consultar `ha apps --help` ou documentação específica do add-on e usar somente método confirmado.

### 7.5 Padrão reutilizável — comparação entre os três projetos

**Decisão operacional:** para adicionar um serviço ao proxy compartilhado, usar como modelo os fragmentos que já funcionam no mesmo Raspberry. Não iniciar uma investigação genérica de NGINX quando os arquivos locais existentes já mostram o padrão adotado.

Padrões observados nos arquivos lidos pelo proprietário:

| Projeto | Arquivo | Padrão de encaminhamento |
|---|---|---|
| Artesão Digital | `nginx_proxy_default_artesaos.conf` | `location =` para normalizar a URL e `location ^~` para encaminhar o prefixo; upstream `f6379561-artesaos-piloto:8099`; `proxy_pass` sem barra final |
| Avisaqui | `nginx_proxy_default_avisaqui.conf` | `location =` para normalizar a URL e `location ^~` para encaminhar `/avisaqui/`; upstream `45c28620-pager-virtual:8095/`; barra final no `proxy_pass` para retirar o prefixo público; timeout 3600s e buffering desativado para streams |
| Instagram | `nginx_proxy_default_instagram.conf` | três `location =` exatas; upstream `45c28620-umdoislab-instagram:8099`; sem barra final no `proxy_pass`, pois os caminhos OAuth/webhook devem chegar ao backend sem reescrita de prefixo |

**Cabeçalhos usados como padrão local:** `Host $http_host`, `X-Forwarded-Proto`, `X-Forwarded-For $remote_addr`, `X-Real-IP $remote_addr` e `proxy_redirect off`. O fragmento Instagram fixa `X-Forwarded-Proto https`, pois o TLS termina no NGINX e o backend recebe HTTP sem TLS (`use_ssl_backend: false`). Essa escolha deve ser mantida coerente com a URL pública HTTPS e validada no teste externo.

**Por que o Instagram usa locations exatas:** OAuth start, callback e webhook são endpoints específicos. Não é necessário criar um prefixo amplo para o painel. O fragmento limita métodos: GET nos endpoints OAuth; GET/POST no webhook, compatível com verificação e entrega de eventos da Meta. O painel administrativo não recebe uma location pública neste arquivo.

**Regra para novos serviços:** copiar o padrão do fragmento mais próximo do tipo de rota, alterando somente caminho público, upstream, porta, métodos e requisitos reais do serviço. Não copiar a barra final de `proxy_pass` sem avaliar se o prefixo deve ser removido. Não editar fragmentos de outros projetos.

### 7.5.1 Configuração de referência Avisaqui — conteúdo integral observado

Arquivo: `/share/nginx_proxy_default_avisaqui.conf`.

```nginx
location = /avisaqui {
    absolute_redirect off;
    return 308 /avisaqui/;
}

location ^~ /avisaqui/ {
    proxy_pass http://45c28620-pager-virtual:8095/;
    proxy_http_version 1.1;

    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Prefix /avisaqui;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Real-IP $remote_addr;

    proxy_redirect off;
    proxy_connect_timeout 5s;
    proxy_read_timeout 3600s;

    proxy_buffering off;
    proxy_cache off;
    client_max_body_size 3m;
}
```

**Detalhe funcional importante:** neste bloco, `proxy_pass` termina com barra (`/`). Como a diretiva está dentro de `location ^~ /avisaqui/`, o NGINX substitui o prefixo correspondente por `/` ao encaminhar. O cabeçalho `X-Forwarded-Prefix: /avisaqui` informa ao backend o prefixo público. O timeout de leitura de 3600 segundos e `proxy_buffering off` atendem às conexões longas/streams do Avisaqui.

**Comparação com o Artesão Digital:** o fragmento do Artesão usa `location ^~ /artesaos-piloto/` com `proxy_pass` sem URI final (sem barra depois da porta), preservando o caminho completo encaminhado ao upstream. Não copiar a barra final de um projeto para outro sem considerar a rota que o backend espera.

### 7.6 Procedimento objetivo para concluir a Central Instagram

1. Confirmar o arquivo em `/share/nginx_proxy_default_instagram.conf`, seu nome compatível com `customize.default` e o hash registrado em 7.4.
2. Não pedir novamente capturas de `customize.active/default`, nem o conteúdo dos fragmentos Artesão/Avisaqui: esses dados já estão registrados nesta seção.
3. A CLI `ha apps` permite consultar informações, logs e controlar apps, mas não expõe execução de shell no container. `docker` não está disponível no Terminal & SSH; o app NGINX declara `docker_api: false` e `host_network: false`.
4. Os logs enviados pelo proprietário terminam em 20/11/2026 18:52 e mostram timeouts do Supervisor/HA e recusas de conexão históricas do Avisaqui. Não mostram erro de sintaxe nem confirmam o carregamento do fragmento Instagram. Não usar esses logs para inferir falha ou sucesso do novo arquivo.
5. O arquivo Instagram foi criado às 18:45 em 20/11/2026. Às 19:01 o proprietário reiniciou `core_nginx_proxy`; o serviço NGINX iniciou e o app permaneceu `started` na versão 4.5.1. O backup foi criado em `/share/nginx_proxy_default_instagram.conf.rollback-20261120`; rollback não foi acionado.
6. Reinício controlado já realizado com backup prévio do fragmento. O NGINX iniciou sem erro fatal. Não repetir reinício sem motivo técnico.
7. Testes HTTPS públicos concluídos: `/oauth/meta/start` retornou 401; `/oauth/meta/callback` retornou 503; `/webhook/instagram` com desafio e token inválido retornou 503. O teste confirma encaminhamento ao servidor da Central e comportamento esperado com recursos desligados. Não atualizar o add-on de 4.5.1 para 4.5.3 como parte desta tarefa.

**Resultado conhecido:** fragmento carregado após reinício do proxy e três rotas respondendo pela URL pública HTTPS com os códigos esperados. O teste `nginx -t` foi feito apenas em ambiente isolado, não dentro do add-on real. A validação operacional das rotas foi aprovada por seus códigos de resposta; OAuth e webhook ainda estão desligados.

### 7.5.2 Validação estática do fragmento Instagram — 20/11/2026

Foi feita conferência direta da fonte privada `mmcromero/instagram-automacoes`, branch `feat/instagram-lote1-conexao-real`:

- `deploy/nginx_proxy_default_instagram_oauth.conf` define exatamente as três rotas preparadas para o Raspberry.
- `instagram-central/server.py` confirma `GET /oauth/meta/start`, `GET /oauth/meta/callback`, `GET /webhook/instagram` para desafio Meta e `POST /webhook/instagram` para eventos.
- A rota `/oauth/meta/status` exige autenticação e não foi exposta no fragmento. Painel, bridge e health também não foram expostos.
- O callback usa query string; NGINX `location = /webhook/instagram` continua correspondendo ao caminho mesmo quando a URL contém query string, pois a seleção de location não considera os argumentos.
- O código mantém `meta_oauth_enabled` e `ingress_enabled` desativados por padrão; a publicação da rota não ativa OAuth nem webhook no aplicativo.

**Teste de sintaxe isolado:** NGINX 1.26.3 local executou `nginx -t` com sucesso para os três blocos e diretivas. Para isolar a gramática, o upstream foi substituído por `127.0.0.1:8099` e os blocos foram inseridos em um `server{}` de teste. Isso valida a sintaxe das diretivas, mas **não** valida o arquivo exato no add-on 4.5.1, a resolução DNS interna do container, o conjunto completo de includes do HA ou o carregamento real.

**Resultado:** rotas e métodos conferem com o código da aplicação; sintaxe dos blocos aprovada em ambiente isolado. Falta validar a configuração real no add-on e o HTTPS público.

### 7.5.3 Reinício controlado e testes HTTPS públicos — 20/11/2026

**Operação executada pelo proprietário no Terminal & SSH:**

- Backup criado: `/share/nginx_proxy_default_instagram.conf.rollback-20261120`.
- `ha apps restart core_nginx_proxy` terminou com sucesso.
- Após 5 segundos, `ha apps info core_nginx_proxy` informou `state: started`, `version: 4.5.1`.
- Logs registraram parada normal do serviço NGINX e nova inicialização: `Generating nginx.conf from template` e `Running nginx...`.
- O fluxo não executou rollback.

**Testes HTTPS externos executados pelo proprietário em `https://romeropi.duckdns.org:8443`:**

| Rota | Resultado HTTP | Interpretação |
|---|---:|---|
| `GET /oauth/meta/start` | 401 | Rota chegou ao servidor; painel exige autenticação |
| `GET /oauth/meta/callback` | 503 | Rota chegou ao servidor; OAuth desativado/incompleto |
| `GET /webhook/instagram?hub.mode=subscribe&hub.verify_token=teste-invalido&hub.challenge=123` | 503 | Rota chegou ao servidor; webhook desativado |

Os três códigos são coerentes com as condições do código da aplicação. O 503 do webhook ocorreu antes da validação do token, pois `ingress_enabled` está desativado. Não é um teste de aceitação de desafio Meta. O 401 de start confirma a barreira de autenticação do painel, não a conclusão do OAuth.

**Conclusão:** NGINX ativo após reinício, fragmento Instagram incluído pelo padrão configurado e três rotas alcançam o backend pela URL pública HTTPS. Não há evidência de erro fatal de configuração nos logs de inicialização apresentados. Não declarar OAuth conectado, webhook inscrito ou DM recebida.

**Próxima fase:** conferir as opções efetivas da Central (sem revelar segredos), validar os campos públicos do app Meta e habilitar OAuth de forma controlada. Depois executar login Meta, validar a identidade exata de `@umdoislab`, testar a inscrição `messages` e habilitar webhook somente quando OAuth e assinatura estiverem confirmados. Não ativar envio de mensagens.

### 7.5.4 Teste de rotas após reinício — evidência do proprietário (20/11/2026)

Base pública testada: `https://romeropi.duckdns.org:8443`.

| Requisição | HTTP | Leitura correta |
|---|---:|---|
| `GET /oauth/meta/start` sem sessão | 401 | Proteção administrativa exigida; resposta esperada sem cookie de painel |
| `GET /oauth/meta/callback` sem fluxo OAuth ativo | 503 | OAuth desativado/incompleto; resposta esperada nesta fase |
| `GET /webhook/instagram` com desafio e token inválido | 503 | Webhook desativado (`ingress_enabled=false)); resposta esperada nesta fase |

**Conclusão:** o proxy público encaminha as três rotas para a aplicação. O HTTP 401 não é falha de OAuth: o start exige sessão administrativa. Os HTTP 503 não são falha de proxy: são as travas da aplicação enquanto OAuth e webhook permanecem desligados. Próxima fase é configurar os campos Meta localmente e habilitar apenas OAuth; manter webhook desligado até a autorização da conta ser verificada.

### 7.5 Limites de evidência

- A captura da configuração e os comandos foram fornecidos pelo proprietário; não foram executados diretamente por um agente remoto.
- DNS/HTTP interno aprovado não equivale a teste TLS público.
- Arquivo criado não equivale a configuração validada/carregada.
- Não foi feita atualização do add-on, reload, restart, alteração dos arquivos do Artesão/Avisaqui ou ativação da Meta nesta verificação.

## 8. Controle de mudanças

A captura é evidência do estado de 19/11/2026, não estado vivo. Mudanças confirmadas devem atualizar **este documento central** na `main`, com data, origem, commit e referência à Issue existente. Os demais projetos devem **apontar para este arquivo**, não copiar inventários independentes que fiquem obsoletos. Nenhum documento autoriza ação destrutiva ou modifica automaticamente instruções em chats já abertos.
