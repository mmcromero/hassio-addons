# Configuração e operação

## Pré-condições

A pasta de trabalho no MIDIAS2 deve estar com a transferência concluída e nome definitivo escolhido. Não configurar o escopo para a pasta temporária `Nova pasta` enquanto a cópia estiver em andamento.

## Conta técnica FileBrowser

Criar uma conta `catalogo-operador` no FileBrowser Quantum, não administradora, com um único escopo na fonte `Default` apontando para a pasta final da cópia, por exemplo:

```
/MIDIAS2/<pasta-final>
```

Permissões globais:
- admin: false
- api: true
- share: false
- realtime: false

Permissões do único escopo:
- view: true
- download: true
- modify: true
- create: true
- delete: false

O campo `scope` da API é o caminho indexado dentro da fonte, não o caminho físico absoluto do host.

## Token e chave

1. Na conta `catalogo-operador`, abrir Settings → API Management.
2. Criar token de API para essa conta, limitado à permissão global `api`.
3. Guardar o token apenas no campo protegido `filebrowser_api_token` do add-on.
4. Definir `bridge_api_key` como segredo aleatório com pelo menos 32 caracteres. Não inserir valores reais no Git, Issues ou documentação.

## Opções do add-on

- `filebrowser_url`: manter `http://db21ed7f-filebrowser-quantum:8072`. A ponte descobre o prefixo Ingress dinâmico a partir do redirect da raiz; não fixar token nem chamar Supervisor API.
- `filebrowser_api_token`: token API da conta técnica.
- `filebrowser_expected_username`: `catalogo-operador`.
- `filebrowser_expected_scope`: `/MIDIAS2/<pasta-final>`.
- `filebrowser_source`: `default`.
- `bridge_api_key`: segredo exclusivo da ponte.
- `audit_log`: `/data/audit.jsonl`.
- `port`: `8090`.

## Modo seguro antes da configuração

Com token, escopo ou chave vazios:
- `GET /health` retorna `configured=false`.
- Todas as rotas operacionais retornam HTTP 503.
- O serviço não consulta nem altera o FileBrowser.

## Acesso interno

A porta 8090/tcp não é publicada no host. O agente chama o add-on pelo proxy interno Home Assistant MCP, especificando a porta 8090. As rotas operacionais exigem o cabeçalho `X-Bridge-Key`.

## Rotas

- `GET /health`: saúde e estado de configuração.
- `GET /v1/items?path=...`: lista arquivos e pastas.
- `GET /v1/metadata?path=...`: metadados.
- `GET /v1/preview?path=...&size=small|large`: preview JPEG/PNG, limite 5 MiB.
- `POST /v1/folders`: criar pasta; dry-run por padrão; aplicar com `apply=true` e `confirmation=CRIAR_PASTA`.
- `POST /v1/move`: mover arquivo; dry-run por padrão; aplicar com `apply=true` e `confirmation=MOVER`.
- `POST /v1/quarantine`: mover arquivo para `_QUARENTENA/<operation-id>/`; dry-run por padrão; aplicar com `apply=true` e `confirmation=QUARENTENA`.

Todas as rotas operacionais exigem `X-Bridge-Key`.

## Limites e garantias

- Esta versão move apenas arquivos individuais; não move diretórios.
- Não existe endpoint de delete, overwrite ou copy.
- Antes e depois de cada movimentação, calcula SHA-256 por streaming (1 MiB por bloco). Se divergir, registra falha e mantém o item no destino para inspeção; não faz rollback automático.
- Toda escrita registra intenção (`started`) antes de executar e resultado (`success`/`failed`) depois, em JSONL com permissão 0600.
- O container não monta `/media` nem qualquer pasta do host.
- O HD original do Windows nunca é acessado.
