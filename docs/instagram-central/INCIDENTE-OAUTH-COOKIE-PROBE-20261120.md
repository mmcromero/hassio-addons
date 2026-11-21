# Incidente Central Instagram — cookie OAuth ausente no probe 0.1.14

**Data do registro:** 20/11/2026  
**Status:** INCIDENTE ABERTO — análise controlada pendente  
**Distribuição em execução:** Central Instagram 0.1.14 no Home Assistant / Raspberry Pi  
**Repositório de distribuição:** `mmcromero/hassio-addons`  
**Repositório de desenvolvimento:** `mmcromero/instagram-automacoes`  
**Controle:** [Issue #1 no repositório de desenvolvimento](https://github.com/mmcromero/instagram-automacoes/issues/1)

## 1. Resumo executivo

A versão 0.1.14 foi publicada no catálogo e o proprietário confirmou a instalação no Raspberry. A tela do Home Assistant mostrou o add-on como **Em execução**. O teste real do navegador, sem Meta, falhou com:

~~~text
OAuth cookie probe failed: OAuth cookie probe missing (host_ok=True, https_ok=True)
~~~

O log comprova que o callback chegou à aplicação com a autoridade pública esperada e com encaminhamento HTTPS reconhecido. O parser não encontrou, no cabeçalho recebido, o cookie com o nome derivado do nonce daquele probe.

**Limite importante:** “cookie probe missing” significa que o parser não encontrou o cookie com o nome esperado. Não prova, sozinho, se o navegador não armazenou o cookie, se não o enviou, se algum intermediário o removeu ou se o nome recebido era diferente.

No mesmo conjunto de logs aparece outra ocorrência:

~~~text
Meta OAuth callback rejected at stage=exchange_code: Meta authorization exchange failed
~~~

Essa mensagem pertence a outra requisição: o caminho de probe retorna antes da lógica de troca de código. A ocorrência em `exchange_code` mostra que, naquela outra callback, a validação do state/cookie e o consumo do state passaram e a falha aconteceu na troca do código com a Meta. Não há timestamp ou identificador de correlação nos trechos fornecidos para ordenar ou associar as duas ocorrências.

## 2. Evidências recebidas

### 2.1 Falha do probe

~~~text
OAuth cookie probe failed: OAuth cookie probe missing (host_ok=True, https_ok=True)
~~~

Leitura confirmada pelo código 0.1.14:

- `host_ok=True`: o valor de `Host` recebido pelo servidor corresponde à autoridade de `meta_oauth_redirect_uri`.
- `https_ok=True`: o servidor recebeu `X-Forwarded-Proto=https`.
- `OAuth cookie probe missing`: não foi encontrado o cookie cujo nome é calculado a partir do nonce do probe.
- O log não registra o cabeçalho Cookie, o nonce, o valor do cookie nem qualquer segredo.

### 2.2 Falha da troca Meta

~~~text
Meta OAuth callback rejected at stage=exchange_code: Meta authorization exchange failed
~~~

O código de `server.py` avança pelos estágios nesta ordem:

1. `parse_callback`: valida query, state e cookie.
2. `consume_state`: consome o state de uso único no SQLite.
3. `exchange_code`: chama a rotina de troca do código com a Meta.

Portanto, a ocorrência em `exchange_code` indica que aquela callback passou pelas duas etapas anteriores. O log não expõe a resposta HTTP original da Meta e não permite identificar a causa específica da rejeição.

### 2.3 Inicialização do contêiner

As mensagens `s6-rc`, `fix-attrs` e permissões de `/run` indicam a inicialização normal dos serviços do contêiner. Não são, por si, a causa do erro de cookie.

## 3. Identificação exata do pacote em execução

- Catálogo: `mmcromero/hassio-addons`.
- PR de publicação: [#67](https://github.com/mmcromero/hassio-addons/pull/67), mesclado.
- Commit de merge: `418ca163c7534273c5d4ed906c835ac424d47d8b`.
- Manifesto: `instagram-central/config.yaml`, versão `0.1.14`.
- Slug: `umdoislab_instagram`.
- Arquitetura declarada: `aarch64`.
- Ingress do add-on: habilitado, porta interna `8099`.
- Tela de informações do Home Assistant consultada: versão atual `0.1.14`, estado `Em execução`.
- HEAD público consultado durante a documentação: `ea5038e08605dc3db365c14837c3c3857f7fbc52`.

Blobs dos arquivos relevantes na distribuição pública:

| Arquivo | Blob SHA |
|---|---|
| `instagram-central/oauth_meta.py` | `0f07af60aa8f6d57ad13a78476eec7b329186d07` |
| `instagram-central/server.py` | `57cc88fb89476bd4b1ab8f65172ee51ea0bae421` |
| `instagram-central/tests/test_http.py` | `65947e1ece194254e9bbbefc9a0ee7de2f5b0ad9` |
| `instagram-central/config.yaml` | `32147c63386061db9b7e32ef3046bc2b085362dc` |

## 4. Fluxo de cookie implementado na 0.1.14

No arquivo `instagram-central/oauth_meta.py`:

1. `start_cookie_probe(cfg)` gera nonce sintético com `secrets.token_urlsafe(32)`.
2. O callback é montado a partir de `meta_oauth_redirect_uri`, acrescentando `?probe=<nonce>`.
3. O nome do cookie é calculado por `_state_cookie_name(nonce)`: prefixo `ig_oauth_state_` mais os primeiros 32 caracteres hexadecimais do SHA-256 do nonce.
4. O valor do cookie é o próprio nonce.
5. Os atributos emitidos são `Max-Age=60; Path=/oauth/meta/callback; Secure; HttpOnly; SameSite=Lax`. Não é definido atributo `Domain`, portanto o cookie é host-only.

No arquivo `instagram-central/server.py`:

- `GET /oauth/meta/start?probe=1` exige a autenticação administrativa existente.
- A resposta envia HTTP 302, `Location` para a callback pública e `Set-Cookie` com o cookie sintético.
- `GET /oauth/meta/callback?probe=...` lê o cabeçalho `Cookie` recebido e chama `check_cookie_probe`.
- O helper procura o nome exato calculado para o nonce.
- O teste não chama a Meta, não grava state OAuth no SQLite e retorna antes da rotina real de OAuth.

## 5. Lacuna de cobertura identificada

O teste em `instagram-central/tests/test_http.py`:

- chama a rota de início;
- lê o valor de `Set-Cookie` da resposta;
- constrói manualmente o cabeçalho `Cookie`;
- injeta esse cabeçalho na requisição de callback.

Esse teste valida a lógica do handler e do parser, mas **não simula o armazenamento e o retorno automático do cookie por um navegador real** depois do 302.

O probe no Raspberry é a primeira evidência real de que o ciclo do navegador não está passando como o teste atual pressupunha. A causa ainda não está localizada.

## 6. Infraestrutura conhecida — sem alteração autorizada

- A aplicação é um add-on Home Assistant com Ingress habilitado para o painel.
- A URL externa usada na integração é `https://romeropi.duckdns.org:8443`.
- O NGINX SSL Proxy encaminha as rotas exatas `/oauth/meta/start` e `/oauth/meta/callback` ao upstream `45c28620-umdoislab-instagram:8099`.
- O fragmento documentado define `Host $http_host` e `X-Forwarded-Proto https`; não contém regra explícita para remover o cabeçalho Cookie.
- O log do probe confirma `host_ok=True` e `https_ok=True` na aplicação.
- O proprietário acessa o Home Assistant por IP local, alias local e endereço externo DuckDNS/Nginx. O teste OAuth/probe deve ser analisado pelo endereço externo configurado, sem presumir que a rota de Ingress e a rota pública externa sejam equivalentes.
- O inventário operacional central registra a criação do fragmento Instagram, o reinício do NGINX e testes de encaminhamento anteriores. Esses registros são evidência histórica fornecida/registrada; não equivalem a uma leitura atual da configuração viva.

Referência: [inventário operacional central do Home Assistant](https://github.com/mmcromero/hassio-addons/blob/main/docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md), seção 7.

## 7. Histórico resumido

| Versão / etapa | Evidência | Interpretação |
|---|---|---|
| 0.1.12 | `OAuth browser state mismatch`, `redirect_authority_match=True`, `forwarded_https=True` | Cookie global foi encontrado, mas o valor não correspondia ao state daquela callback. |
| 0.1.13 | Cookie com nome derivado do state | Correção preventiva para evitar colisões entre autorizações/abas. |
| Probe anterior | PASS em teste automatizado | Não reproduzia o armazenamento real do cookie pelo navegador; o teste injetava o cabeçalho manualmente. |
| 0.1.14 | Probe passou a usar o mesmo nome derivado do state | Alinhou o probe ao mecanismo do OAuth real, mas o teste de navegador falhou com cookie esperado ausente. |
| 0.1.14 — outra callback | Falha em `exchange_code` | Uma callback distinta passou por parse/consumo do state e falhou na troca do código com a Meta. |

## 8. Análise solicitada ao Codex

Solicitar revisão técnica controlada, baseada nos blobs e commits exatos acima, com estes objetivos:

1. Reconstruir a cadeia completa do cookie: resposta 302, `Set-Cookie`, armazenamento do navegador, política de domínio/path/Secure/SameSite e envio à callback.
2. Distinguir as possibilidades: cookie não armazenado; cookie armazenado e não enviado; cookie enviado com nome inesperado; cabeçalho removido/alterado por proxy; erro no nome derivado ou na interpretação do cabeçalho.
3. Revisar o caminho externo NGINX → upstream e a relação com Ingress, sem presumir que o tráfego OAuth externo atravesse o Ingress.
4. Comparar a implementação privada 0.1.13 com o código público efetivamente instalado 0.1.14 e identificar diferenças que precisam voltar à fonte privada.
5. Analisar separadamente a falha `exchange_code`: parâmetros, `redirect_uri`, endpoint/versão Graph, tratamento de status e sanitização de erro. Não fazer chamada real à Meta.
6. Explicar por que os testes existentes passaram apesar da falha no navegador.
7. Propor testes offline reproduzíveis que simulem um navegador real (CookieJar ou Chromium/Playwright) e o 302 completo, com servidor/proxy local e dados sintéticos.
8. Entregar uma matriz de evidências, hipótese principal, hipóteses alternativas, causa ainda não comprovada, correção mínima proposta e testes de regressão.

## 9. Limites obrigatórios da análise

- **Somente leitura da implementação e análise local controlada.**
- Pode executar testes locais/offline com dados sintéticos, stubs e bloqueio de rede externa.
- Não editar arquivos, criar commits de correção, fazer merge ou publicar sem nova autorização.
- Não acessar nem alterar o Raspberry, Home Assistant, Supervisor, NGINX, Ingress, opções ou banco persistente.
- Não fazer login, consentimento, troca de token ou chamada Graph real à Meta.
- Não habilitar webhook, assinatura, recebimento de Direct, respostas automáticas, envio de mensagens, drafts, posts ou stories.
- Não solicitar nem imprimir cookies, nonce, authorization code, state, tokens, app secret, verify token, senha ou cabeçalhos completos.
- Não recomendar ampliar `Path` para `/`, remover `Secure`, enfraquecer `SameSite` ou mudar NGINX/Ingress sem demonstrar a causa e o impacto.
- Preservar arquitetura multi-contas: state isolado por tentativa e credenciais separadas por negócio.
- Não transferir comandos de terminal ao proprietário. A análise deve ser executada pelo ambiente Codex disponível.

## 10. Critério de conclusão da passagem

O Codex deve devolver um relatório com:
- fontes/SHAs exatos revisados;
- fatos confirmados separados de hipóteses;
- explicação independente para o probe e para `exchange_code`;
- testes executados e logs sanitizados;
- causa raiz comprovada ou evidência que ainda falta;
- correção mínima recomendada e impacto multi-contas;
- lista explícita do que **não** foi alterado.

**Estado desta passagem:** DOCUMENTAÇÃO PREPARADA; análise Codex ainda não confirmada. Nenhuma correção de código ou mudança operacional foi executada nesta etapa.
