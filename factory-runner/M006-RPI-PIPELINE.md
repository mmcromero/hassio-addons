# M006 — Esteira determinística no Raspberry Pi 4 existente

Decisão vigente: Issue #2, comentário 7035036351 e P0 7034806094. Factory Runner
opera exclusivamente como add-on HA no Pi existente. Outro computador, Forja,
VM ou nuvem não é dependência do produto. Codex/Docker neste lote são laboratório
de desenvolvimento; nenhum equipamento/serviço foi provisionado para operação.

Este lote não altera versão RC18, não publica candidata, não instala no HA e não
ativa publicação. `run.sh` permanece intacto. A imagem contém componentes
**dormentes** e usuários separados; não inicia emissor, UI de consentimento ou
publicador. `/api/publication-status` é autenticado e somente leitura. Não há
`/api/publish`; `/api/fechar-pacote` continua bloqueado por Bearer.

## Fluxo implementado e fronteira de confiança

1. O preparo declarativo existente lê somente Git blobs por SHA, usando receita
   e perfil da imagem confiável, política, versão, staging atômico e receipt.
2. `ArtifactContract` revalida o receipt, consulta **também a política vigente** na
   branch de origem (um freeze não congela consentimento), verifica elegibilidade
   e reproduz a receita inteira em staging próprio a partir dos objetos Git. Pin
   do exportador, evidências de versão e contrato CI são repetidos sem executar
   scripts ou workflows. Compara arquivos, modos, tamanhos e SHA-256. Adulterar
   artefato e receipt coerentemente não muda o SHA de origem aprovado.
3. `GitHubBytesTransport.plan` lê HEAD/commit/árvore completa, rejeita truncamento,
   recompõe o hash da árvore independentemente e gera diff exato. O prefixo é
   substituído e obsoletos desse prefixo aparecem como exclusões; paths externos
   ficam preservados. Shared paths exigem allowlist do perfil. Workflow idêntico
   pode permanecer; qualquer mudança efetiva em `.github/` é recusada neste lote.
4. `PublicationWorkflow.propose` entrega ao emissor a proposta imutável, preview
   completo e receipt. Emissor confere seus digests e armazena os três. O browser
   não escolhe comandos, paths, chaves, repo/ref, conteúdo ou descrição do preview.
5. O proprietário revê destino, versão, Issue, SHA completo, HEAD esperado,
   arquivos/modos/exclusões, hashes e testes; reautentica com **senha independente**
   e digita PUBLICAR. `ApprovalIssuer` usa scrypt, salt, throttle persistente e
   transação auditada para emitir um grant Ed25519 de até cinco minutos. A chave
   privada pertence só ao emissor; Bearer operacional nunca emite grants.
6. `GrantVerifier` recebe apenas bytes imutáveis da chave pública com fingerprint
   pinado, identidade esperada e acesso Unix ao status assinado. Verifica schema,
   domínio, identidade, todos os bindings, TTL, nonce e consentimento. Cada status
   tem challenge aleatório, digest do grant, purpose e tempo; ausência/replay/erro
   do serviço de revogação bloqueia escrita.
7. Em cada envio privilegiado, o workflow consulta novamente o grant. Só transmite
   bytes congelados em memória, derivados do artefato reproduzido. Token GitHub
   fica somente no transporte confiável, nunca em subprocesso Git/OpenSSL, argv,
   ambiente, workspaces, receipt, UI ou logs.
8. Cria blobs, árvore e commit por API GitHub com hashes esperados, modos e parent
   exatos; antes de mudar ref baixa todos os blobs de artefato e verifica SHA-256
   e OID Git. Uma árvore canônica completa prova preservação de arquivos externos.
   Usa **GraphQL updateRefs com beforeOid, afterOid e force:false** para CAS atômico,
   em vez de presumir que PATCH REST force:false compare um SHA esperado.
9. Confere remotamente HEAD, parent, árvore, arquivos, modos e SHA-256 após CAS.
   Retorna estado explícito `PUBLISHED_VERIFIED_PENDING_HOMOLOGATION`. Não instala,
   executa scripts de produto, faz merge privado, force-push ou dispara Actions.

`workflow_for_project` monta o contrato a partir de perfis e workspaces aprovados
do próprio add-on. O cliente não fornece configuração de autoridade ou destino.
Receipts com testes PENDING continuam sem publicação: este caminho não fabrica
PASS nem executa testes dos produtos no HA. Avisaqui fechado continua bloqueado.
Artesão com build ARM64/AMD64 permanece dependência **da sua receita/evidência
legítima**, sem exigir outra máquina como arquitetura do Runner.

## Emissor, verificador e segredos no mesmo Pi

Contas de serviço previstas na imagem, sem login:

| Conta | Material e atribuição |
| --- | --- |
| `runner` | API de operação/preparo; não lê chave privada, senha do proprietário ou token de publicação; não acessa socket de consentimento |
| `publisher` | Contrato/perfil públicos confiáveis, entrada de artefatos/objetos Git somente leitura, chave pública pinada, ledger privado e token GitHub mínimo; pode propor e consultar status, não consentir/revogar |
| `approval` | Chave privada Ed25519 e registro scrypt do proprietário; ledger/auditoria próprios; não lê token GitHub |
| `owner_ui` | UI de reautenticação por ato via ingress verificado e IPC; não lê chave privada ou token GitHub |

