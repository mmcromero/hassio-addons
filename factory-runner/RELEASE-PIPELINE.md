# Esteira consolidada — Factory Runner M019 / candidata RC20

> **Estado atual — 24/11/2026:** fonte ativa mmcromero/factory-runner:desenvolvimento; candidata 0.1.0-rc.20. A RC19 é o baseline publicado/instalado. A publicação desta candidata não instala nem reinicia o add-on.
>
> O Dockerfile executa bash -n, py_compile e unittest discover na etapa de validação. Para add-on sem image pré-compilada, o Supervisor executa esse build durante a atualização no HA. Não exigir Docker externo, QEMU ou Actions como gate genérico.
>
> O owner ingress está disponível via Supervisor na porta interna 8099; a página de status é somente leitura por padrão. Consentimento exige opt-in e identidade HA. As rotas de publicação são protegidas por ativação root-managed e grant independente; o gate permanece fechado por padrão. Não confundir a publicação da RC do Runner com publicação de pacotes dos produtos.
>
> O restante deste documento preserva o contrato técnico M006. Declarações históricas de ausência de rotas, ingress ou serviços são anteriores ao incremento M019 e estão supersedidas por este estado.

Controle: Issue #2 do Orquestrador; fonte ativa em mmcromero/factory-runner:desenvolvimento.
Avisaqui e Artesão mantêm políticas, versões e receitas independentes.

## Operação disponível

A API operacional permanece autenticada e em loopback. `/api/prepare` e
`/api/prepare-declarative` usam somente o perfil confiável da imagem, SHA completo,
política aberta, versão coerente e blob aprovado do exportador. Não executam o
exportador no caminho declarativo. `/api/release-plan` continua somente leitura;
`/api/fechar-pacote` continua 403 mesmo com Bearer válido.

O incremento M018/M019 integrou o Publisher isolado e as rotas autenticadas
`/api/publication-preview`, `/api/publication-propose`, `/api/publish` e
`/api/publication-reconcile`. Elas encaminham somente payloads fechados ao
Publisher por IPC Unix. O Publisher valida perfil, recibo, política vigente,
artefato reproduzido, token de escrita separado, ativação root-managed e grant
Ed25519 do proprietário. Sem qualquer gate, a escrita retorna bloqueio; Bearer
operacional não é consentimento. O estado atual permanece sem token de escrita
e sem ativação root-managed.

Console local, sob a conta confiável do Runner e com os diretórios configurados:

```sh
python3 -I /app/release_console.py projects
python3 -I /app/release_console.py status --project avisaqui --source-sha SHA_COMPLETO
python3 -I /app/release_console.py prepare --project avisaqui --source-sha SHA_COMPLETO
python3 -I /app/release_console.py operations
```

O console recusa seleção de comando, URL, caminho e publicação pelo cliente.
Não tem comando publish nem abre porta. Não altera opções/segredos do HA.
Receitas que exigem execução de código externo não são habilitadas pelo console.

## Integridade e repetição

O preparo usa identidade derivada de perfil, SHA de origem e SHA do catálogo,
trava interprocesso e staging exclusivo. Somente um diretório completo e selado
é renomeado para o nome final. Falhas preservam staging `.incomplete-*` para
inspeção; nenhum arquivo/snapshot existente é removido automaticamente.

`RELEASE_RECEIPT.json` registra projeto, pacote, versão, origem/ref/SHA,
destino/ref/SHA esperado, hash do perfil, escopo, arquivos exatos, modos, tamanhos,
SHA-256, momento e resultados de testes. A resposta inclui o digest canônico do
recibo. O mesmo pedido revalida todos os bytes e devolve o mesmo digest sem
criar outra candidata. Symlinks, hardlinks, traversal, `.git`, nomes sensíveis,
manifesto/artefato adulterado e budgets excedidos são recusados.

**Preparo não executa testes do produto.** O recibo nasce `tests=PENDING`; isso
impede publicação no componente de teste. Um resultado PASS externo só tem valor
se o executor legítimo e a autoridade verificarem sua origem e o digest exato.
Diretórios e perfis precisam ser exclusivos da conta confiável: hashes não
substituem isolamento, identidade ou autorização. Não edite recibos reais para
simular PASS. Fixtures modificam somente evidência sintética em diretórios temporários.

## Publisher runtime — integração M018/M019

- O serviço Publisher roda sob UID próprio e recebe requisições do Runner por socket Unix com SO_PEERCRED e ACL.
- Approval, Publisher e Owner UI são iniciados por `env -i` com PATH mínimo antes de `su-exec`; não recebem os tokens do Runner nem variáveis de workspace. O processo Runner/API mantém apenas os tokens necessários; o token de escrita do Publisher continua em arquivo privado separado. Regressão em `tests/test_factory_runner_security.py`.
- O token GitHub de escrita fica em arquivo privado separado do token de leitura dos workspaces; sem ele, o transporte é somente leitura.
- A ativação root-managed é uma trava independente. O consentimento do proprietário é por proposta, com reautenticação, grant Ed25519, TTL, nonce e revogação.
- A rota /api/publish existe, mas o gate de ativação permanece fechado. A publicação do próprio add-on RC20 no catálogo não ativa a publicação de pacotes dos produtos.

