# Central Editorial MCP universal — 0.1.6 (TLS validado; autenticação MCP pendente)

**Estado verificado em 23/11/2026, 09:09–09:15 BRT:** versão 0.1.6 instalada e iniciada no Home Assistant ARM64; Supervisor registra build Docker concluído e atualização bem-sucedida. A correção de `--statedir=/data/editorial-mcp-tailnet` foi aplicada sem mover o estado do nó. O Tailscale 1.104.7 está online; Funnel confirma HTTPS 443, publicação e destino loopback 8765; DNS A/AAAA está resolvido; a sonda TLS do aplicativo registrou `external_tls=verified`. GET local 405 é esperado para este endpoint POST-only. O evento sanitizado `daemon_event=rate_limit` ainda aparece, mas não impede o handshake TLS verificado e não prova, isoladamente, rate limit ACME.

## Homologação 0.1.6 — evidências e próximo gate

- **Build ARM64:** Supervisor: `Build ...:0.1.6 done`; `App ... successfully updated`. O Dockerfile executa `py_compile` e as quatro suítes de testes durante o build; a imagem só foi concluída após esses comandos.
- **TLS/Funnel:** `external_tls=verified`; `funnel_config=https_443=True public=True loopback_target=True`; DNS A/AAAA verdadeiro; `loopback_http=405` esperado. Tailscale BackendState Running, nó dedicado online e 23/23 peers de ingresso online.
- **Endpoint MCP:** `https://central-editorial-mcp.taila6d74.ts.net/mcp` (não confundir com `central_url`, que é a origem HTTPS da Central REST na porta 8443).
- **Autenticação:** cada POST exige `X-Editorial-Key` no formato da chave editorial `cei1...`; sem chave válida o servidor responde 403 sem corpo. O teste n8n sem autenticação e uma tentativa com credencial genérica existente não concluíram o handshake. Não foi localizada uma credencial dedicada identificável como `X-Editorial-Key`; não reutilizar credenciais por tentativa.
- **Intervenção mínima pendente:** na Central, gerar uma chave exclusiva para a conta **Umdoislab**; no n8n, criar uma credencial **Header Auth** com nome do cabeçalho `X-Editorial-Key` e valor da chave. Guardar o segredo somente no cofre de credenciais do n8n — nunca colar no chat. Depois, localizar o ID pelo inventário de credenciais e executar `verify_agent_mcp_server` para listar as cinco ferramentas. Repetir com chave e credencial próprias para **Tudo é 3D** para homologar isolamento multi-conta.
- A documentação oficial do n8n confirma suporte a autenticação por cabeçalho genérico no MCP Client; o tipo Header Auth configura nome e valor de cabeçalho: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-langchain.mcpClient/ e https://docs.n8n.io/integrations/builtin/credentials/httprequest/ .

- **ChatGPT direto:** a documentação OpenAI vigente em 23/11/2026 informa que conexões MCP personalizadas com suporte completo (incluindo escrita) no ChatGPT web estão disponíveis em Business e Enterprise/Edu; Pro tem apenas leitura/recuperação. A conta Plus não tem suporte a essa conexão customizada. Portanto, o caminho ChatGPT atual permanece o plugin original 1.1.1 (já confirmado nas duas contas); o MCP 0.1.6 atende n8n, Claude e clientes compatíveis com cabeçalho. Não tentar contornar a política do ChatGPT com chave estática. Uma futura conexão direta via OAuth 2.1 é uma frente separada e ainda exige provedor, metadados protegidos, autorização por conta e refresh token. Fontes: https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt ; https://developers.openai.com/plugins/build/auth .

- **Plugin ChatGPT preservado:** adapter 1.1.1 conectado nas contas Umdoislab e Tudo é 3D; ambas retornam `transfer_to_review` e `read_own_receipts`; publicação direta indisponível. Nenhuma imagem foi transferida e nenhuma publicação foi feita nesta retomada.
- Nenhum ajuste no Tailscale principal, NGINX compartilhado, n8n workflows, Central REST, Meta ou Google Drive. A única pendência manual é criar e guardar a credencial de integração acima; não é necessário reinstalar ou reiniciar o app.

