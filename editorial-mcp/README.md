# Central Editorial MCP universal — 0.1.1 (candidata)

Este aplicativo é independente da Central Instagram e de plugins OpenAI. Não lê o banco da Central, não altera OAuth/Meta, não usa o n8n e não expõe Supervisor. A Central continua responsável por autenticação, isolamento, validade/revogação da chave, cotas, normalização, rascunhos e recibos. Não existe ferramenta de publicação, exclusão ou leitura geral do acervo.

## Instalação e ativação controlada

1. Após publicação autorizada no catálogo, instalar somente **Fábrica de Softwares - Central Editorial MCP**. Configurar `central_url` com a origem HTTPS real já salva na Central (sem `/panel`), deixando `funnel_enabled: false`. Iniciar. Nenhuma porta do host é publicada; servidor HTTP local em 127.0.0.1:8765. Não usar TLS inseguro no upstream.
2. Para acesso Claude cloud, ativar `funnel_enabled: true` somente neste novo aplicativo e iniciar. O processo usa Tailscale v1.104.7 em userspace, com estado e socket próprios no volume do app. Não modificar o Tailscale existente, nem habilitar compartilhamento do HA. Autorizar o nó **central-editorial-mcp** pelo link de login nos logs do novo app, se solicitado. Não enviar o link de autenticação ao chat. MagicDNS, certificados HTTPS e permissão Funnel para o nó são requisitos do provedor. Se o CLI recusar por política, parar e revisar a autorização limitada ao novo nó; não ampliar globalmente por tentativa. URL HTTPS candidata sai nos logs após o CLI aceitar o Funnel; somente teste externo confirma acesso. A porta pública exigida pelo Claude é 443. Não presumir que o IP/hostname/URL da Central REST é o MCP.
3. Na Central, selecione a conta, Configurações Meta → Ferramentas → Conectar ferramentas de criação. Crie chave exclusiva (nome Claude ou outra ferramenta), sem publicação direta. A chave de integração expira em 90 dias conforme Central; revogar na Central interrompe acesso. Não copiar em mensagens, URLs, Git, logs nem configurações compartilhadas.
4. No Claude: Personalizar → Conectores → Adicionar conector personalizado. Nome Central Editorial; URL HTTPS real obtida no passo 2, com `/mcp`. Autenticação **Sem login** (sem OAuth); em Cabeçalhos de requisição, nome `X-Editorial-Key`, valor a chave `cei1` recém-criada. O servidor continua exigindo autenticação pelo cabeçalho. Para outra conta, crie outra chave/conector; não escolha conta por argumento nem reutilize chave de produção do ChatGPT. Se o aplicativo não aceitar o cabeçalho personalizado, registrar impedimento e usar cliente HTTP/SDK compatível; não expor o servidor sem chave.
5. Primeiro, peça `consultar_conexao`. Confirme a conta retornada. Nenhuma transferência. Após autorização específica, testar envio de pequena mídia de diagnóstico e legenda para revisão; consultar `consultar_envio` pelo mesmo requestId e conferir o rascunho. Não publicar. Somente depois testar arquivo real do chatbot e ativar iniciar com o sistema, se desejado.

## Contrato MCP

Streamable HTTP `/mcp`, JSON-RPC, handshake `initialize`/`notifications/initialized`, `tools/list`/`tools/call`; sem SSE persistente ou sessão. Protocolos suportados neste lote: 2025-03-26, 2025-06-18 e 2025-11-25. Clientes dual-era podem negociar a revisão anterior; cliente exclusivamente 2026-07-28 não é suportado. Compatibilidade Claude real pendente. GET não abre stream (405); POST autenticado. Host e Origin validados. Chave não é um parâmetro de ferramenta. Cada POST confirma a chave pelo recibo reservado sem mutação, depois encaminha somente operações da API fixa; não há armazenamento de chaves no adaptador.

