> **HISTÓRICO — SEM EFEITO OPERACIONAL:** esta cópia pertence a um estado anterior do Factory Runner e não é a fonte de desenvolvimento nem a esteira atual. Fonte canônica atual: [mmcromero/factory-runner, branch desenvolvimento](https://github.com/mmcromero/factory-runner/tree/desenvolvimento), especialmente [factory-runner-add-on/RELEASE-PIPELINE.md](https://github.com/mmcromero/factory-runner/blob/desenvolvimento/factory-runner-add-on/RELEASE-PIPELINE.md) e [docs/CONTINUIDADE-ATIVA.md](https://github.com/mmcromero/factory-runner/blob/desenvolvimento/docs/CONTINUIDADE-ATIVA.md). Leia a versão atual antes de qualquer decisão; este documento é somente histórico de distribuição.

# Esteira consolidada — Factory Runner RC18

> Diretriz vigente M006/P0 (20/11/2026): operação exclusivamente no Raspberry
> Pi 4/add-on HA existente, sem host externo como dependência. Componentes de
> publicação dormentes e publish=disabled; nenhuma ativação/RC autorizada neste
> lote. Desenho e limites atuais: [M006-RPI-PIPELINE.md](M006-RPI-PIPELINE.md).
> Referências históricas a executor externo não definem a arquitetura vigente.


Controle: Issue #2 do Orquestrador; fonte privada na branch filha do PR #4.
Avisaqui e Artesão mantêm políticas, versões e receitas independentes.

## Operação disponível

A API continua autenticada, em loopback, sem publicador. `/api/prepare` e
`/api/prepare-declarative` usam somente o perfil confiável da imagem, SHA completo,
política aberta, versão coerente e blob aprovado do exportador. Não executam o
exportador no caminho declarativo. `/api/release-plan` continua somente leitura;
`/api/fechar-pacote` continua 403 mesmo com Bearer válido.

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

## Publicador separado — somente laboratório Git local

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
