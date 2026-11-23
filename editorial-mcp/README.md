# Central Editorial MCP universal

**Versão do pacote:** 0.1.10 (publicada no catálogo Home Assistant; instalação pendente)  
**Slug Home Assistant:** `editorial_mcp_universal`  
**Arquiteturas:** `aarch64`, `amd64`

Adaptador MCP independente para a Central Editorial. Recebe solicitações de clientes MCP e encaminha conteúdo selecionado para revisão. Não publica diretamente em redes sociais.

## Recursos

- Consultar a conexão e a conta associada à chave.
- Consultar recibos próprios por `requestId`.
- Enviar mídia e legenda para revisão, somente após autorização explícita.
- Validar um arquivo temporário do host ChatGPT por MIME, tamanho e SHA-256.
- Enviar arquivo temporário validado para revisão, sem persistir a mídia no adaptador.\n- Receptor PWA Android: compartilhar imagem de ChatGPT, Claude ou outro app pela folha Compartilhar do Android; selecionar conta e formato e enviar para revisão.

## Transporte e autenticação

- Transporte: MCP Streamable HTTP em `/mcp`.
- `X-API-Key`: cabeçalho padrão para clientes como Claude Custom Connector.
- `X-Editorial-Key`: cabeçalho legado, mantido para compatibilidade com clientes existentes.
- Envie exatamente um dos cabeçalhos. Requisições sem chave, com chave inválida, com valores repetidos ou com os dois cabeçalhos são recusadas.
- A chave `cei1` legada continua vinculada a uma conta. A nova chave `cei2` recebe escopo definido na Central; o MCP lista somente as contas autorizadas e exige destino explícito quando houver mais de uma.
- Um único conector pode usar a chave `cei2` multi-conta. Escopo, destino e recibos são validados pela Central; as chaves `cei1` permanecem isoladas.
- No Claude Custom Connector, use autenticação **No sign-in** com o cabeçalho padrão `x-api-key` e a chave `cei2` emitida pela Central.
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


## Conexão multi-conta (0.1.9)

Requer Central Instagram 0.1.39. Crie uma conexão na aba Ferramentas e guarde a chave cei2 somente no cliente (X-API-Key ou X-Editorial-Key). O escopo de proprietário inclui novas contas operacionais autorizadas; o delegado recebe somente a seleção explícita. O painel ainda tem sessão administrativa compartilhada, não identidade individual. Chaves cei1 continuam restritas. `listar_contas` retorna destinos autorizados; informe `conta` por nome, @ ou ID e confirme o destino quando houver várias opções.

Para Drive, configure identidade técnica exclusiva de leitura, sem delegação de domínio, com acesso apenas à pasta privada autorizada. Vincule uma raiz exclusiva à conexão; os arquivos ficam em subpastas filhas diretas cujo nome é o ID canônico da conta. `validar_arquivo_drive` confirma o tamanho e SHA-256 sem armazenar; `enviar_arquivo_drive_para_revisao` exige autorização explícita, limite agregado de 4 MiB e requestId estável. Somente revisão. Não use links públicos, caminhos locais ou tokens em argumentos. Nenhuma exclusão automática. O acesso real ainda precisa ser homologado.


## Receptor de compartilhamento Android — 0.1.10

- Abra `https://<hostname-publico-do-Funnel>/share` no Chrome Android e instale o app ou adicione-o à tela inicial.
- Depois, em ChatGPT ou Claude, use o recurso de compartilhar/salvar a imagem e escolha **Central Editorial** na folha de compartilhamento do Android. O suporte depende de o aplicativo de origem expor o arquivo ao compartilhamento do sistema.
- A PWA recebe JPEG/PNG/MP4 via Web Share Target, mantém o arquivo localmente no IndexedDB e mostra a fila para conferência.
- Informe a chave multi-conta `cei2`, carregue as contas, escolha explicitamente Umdoislab ou Tudo é 3D e toque em **Enviar para revisão**.
- A chave fica somente na memória da página; não é gravada em localStorage/sessionStorage. A arquivos compartilhados são removidos na próxima abertura do app após 24 horas. O envio exige ação explícita e usa a API de rascunhos existente; nunca publica.
- Limite atual: 4 MiB agregados por transferência. A PWA não depende de URL temporária do host ChatGPT nem de Google Drive.
- Rotas novas: `GET /share`, `POST /share-api/accounts`, `POST /share-api/transfer`. A API exige chave `cei2` e valida o destino na Central. As rotas MCP existentes permanecem disponíveis.

**Estado da candidata:** código e testes adicionados na branch `feature/editorial-share-pwa-chatgpt-claude`; ainda não executados em build real do Supervisor nem testados com compartilhamento real no Android. Não declarar homologado até executar esses gates.