## Histórico de 0.1.5 (anterior)
# Central Editorial MCP universal — 0.1.5 (diagnóstico TLS, não homologada)

**Estado atual:** 0.1.4 instalada e iniciada no ARM64; Funnel aceito, mas sonda MCP n8n reproduziu alerta TLS 80 antes de HTTP. 0.1.5 acrescenta diagnóstico/correção potencial de emissão, não prova resolução. As instruções históricas abaixo podem referir-se a versões anteriores. O build de 0.1.5 executa 32 testes, dos quais oito novos foram executados localmente; build integral e homologação ainda pendentes.

**Compatibilidade:** Claude documenta cabeçalho personalizado; ChatGPT remoto não suporta chave API personalizada e exige OAuth 2.1 para operações privadas. Não desativar segurança. Plugin ChatGPT 1.1.1 preservado e confirmado para as duas contas. OAuth universal requer provedor e associação autenticada com conta/chave editorial, não simplesmente aceitar tokens sem validação. Fonte: https://developers.openai.com/plugins/build/auth e https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp.

**Diagnóstico:** com diagnostics_enabled=true, a saída do daemon é consumida em thread e somente categorias fixas são registradas. O diagnóstico testa GET local (405 esperado), DNS do container, configuração estrutural Funnel, TLS com validação de CA/SNI, e só em erro TLS executa uma tentativa limitada de certificado do nó dedicado em diretório temporário privado, posteriormente removido. Pode solicitar emissão; não repetir reinícios para forçar emissão. Nenhum certificado/chave ou saída bruta aparece nos logs. Não altera outros nós, a Central, OAuth Meta ou o HA.


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

## Segurança e reversão

Sem privilégios de host, portas mapeadas, Supervisor API, credencial Meta, shell remoto ou chave persistida pelo adaptador. Ficheiro de estado do nó em /data e socket próprio. Desativar `funnel_enabled` e reiniciar este app ou pará-lo encerra seu acesso; nenhuma mudança no Tailscale principal. Para revogar chave, use a Central; para remover nó dedicado, peça autorização separada, confirme o nome exato no painel Tailscale. Não use reset ou logout no nó existente. Logs do adaptador não mostram corpo, chave ou arquivos; logs do CLI de primeira autorização devem ficar privados. Nenhuma dependência de GitHub Actions.

## Verificação e fontes

`python3 -m py_compile server.py run.py test_server.py test_diagnostics.py test_host_file_bridge.py` e `python3 -m unittest -v test_server test_diagnostics test_host_file_bridge` são os gates do build. As suítes usam HTTP local, Central simulada e download HTTP simulado; não acessam Drive, Meta ou internet real. Cobrem autenticação, isolamento de conta, autorização, recibos, Host/Origin, ausência de publicação, sanitização de diagnóstico e ponte de arquivo temporário. As 24 verificações são executadas pelo próprio Dockerfile durante o build do Supervisor: 9 testes de contrato MCP, 3 de diagnóstico/compatibilidade e 12 da ponte temporária, precedidos por `py_compile`. Não há runner externo, QEMU ou GitHub Actions como pré-requisito. O resultado só será PASS após a construção real da candidata no Home Assistant. Tailscale/Funnel, TLS e conexão de cliente em ambiente real exigem homologação. Não declarar compatibilidade de cliente nem mídia real sem evidência.

- https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp
- https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning
- https://tailscale.com/docs/features/tailscale-funnel
- https://tailscale.com/docs/reference/tailscale-cli/funnel
- https://tailscale.com/docs/reference/tailscale-cli/up
- https://tailscale.com/docs/features/containers/docker/docker-params


## Diagnóstico local opt-in — candidata 0.1.1

A versão 0.1.1 acrescenta `diagnostics_enabled`, opcional e desativada por padrão. A chave não tem valor padrão obrigatório no manifesto; quando ausente em instalações antigas, o código a interpreta como `false`. Quando habilitada, o app grava no log local apenas estados sanitizados de versão, identidade/estado do nó, contagem de peers de ingresso, resumo Funnel/Serve e conectividade grosseira. Não imprime JSON bruto, nomes/IPs de peers, endereços, tokens, chaves, state file ou URL de login. Não cria rota HTTP de diagnóstico, não executa bugreport e não envia dados externamente. A coleta é somente leitura.

