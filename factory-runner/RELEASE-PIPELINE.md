# Esteira consolidada — Factory Runner (base M006, incrementos M018/M019; estado RC30)

> **Estado de código — 24/11/2026 / M050:** fonte ativa `mmcromero/factory-runner:desenvolvimento`; versão declarada no manifesto: `0.1.0-rc.30`. RC30 permanece somente em desenvolvimento: não publicada nem instalada. A última instalação comprovada no histórico é RC28 (M044/M045); não inferir atualização posterior. RC19/RC20 são estados históricos, não baseline operacional atual.
>
> O Dockerfile executa bash -n, py_compile e unittest discover na etapa de validação. Para add-on sem image pré-compilada, o Supervisor executa esse build durante a atualização no HA. Não exigir Docker externo, QEMU ou Actions como gate genérico.
>
> O cadastro inicial do proprietário é feito uma única vez pelas Configurações nativas do add-on. A senha temporária é encaminhada no startup pelo helper root-only à autoridade Approval via IPC local e os campos temporários são limpos somente após confirmação durável. O Ingress não cadastra o proprietário: oferece status e consentimento por proposta. O consentimento não redigita a senha; exige sessão/identidade HA verificada, CSRF de uso único e confirmação explícita `PUBLICAR`. O Publisher continua protegido por ativação root-managed, token separado e grant Ed25519; nenhuma destas proteções foi liberada por esta RC.
>
> O restante deste documento preserva o contrato técnico M006. Declarações históricas de ausência de rotas, ingress ou serviços são anteriores ao incremento M019 e estão supersedidas por este estado.

Controle: Issue #2 do Orquestrador; fonte ativa em mmcromero/factory-runner:desenvolvimento.
Avisaqui e Artesão mantêm políticas, versões e receitas independentes.

## Auditoria M050 — RC30 e reconciliação do estado (24/11/2026)

### Baseline e escopo revisados

- Base indicada por M047: `15e6625bbc22f293677062fe299015d65c62fd04`.
- HEAD RC30 indicado por M047: `4daf3fe633f067f8d32c532eae5e5c2a3f7d98d1`.
- Comparação GitHub da base ao HEAD RC30: **17 commits à frente, 0 atrás**.
- Arquivos de código/configuração/documentação do lote: 12 caminhos. As mudanças de runtime concentram-se em `owner_settings_enroll.py`, `owner_approval.py`, `owner_bootstrap.py`, `owner_consent_ui.py`, `ha_ingress_server.py`, `owner_ingress_service.py`, `run.sh`, Dockerfile/config e duas suítes de teste.
- RC30 declara `0.1.0-rc.30` em `config.yaml` e no cabeçalho do changelog.
- M049 acrescentou apenas documentação; não alterou o código da RC30. O HEAD documental atual não deve ser confundido com o HEAD de código RC30.

### Conclusões da revisão estática

1. Cadastro inicial único movido para as Configurações do add-on. O Ingress não expõe mais rotas de cadastro; apresenta orientação para usar Configurações e mantém o consentimento por proposta.
2. `owner_settings_enroll.py` executa como root no startup, valida arquivo/opções, confirmação e identidade HA/Ingress, comunica-se com a autoridade Approval somente pelo socket Unix local e só solicita a limpeza dos campos temporários depois de receber estado de cadastro durável.
3. A autoridade valida a confirmação `CADASTRAR`, compara a senha em tempo constante, cria a chave Ed25519 e o registro em staging privado, faz fsync e confirma o estado antes de devolver sucesso.
4. Se a limpeza das opções pelo Supervisor falhar, o helper retorna falha e o startup fecha; em nova tentativa, o estado já cadastrado evita recriar credenciais e permite repetir a limpeza. Isso é comportamento previsto pelo código, ainda sem ensaio integrado desta candidata.
5. Consentimento de publicação não pede a senha novamente. A jornada mantém identidade/sessão HA, CSRF de uso único e confirmação explícita `PUBLICAR`; o grant e os gates independentes do Publisher permanecem.
6. Dockerfile inclui o helper tanto na etapa de validação quanto na imagem runtime; `run.sh` aguarda Approval IPC antes de processar as opções temporárias e falha fechado se a submissão não puder ser processada.
7. A leitura estática não identificou no diff revisado uma rota de cadastro Ingress remanescente nem um caminho de consentimento que exija redigitação da senha. Isso não equivale a aprovação de segurança nem a execução dos testes.

