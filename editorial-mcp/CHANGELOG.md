## 0.1.2 — candidata de transporte privado de arquivos

- Novos tools `validar_arquivo_temporario` (somente leitura, sem transferência) e `enviar_arquivo_temporario_para_revisao` (transferência após aprovação explícita). para referências temporárias assinadas emitidas pelo host ChatGPT após leitura de arquivos pelo conector.
- Allowlist HTTPS de subdomínios `oaiusercontent.com`, caminho `/files/`, assinatura de leitura, validade máxima de 15 minutos e redirects recusados.
- Download em memória com limite de 4 MiB agregado, validação de MIME/magic, tamanho e SHA-256; URL nunca é registrada nem persistida.
- Mantém envio Base64 para outros clientes MCP; não aceita URL pública do Drive ou URL arbitrária.
- Testes sem rede para allowlist, expiração, redirects, hash, tamanho, idempotência e ausência de publicação.
- Mantém diagnósticos Tailscale/Funnel locais opt-in; nenhuma alteração no Tailscale principal.
- A prova positiva foi executada na PoC isolada, não no add-on. O build ARM64 e a homologação MCP/cliente ainda estão pendentes.

## 0.1.1 — candidata de diagnóstico

- Inclui diagnóstico local opt-in para investigar Tailscale/Funnel sem criar endpoint público.
- Captura do CLI em modo texto e parsing explícito; sem saída bruta, IPs, identidade de peers, links de login ou segredos.
- Testes sem rede para parsing e sanitização dos diagnósticos.
- Build do Supervisor executa as suítes do adaptador e do diagnóstico.
- `diagnostics_enabled` permanece false por padrão; nenhuma alteração no Tailscale principal.
- Não inclui integração Google Drive; H2 permanece pendente.

## 0.1.0 — candidata

- Adaptador MCP Streamable HTTP, sem sessão, versões 2025-03-26/06-18/11-25.
- Chave exclusiva da Central por cabeçalho; validação de conta e revogação delegada à API existente; sem ferramentas de publicação.
- Consulta da conexão, recibo e transferência explícita de mídia (bytes em base64) com legenda. Limite inicial de 4 MiB agregados.
- Nó Tailscale dedicado em userspace, Funnel opcional inicialmente desativado; nenhum mapeamento de porta, privilégio, rota, compartilhamento de estado ou alteração de outro app.
- Testes locais com API simulada. Build, acesso externo, cliente Claude e mídia gerada real ainda não homologados.