## Publicador de referência em laboratório Git local — histórico RC18

`local_publisher.py` é componente de referência para testes, sem rota HTTP e sem
cópia na imagem final HA. Só escreve em Git **bare dentro do seu diretório de
estado privado**, sem remotes, URL, rede ou push. Não publica GitHub. Recusa
checkouts/targets externos. Seu caminho não é um atalho para publicar produtos.

A autoridade é injetada pelo executor confiável, com chaves HMAC independentes
do Bearer; não há emissor de aprovação na API, console ou perfis. Não foi criada
ou instalada chave de produção neste lote. `grant_payload` descreve o contrato,
não assina nem concede autoridade. Provisionamento real de aprovador, chaves,
revogação e executor isolado é dependência externa específica.

O grant assinado vincula autoridade, nonce, Issue, ação, projeto, pacote,
repositórios/refs, origem SHA completo, versão, SHA esperado da distribuição,
perfil, escopo/paths compartilhados e digest do recibo. Expiração máxima de 24h,
revogação e nonce persistente são verificados. Strings owner_approved, WhatsApp,
n8n ou Bearer não substituem assinatura. A mesma operação concluída é idempotente;
nonce com outro binding é replay. Banco SQLite serializa escritores.

`preview` mostra adições/modificações/exclusões contra o SHA fixado e não escreve
objetos/refs. Publicar exige testes PASS vinculados ao SHA e grant independente,
revalida bytes e expiração antes do CAS, cria commit filho do SHA esperado e usa
`git update-ref REF NOVO ANTIGO`. Não há force-push. Somente o prefixo aprovado é
substituído, com preservação de arquivos externos e modos executáveis. Paths
compartilhados precisam constar no perfil e no grant. A publicação GitHub do
próprio Runner neste lote é a exportação revisada pela equipe, não esse simulador.

Intent durável antecede CAS; um retry reconcilia o commit exato se houver queda
entre Git e SQLite. Ref divergente bloqueia; cancelamento/deadline impedem nova
escrita inclusive no retry. Falhas geram eventos sanitizados persistentes, sem
rollback automático da ref: outro escritor pode ter avançado. Revogação/expiração
impedem retry privilegiado; reconciliar manualmente a evidência preservada nesse
caso, sem renovar aprovação por inferência. SQLite/FS precisam fornecer a
durabilidade esperada; não é prometida tolerância a perda física de armazenamento.

## Receitas de produtos

- Avisaqui: política vigente encerrada não é aberta por este código. Declaração
  de exportação aprovada e pin do script continuam obrigatórios. Fixtures Git
  completas cobrem preparo, recibo, autorização e CAS local sem pacote real.
- Artesão: `/api/prepare` continua bloqueado até executor externo autorizado.
  `artesao_isolated_executor.py` mantém a receita oficial e não entra no runtime.
  `artesao_artifacts.py` revalida sua saída com recibo oficial do mesmo SHA,
  checksums completos dos pacotes, hashes dos archives/imagem, proveniência,
  schemas e evidências distintas HA `linux/arm64` e Debian `linux/amd64`.
  O builder chama esse verificador antes de concluir. Ele também pode ser usado
  offline para receber saída do builder. Não extrai archives nem executa comandos.
  Testes com metadados sintéticos não provam build real ou autoridade. Não há
  transporte GitHub para o pacote dual nem liberação automática por grant genérico.

## Validação e próxima homologação

`validate_offline.py --output DIRETORIO_NOVO` executa suítes offline com ambiente
sem credenciais herdadas e preserva logs, exit codes e hashes de código/config.
Na fonte privada inclui a suíte do repositório; no catálogo executa a do add-on.
O Dockerfile executa a suíte completa na etapa de validação e uma segunda rodada
workspace_sync como usuário não root. O runtime não recebe publicador, builder,
verificador dual ou testes. A CA do proxy do laboratório pode ser fornecida por
BuildKit secret `build_ca`; TLS não é desligado e a CA não vai à imagem final.

Publicação de uma RC do Runner no catálogo não habilita pacotes dos produtos.
Autoridade e isolamento reais de publish continuam NO-GO específico; o produto
permanece parcialmente concluído para esse uso. Build/atualização e homologação
no HA dependem do proprietário. Não há Actions, mudanças em servidores, Docker
de produção, reabertura de pacote, instalação ou rotação de segredos neste fluxo.
