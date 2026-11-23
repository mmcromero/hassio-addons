# Central Editorial MCP universal

**Versão do pacote:** 0.1.8  
**Slug Home Assistant:** `editorial_mcp_universal`  
**Arquiteturas:** `aarch64`, `amd64`

Adaptador MCP independente para a Central Editorial. Recebe solicitações de clientes MCP e encaminha conteúdo selecionado para revisão. Não publica diretamente em redes sociais.

## Recursos

- Consultar a conexão e a conta associada à chave.
- Consultar recibos próprios por `requestId`.
- Enviar mídia e legenda para revisão, somente após autorização explícita.
- Validar um arquivo temporário do host ChatGPT por MIME, tamanho e SHA-256.
- Enviar arquivo temporário validado para revisão, sem persistir a mídia no adaptador.

## Transporte e autenticação

- Transporte: MCP Streamable HTTP em `/mcp`.
- `X-API-Key`: cabeçalho padrão para clientes como Claude Custom Connector.
- `X-Editorial-Key`: cabeçalho legado, mantido para compatibilidade com clientes existentes.
- Envie exatamente um dos cabeçalhos. Requisições sem chave, com chave inválida, com valores repetidos ou com os dois cabeçalhos são recusadas.
- A chave é emitida pela Central Editorial e validada pela API da Central. A conta é derivada da chave; não é escolhida por argumento da ferramenta.
- Use uma chave e um conector separados para cada conta autorizada. Nunca compartilhe chaves entre contas.
- No Claude Custom Connector, use autenticação **No sign-in** com o cabeçalho padrão `x-api-key` e a chave exclusiva da conta.
- Clientes que usam `X-Editorial-Key` não precisam alterar sua configuração.

## Configuração

| Opção | Uso |
|---|---|
| `central_url` | Origem HTTPS da Central, sem caminho `/panel` |
| `funnel_enabled` | Ativa o Funnel HTTPS no nó Tailscale dedicado deste app; padrão `false` |
| `diagnostics_enabled` | Diagnóstico local sanitizado e opt-in; ausente ou `false` mantém a coleta desativada |

O app usa processo Tailscale, estado e socket próprios. Não modifica o Tailscale principal do Home Assistant. O acesso remoto pelo Funnel exige HTTPS público na porta 443.

## Segurança e limites

- Não oferece ferramenta de publicação, exclusão ou leitura geral do acervo.
- Não aceita chave em URL, query string ou argumento MCP.
- O servidor não armazena a chave editorial.
- A transferência exige autorização explícita e cria somente um rascunho de revisão.
- A ponte de arquivo temporário aceita somente URL assinada de leitura do host ChatGPT, valida hash/MIME/tamanho e trabalha em memória.
- Limite agregado do adaptador: 4 MiB por transferência.
- Não armazene tokens, senhas, `options.json`, estado Tailscale, sessões ou mídia privada no Git.

## Build e testes

O Dockerfile executa `py_compile` e as suítes `test_server`, `test_diagnostics`, `test_host_file_bridge` e `test_funnel_probe` durante o build do Supervisor. Para builds locais, use Python 3 e as mesmas suítes. O build real na arquitetura de destino deve ser confirmado durante a instalação/atualização no Home Assistant.

## Alterações da versão 0.1.8

- Adiciona `icon.png` e `logo.png), usando os mesmos arquivos oficiais dos demais apps do catálogo.
- Atualiza a versão do pacote e do handshake MCP para 0.1.8.
- Preserva autenticação, permissões, ferramentas, opções e compatibilidade da versão 0.1.7.