### Cobertura adicionada/alterada identificada

- `test_factory_runner_owner_settings_enroll.py`: 7 testes novos (cadastro via IPC local, idempotência após cadastro, rejeição de senha inválida, identidade incompleta, campos vazios, limpeza seletiva e falha de limpeza).
- `test_factory_runner_owner_ui_enrollment.py`: 4 testes no estado RC30 (orientação para Configurações, consentimento sem senha, POST HTTP sem senha e rotas antigas de cadastro indisponíveis).
- `test_factory_runner_owner_bootstrap.py`: 10 testes existentes/atualizados na área de provisionamento e identidade.
- `test_factory_runner_owner_ingress_service.py`: 2 testes de serviço Ingress.
- O Dockerfile declara validação com `bash -n`, `py_compile`, `unittest discover` da suíte `test_factory_runner_*.py`, mais rodadas não-root de workspace sync e E2E probe. `validate_offline.py` é a entrada offline que gera logs, exit codes e hashes.

**Contagem acima é inspeção estática dos métodos de teste, não resultado de execução.**

### Limite objetivo de validação nesta etapa

- A árvore atual não contém arquivos em `.github/workflows/`; não existe workflow local de CI a consultar/disparar para esta candidata.
- Check-runs e status associados ao HEAD documental M049 retornaram vazios (`check_runs=[]`, status sem contextos). Isso não representa PASS.
- O conector GitHub disponível nesta sessão permite inspecionar e alterar conteúdo Git, mas não disponibiliza checkout/terminal para executar `validate_offline.py` ou Docker build.
- A instalação comprovada no HA permanece RC28; RC30 não está instalada. A atualização do add-on não foi autorizada nesta etapa e não deve ser usada como atalho para executar testes.
- Portanto, **a suíte RC30, a validação offline completa e o build Docker/ARM64 não foram executados nesta etapa**. Não declarar PASS, GO técnico final ou candidata pronta para publicação.

### Reconciliação documental concluída

O cabeçalho anterior deste manual (M019/RC20/RC19 baseline), o cabeçalho de `CONTINUIDADE.md` e o de `OPERACAO-ESTEIRA.md` estavam obsoletos em relação a M047/M049. Foram atualizados para declarar RC30 como estado de desenvolvimento e RC28 como última instalação comprovada. O histórico anterior foi preservado; as afirmações antigas não são mais apresentadas como estado vigente.

### Resultado M050

**AUDITORIA ESTÁTICA E RECONCILIAÇÃO DOCUMENTAL CONCLUÍDAS. VALIDAÇÃO EXECUTÁVEL PENDENTE.**

Próxima ação para encerrar a Entrega 1: executar `python3 validate_offline.py --output <diretório-novo>` em checkout confiável da fonte e, conforme os resultados, o build Docker da etapa de validação que exercita `bash -n`, `py_compile`, suíte completa e probes não-root. Corrigir falhas, repetir apenas os testes afetados e registrar logs/exit codes/hashes vinculados ao HEAD exato. Até essa evidência, não iniciar a Entrega 2 nem publicar/instalar RC30.

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
- A ativação root-managed é uma trava independente. O consentimento do proprietário é por proposta, com sessão HA verificada, CSRF/nonce de uso único, confirmação explícita `PUBLICAR`, grant Ed25519, TTL e revogação. Não exige redigitação da senha do cadastro.
- A rota `/api/publish` existe, mas o gate de ativação permanece fechado no último estado documentado. A publicação do próprio add-on Factory Runner no catálogo não ativa a publicação de pacotes dos produtos.

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
