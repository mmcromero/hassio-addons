# 0.1.10 — receptor de compartilhamento Android (candidata)

- Adiciona PWA instalável com Web Share Target para receber arquivos JPEG/PNG/MP4 compartilhados pelo sistema Android.
- Adiciona API autenticada por chave cei2 para listar contas e transferir mídia selecionada para revisão, com destino validado pela Central.
- Arquivos recebidos ficam temporariamente no IndexedDB do navegador; fila expira em 24 horas. Chave não é persistida no navegador.
- Mantém o fluxo MCP 0.1.9, a autenticação existente, o slug e a configuração do Funnel. Nenhuma publicação automática.
- Testes de contrato adicionados; build Supervisor e homologação real Android/ChatGPT/Claude ainda pendentes.

# 0.1.9 — conexão multi-conta e Drive privado

- Preserva contrato cei1. Nova chave cei2 requer Central Instagram 0.1.39; listagem dinâmica, destino explícito, teste Drive somente leitura e transferência por IDs. Sem publicação direta ou exclusão Drive. Slug, ícone, logo e túnel preservados. Provisionamento e teste real Drive pendentes.

## 0.1.8 — identidade visual padronizada (candidata)
- Inclui `icon.png` e `logo.png` com os mesmos blobs oficiais já usados pelos demais apps do catálogo: icon `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a`; logo `7e500016222b0a5bf395be8ed17447edeb3e2af9`.
- Atualiza `config.yaml`, `serverInfo.version` e o teste de contrato para 0.1.8.
- Preserva integralmente a autenticação 0.1.7: `X-Editorial-Key` para clientes existentes e `X-API-Key` padrão para Claude; sem mudança de permissões ou isolamento.
- Não altera opções, estado Tailscale, Central, plugin, n8n, credenciais ou dados persistentes.
- Gate seguinte: build do Supervisor na atualização do Home Assistant e conexão real do Claude; não declarar homologação de cliente antes do teste.

## 0.1.7 — compatibilidade Claude via cabeçalho padrão (candidata)
- Aceita a chave editorial pelo cabeçalho original `X-Editorial-Key` ou pelo cabeçalho padrão `X-API-Key`, preservando o mesmo formato `cei1...` e a validação por conta na Central.
- Rejeita requisições com ambos os cabeçalhos ou valores repetidos; nenhuma rota de autenticação alternativa sem chave foi criada.
- Mantém compatibilidade do n8n sem alteração de sua credencial atual; permite Claude Custom Connector usar `x-api-key`, cabeçalho padrão aceito pela Anthropic sem depender da aprovação de cabeçalho personalizado.
- Adiciona testes de aceitação do cabeçalho padrão, recusa de duplicidade e recusa de chave malformada antes da validação upstream.
- O build ARM64 do Supervisor concluiu e o app 0.1.7 iniciou no Home Assistant. O Dockerfile executou `py_compile` e as suítes integradas; a conexão real pelo cliente Claude continua pendente.

## 0.1.6 — correção da configuração persistente TLS
- Configurar explicitamente o diretório privado VarRoot via `--statedir`, preservando estado, socket e identidade existentes.
- Ajustar timeout de handshake em sonda opt-in (75 s, após conexão de 8 s); classificar ausência de VarRoot sem expor dados.
- 12 testes locais dirigidos aprovados; build integral de 33 casos e TLS externo pendentes.
- Não altera autenticação, opções, publicação, Central ou outros serviços.

## 0.1.5 — diagnóstico TLS dirigido, não homologado
- Captura sanitizada de eventos do daemon; sonda local, DNS, JSON do Funnel, TLS verificado e certificado dedicado temporário quando necessário.
- Oito testes novos; nenhum acesso a Meta, Drive ou Central durante os testes locais.
- Identificado requisito OAuth do ChatGPT remoto; não resolvido nesta versão, chave editorial preservada.

## 0.1.4 — correção dos testes de build (não homologada)

