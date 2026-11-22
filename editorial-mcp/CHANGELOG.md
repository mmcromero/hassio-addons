## 0.1.0 — candidata

- Adaptador MCP Streamable HTTP, sem sessão, versões 2025-03-26/06-18/11-25.
- Chave exclusiva da Central por cabeçalho; validação de conta e revogação delegada à API existente; sem ferramentas de publicação.
- Consulta da conexão, recibo e transferência explícita de mídia (bytes em base64) com legenda. Limite inicial de 4 MiB agregados.
- Nó Tailscale dedicado em userspace, Funnel opcional inicialmente desativado; nenhum mapeamento de porta, privilégio, rota, compartilhamento de estado ou alteração de outro app.
- Testes locais com API simulada. Build, acesso externo, cliente Claude e mídia gerada real ainda não homologados.