- `consultar_conexao`: conta derivada da chave após validação pela Central; publicação indisponível pelo MCP.
- `consultar_envio`: `requestId` estável, 16–100 caracteres alfanuméricos/underscore/hífen.
- `enviar_para_revisao`: `requestId`, `transferApproved: true` somente após pedido explícito do cliente, `format` (`feed`, `story`, `reel`, `carousel`), `caption` até 2200 caracteres, `media` em ordem, itens `{mime, base64}`. JPEG/PNG/MP4; quantidade compatível com formato; máximo 4 MiB agregados no adaptador, abaixo do limite REST de 25 MiB por arquivo. A Central valida a mídia conforme formato, normaliza e cria rascunho atômico; o adaptador calcula o mesmo resumo SHA-256 do cliente original. Reutilize requestId em falhas; consulte recibo antes de repetir. Não invente bytes; não mande URLs, caminhos ou referências de arquivos que o cliente não consegue ler. Um recibo encontrado pode refletir estado de publicação manual na Central; não significa que o MCP publicou.

**Limitação importante:** MCP não dá automaticamente acesso aos bytes de anexos ou imagens geradas em um chatbot. Base64 é uma interface inicial para clientes capazes de obter os bytes reais, não prova de upload pelo Claude no celular. O transporte privado de arquivos (ex.: Drive, com credencial e escopo próprios) é etapa separada; não usar links públicos, não tentar ler o Drive inteiro. A integração ChatGPT/Drive existente não é tocada.


## Diagnóstico opt-in da candidata 0.1.1

A opção `diagnostics_enabled` vem desativada por padrão. Quando habilitada, o app registra apenas linhas `DIAG` locais após o CLI aceitar o Funnel:

- versão Tailscale;
- estado do backend, online/offline, correspondência do hostname esperado, presença da capacidade Funnel e contagem de peers de ingresso (sem identidades);
- resumo de `funnel status` e `serve status`, sem despejar a saída bruta;
- campos allowlisted de `netcheck`, sem endereço IP;
- falhas reduzidas ao nome da classe de exceção.

A saída do CLI é capturada como texto para parsing explícito. Não cria endpoint HTTP de diagnóstico, não envia logs ao Tailscale, não executa `bugreport`, não altera Funnel/Serve/ACL e não coleta token, URL de login, IP ou identidade de peers. A evidência local não substitui uma sonda HTTPS externa.

## Segurança e reversão

Sem privilégios de host, portas mapeadas, Supervisor API, credencial Meta, shell remoto ou chave persistida pelo adaptador. Ficheiro de estado do nó em /data e socket próprio. Desativar `funnel_enabled` e reiniciar este app ou pará-lo encerra seu acesso; nenhuma mudança no Tailscale principal. Para revogar chave, use a Central; para remover nó dedicado, peça autorização separada, confirme o nome exato no painel Tailscale. Não use reset ou logout no nó existente. Logs do adaptador não mostram corpo, chave ou arquivos; logs do CLI de primeira autorização devem ficar privados. Nenhuma dependência de GitHub Actions.

## Verificação e fontes

O build do Supervisor executa `python3 -m py_compile` e as suítes `python3 -m unittest -v test_server test_run_diagnostics`, com API simulada e sem rede externa. Isso não comprova build ARM64 real, acesso público HTTPS, cliente Claude ou transferência de mídia real. Verificar os casos de autenticação, conta, autorização, conflito, recibo, Host/Origin e ausência de publicação. Build no Supervisor, Tailscale/Funnel, TLS e conexão Claude em ambiente real ainda exigem homologação. Não declarar compatibilidade de cliente nem mídia real sem evidência.

- https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp
- https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning
- https://tailscale.com/docs/features/tailscale-funnel
- https://tailscale.com/docs/reference/tailscale-cli/funnel
- https://tailscale.com/docs/reference/tailscale-cli/up
- https://tailscale.com/docs/features/containers/docker/docker-params