- Corrige importação de `run` em `test_diagnostics.py`, eliminando o `NameError` identificado no build ARM64 real do Supervisor.
- Atualiza o contrato de versão em `test_server.py` para conferir `serverInfo.version = 0.1.4`.
- Atualiza `config.yaml` e `server.py` para a versão 0.1.4, evitando reutilizar a tag de build 0.1.3 que falhou.
- Evidência do Supervisor: 22 dos 24 testes passaram; 1 falhou por expectativa de versão antiga e 1 erro por import ausente. Nenhum teste de integração real foi homologado.

## 0.1.3 — correção de build (não homologada)

- Remove bloco MCP duplicado e truncado que ficou após `make_server()` e causava `SyntaxError: unmatched '}'` na linha 428.
- Preserva o bloco `TOOLS` e a função `dispatch` válidos, incluindo as cinco ferramentas previstas para a integração Google Drive/ChatGPT.
- Mantém o build do Supervisor como gate: `py_compile` seguido pelas 24 verificações automatizadas.
- Build anterior 0.1.2 falhou antes dos testes; 0.1.3 ainda não foi construída nem homologada.

## 0.1.2 — candidata de transporte privado de arquivos (não homologada)

- Acrescenta `validar_arquivo_temporario`, ferramenta somente leitura que baixa em memória e valida MIME, tamanho e SHA-256 sem transferir à Central.
- Acrescenta `enviar_arquivo_temporario_para_revisao`, que aceita somente referência assinada temporária do host ChatGPT, após autorização explícita, e usa o fluxo de importação existente para criar rascunho de revisão.
- Restringe a referência a HTTPS em subdomínio `oaiusercontent.com`, caminho `/files/`, escopo exato `sp=r`, assinatura e validade restante de até 24 horas; recusa hosts externos, links do Drive, traversal e redirects.
- Download em memória, limite agregado de 4 MiB, verificação de tamanho, assinatura do formato e SHA-256. Sem persistência da imagem ou da URL pelo Worker.
- Mantém a transferência Base64 para outros clientes MCP e preserva os diagnósticos locais opt-in 0.1.1 do Tailscale/Funnel.
- Mantém `diagnostics_enabled` opcional e desligado quando ausente, preservando configurações existentes da versão 0.1.0 sem exigir alteração manual.
- Inclui testes específicos da ponte temporária e executa, no build, as suítes MCP, diagnóstico e ponte.
- Evidência PoC 0.1.3: 1.977.007 bytes recebidos, SHA-256 conferido, recibo R2 confirmado e nenhuma imagem persistida. Não equivale a homologação do add-on nem a transferência à Central.
- Build ARM64, execução integral dos testes, teste no add-on instalado e homologação externa ainda pendentes.

## 0.1.1 — candidata diagnóstica (não homologada)

- Alinha `serverInfo.version` do handshake MCP à versão do pacote.
- Adiciona coleta local opt-in de estado do Tailscale/Funnel/Serve/netcheck, desativada por padrão e sem endpoint HTTP novo.
- Reduz logs a indicadores sanitizados; não registra JSON bruto, IPs, portas, regiões, nomes de peers, tokens, chaves ou URLs de login.
- Inclui teste dirigido para garantir que IP, porta e região não apareçam no resumo do netcheck.
- Build, testes e homologação no Home Assistant ainda pendentes.

## 0.1.0 — candidata

- Adaptador MCP Streamable HTTP, sem sessão, versões 2025-03-26/06-18/11-25.
- Chave exclusiva da Central por cabeçalho; validação de conta e revogação delegada à API existente; sem ferramentas de publicação.
- Consulta da conexão, recibo e transferência explícita de mídia (bytes em base64) com legenda. Limite inicial de 4 MiB agregados.
- Nó Tailscale dedicado em userspace, Funnel opcional inicialmente desativado; nenhum mapeamento de porta, privilégio, rota, compartilhamento de estado ou alteração de outro app.
- Testes locais com API simulada. Build, acesso externo, cliente Claude e mídia gerada real ainda não homologados.