Diretórios de segredos/ledgers são exclusivos 0700, arquivos 0600, sem aliases;
chave pública/perfis são administrados fora dos workspaces, sem escrita pelo
preparador. IPC usa socket Unix 0660 em diretório 2750 do emissor/grupo
`consent_clients`; grupo inclui publisher/owner_ui, exclui runner. Servidor e
cliente verificam **SO_PEERCRED do kernel**; ACL de ações é por UID confiável.
IDs/caminhos/ACL não vêm de headers, JSON do browser ou dados de projeto.

Na ativação futura, provisionamento administrativo no próprio add-on precisa dar
ao publisher leitura dos inputs/snapshots aprovados, sem escrita neles, e manter
credenciais em subárvores separadas. Os workspaces RC18 existentes continuam com
suas permissões; este lote não os altera por inferência. O probe em container usa
somente dados sintéticos para testar permissões reais entre as quatro contas.
Nenhuma chave, senha ou token de produção é gerado/enrolado por estes módulos.

## UX segura proposta e exercitada offline

`OwnerConsentUI` é aplicação dormente, sem listener ou rota no HA atual. Adapter
HA ingress futuro deve verificar sessão de proprietário e origem TLS por mecanismo
confiável do próprio HA; **não** aceitar `Authorization: Bearer` da API ou headers
encaminhados por cliente como prova. Seu callback recebe contexto autenticado do
adapter, nunca um boolean do browser. A aceitação real desse adapter está pendente.

A aplicação gera sessão/CSRF aleatórios de dois minutos; a mesma sessão só pode
ser consumida uma vez. POST exige owner igual, Origin exata, CSRF, senha independente
e PUBLICAR. Página escapa todo conteúdo, usa no-store/CSP e não mostra comandos
ou campos arbitrários de testes. O adapter precisa aplicar cookie Secure/HttpOnly/
SameSite=Strict no path real do ingress e transportar formulário só por TLS.
Não há chave do emissor nem credencial GitHub na UI. Não há dependência de host
adicional: o acesso é pelo frontend HA que o proprietário já usa.

## Nonce, revogação, concorrência e recuperação

Um ledger SQLite único por publisher, private file, synchronous FULL, transações
IMMEDIATE e lock por instância serializam threads/processos. Intent durável com
commit/tree/diff/hashes esperados precede qualquer escrita remota. Nonce vinculado
a outro binding não é aceito. Objetos Git são content-addressed; retry pré-CAS
reenvia os mesmos objetos e nunca duplica um commit/ref.

O emissor serializa consentimento/revogação/reserva. **Reserva assinada é o ponto
de linearização** imediatamente anterior ao CAS: revogar antes bloqueia a escrita;
após reservar, a UI deve informar `publication_reserved_reconcile_required`, nunca
anunciar revogação bem-sucedida. Resultado desconhecido exige reconciliação. Não
prometemos cancelar atomicamente uma requisição GitHub já autorizada em trânsito.
Deadline/cancelamento impedem novas escritas antes da reserva e antes de etapas;
perda de rede não dispara rollback da ref nem renovação automática de grant.

`reconcile(nonce)` é separado e **somente GET remoto**, baseado em intent previamente
autorizado e protegido. Pode comprovar CAS já concluído após sync da distribuição,
expiração ou revogação, sem grant novo nem política de preparação antiga ainda
aberta. HEAD igual ao esperado confirma ref inalterada; HEAD diferente do commit
intencionado e do esperado bloqueia e exige análise. Não presume sucesso nem
sobrescreve outro escritor. Nova tentativa de escrita sempre requer política
atual e grant válido. Mudança de destino/perfil impede reconciliação automática.

## Transporte, limites e aceite

HTTPS GitHub fixo, TLS verificado, sem redirect/forward de Authorization; endpoints
construídos de repo/ref confiáveis. API tree é completa ou bloqueada; budget de
resposta/arquivos, timeout por chamada e deadline de operação limitam recursos.
Escopo de path é verificação da aplicação, **não uma permissão do token**. Futuro
token deve limitar conta/repositório/permissão; credencial de leitura de workspace
não vira credencial de publicação. Permissões de branch continuam sendo do GitHub.

Componentes, chaves públicas/perfis e imagem são parte da base confiável; contas
administrativas/serviço publisher comprometidas continuam risco. Hash não substitui
consentimento, nem metadado sintético comprova build. Nenhum dado de repositório
é importado como Python/JS/shell ou usado como comando. Não se dá Docker socket
ou privilégio do host a worker; Bubblewrap/Landlock não são contornados.

**Implementado / testado offline** não significa instalado ou homologado. Faltam
aceite formal de Segurança/Tech Lead, enrollment legítimo no Pi, adapter ingress
real, credential/ACL mínimos e ensaio de mutações em repositório de teste sob
permissão específica. Introspecção/read da API real confirmou o contrato e uma
peculiaridade de mensagens Git (API omite LF final), mas não homologa mutações.
Somente depois cabe decisão específica de ativação/uma candidata consolidada.
Não é pedido outro computador nem nova instalação a cada teste.