O teste `test_diagnostics.py` verifica que IP, porta e região não aparecem no resumo do netcheck. A execução automatizada desse teste ocorre junto às demais suítes no build do Supervisor. O código preparado, por si só, não comprova a causa da falha TLS.


## Ponte privada de arquivos do host ChatGPT — candidata 0.1.2

A candidata 0.1.2 acrescenta duas ferramentas para o fluxo ChatGPT + conector Google Drive, sem credencial Google no add-on e sem link público do Drive:

- `validar_arquivo_temporario`: baixa uma referência temporária em memória e retorna apenas MIME, tamanho e SHA-256. Não faz upload/commit de mídia à Central, não transfere conteúdo nem persiste a imagem. A autenticação MCP continua usando a consulta de recibo de prova já existente.
- `enviar_arquivo_temporario_para_revisao`: após solicitação explícita do usuário, valida e envia o arquivo ao fluxo existente de importação da Central, criando apenas o rascunho de revisão. Não publica.

### Fluxo

1. O conector Google Drive autenticado lê o arquivo privado com `fetch(download_raw_file=true, include_base64=false)`.
2. O host ChatGPT disponibiliza `file_uri.download_url`, referência assinada e temporária; não é URL pública do Drive.
3. A chamada MCP envia a referência temporária, MIME, tamanho e SHA-256 esperado.
4. O Worker aceita somente HTTPS em subdomínio `oaiusercontent.com`, caminho `/files/`, escopo de leitura exato (`sp=r`), assinatura e validade restante de até 24 horas (compatível com a validade observada na referência real do host). Recusa host externo, links do Drive, caminhos com traversal e redirecionamentos.
5. O Worker baixa em memória, limita o tamanho, confere assinatura do formato e SHA-256 antes de usar `import_upload` e `import_commit` da Central.

A referência temporária é um segredo bearer: trafega somente no payload privado da chamada MCP, não deve ser copiada para canais públicos e não é gravada em logs, recibos ou disco pelo add-on. O arquivo não é persistido pelo Worker. Limite inicial agregado: 4 MiB por transferência. O original permanece privado no Drive.

### Limites e evidências

- O caminho comprovado na PoC é Drive privado → conector autenticado ChatGPT → URL temporária do host → Worker. O Worker não acessa a API do Google Drive diretamente.
- A PoC isolada 0.1.3 recebeu 1.977.007 bytes, confirmou SHA-256 e recibo R2 e não persistiu a imagem. Isso prova o transporte host→Worker, não a integração 0.1.2 instalada nem a transferência à Central.
- A reutilização da mesma referência após o prazo `se` falhou fechada (`HOST_DOWNLOAD_UNAVAILABLE`), sem receber bytes ou persistir mídia.
- Outros clientes MCP continuam usando `enviar_para_revisao` com bytes Base64 reais.
- Esta candidata preserva os diagnósticos opt-in 0.1.1 de Tailscale/Funnel. O teste `test_diagnostics.py` permanece parte obrigatória da suíte.

### Validação ainda necessária

O código foi integrado à fonte privada `instagram-automacoes:desenvolvimento`. A revisão estática encontrou uma divergência no bloco de ferramentas da cópia de distribuição anterior; por isso, aquela cópia não é fonte confiável para gerar pacote. A implementação fonte foi recomposta sobre a base 0.1.1, preservando os diagnósticos e corrigindo o contrato MCP.

Ainda não foram executados nesta retomada o conjunto completo de testes, o build ARM64, o teste da ferramenta no add-on instalado, a sonda HTTPS externa ou a transferência real à Central. Não declarar PASS até obter essas evidências. A candidata 0.1.2 está congelada na branch privada `release-candidate`; ainda não foi publicada no catálogo, instalada ou homologada no Home Assistant.

