# Proveniência — Central Editorial MCP 0.1.6

Fonte privada: `mmcromero/instagram-automacoes` / `release-candidate` / `43b60e0ffdd7a8140a3aab0d762b358d530e059e`.

Correção efetiva da configuração VarRoot do Tailscale 1.104.7: `--statedir` explícito preserva arquivo de estado e socket dedicados. Doze testes dirigidos locais aprovados (dois módulos de teste, servidor HTTP isolado por stub). Quatro blobs testados conferidos. Build com 33 testes no Supervisor e emissão de certificado/HTTPS externo ainda pendentes. Nenhum Actions acionado. A 0.1.5 permanece instalada até atualização pelo operador. OAuth e homologação de clientes ainda pendentes. Nenhuma publicação em rede social.

| Arquivo | Git blob SHA |
|---|---|
| CHANGELOG.md | b90016b94e1f7842af96ee3585dd0ce8da8387fc |
| DIAGNOSTICS.md | 5097818c7586b5002b47c6e814f6eae31515eddc |
| Dockerfile | 2deb28eecdb8628d15f6dc4d5dd9efd6dc5b40f2 |
| README.md | b4ba3263c126b6ef0366bd6bda8739d6557be0df |
| config.yaml | 6c43f1f22287461c46f5cf01017174ea3e89857f |
| funnel_probe.py | 1ce8d5c463dbd89d70edb108f6335e42530495b6 |
| run.py | 3284ca3510d0eb34ace52b47a19a66301a467728 |
| server.py | a0a64cc309e03bc14e5408c0e414a98ec864eb8e |
| test_diagnostics.py | 8298eb22baaf3c0e7a3833c3388b36c1f1779477 |
| test_funnel_probe.py | 8d9a73355b5e45a0f190704cbee09b40d23a10f8 |
| test_host_file_bridge.py | 23187cc36df597ba6ed3a661c1de5e2cffeff850 |
| test_server.py | 063f62e6f5dcf9dbde9f2e291f5366692fdf669c |


## Homologação em 23/11/2026 09:09–09:15 BRT
- Supervisor confirmou build ARM64 0.1.6 concluído e app atualizado/iniciado.
- Tailscale 1.104.7: external_tls=verified; HTTPS 443, Funnel public e proxy loopback 8765 verdadeiros; DNS A/AAAA resolvido; backend Running, nó online, 23/23 peers de ingresso online. GET 405 esperado.
- Endpoint: https://central-editorial-mcp.taila6d74.ts.net/mcp.
- n8n verify_agent_mcp_server não completou POST sem autenticação e com uma credencial genérica que não foi comprovada como X-Editorial-Key. O servidor exige esse cabeçalho e retorna 403 vazio se ausente/inválido.
- Próximo gate humano: criar chave específica para Umdoislab na Central e credencial n8n Header Auth com header name X-Editorial-Key; não enviar o segredo pelo chat. Após isso, testar MCP tools/list e consultar_conexao; repetir com chave separada Tudo é 3D.
- Plugin 1.1.1 consultado: ambas as contas conectadas e com transfer_to_review/read_own_receipts; publishingAvailable=false. Nenhuma mídia transferida ou publicada.

- **ChatGPT direto:** a documentação OpenAI vigente em 23/11/2026 informa que conexões MCP personalizadas com suporte completo (incluindo escrita) no ChatGPT web estão disponíveis em Business e Enterprise/Edu; Pro tem apenas leitura/recuperação. A conta Plus não tem suporte a essa conexão customizada. Portanto, o caminho ChatGPT atual permanece o plugin original 1.1.1 (já confirmado nas duas contas); o MCP 0.1.6 atende n8n, Claude e clientes compatíveis com cabeçalho. Não tentar contornar a política do ChatGPT com chave estática. Uma futura conexão direta via OAuth 2.1 é uma frente separada e ainda exige provedor, metadados protegidos, autorização por conta e refresh token. Fontes: https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt ; https://developers.openai.com/plugins/build/auth .
