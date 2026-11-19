# Factory Runner — Operação e segurança

## Limites atuais

A versão candidata 0.1.0-rc.2 oferece **pré-verificação somente leitura e preparação local**. Não tem
capacidade autorizada de desenvolver ou publicar, mesmo com Bearer válido.

O serviço exige `runner_auth_token` nas opções do Home Assistant com
um segredo de alta entropia (mínimo 32 caracteres). Não usar valores de exemplo
ou segredos versionados. O token autentica o cliente, mas **não autoriza**
operações em repositórios. Os fluxos n8n existentes não devem ser apontados
para este candidato sem homologação da mudança.

A porta `9876/tcp` não é publicada no host por padrão e o servidor usa
`127.0.0.1`. Não abrir a porta nem mudar o bind sem projeto de rede,
autorização e TLS/autenticação revisados. Nenhum novo valor deve ser escrito
em arquivos versionados para prover credenciais.

## Pré-verificação por projeto

As rotas autenticadas `GET /api/projects` e `POST /api/preflight` exigem perfis versionados em `/app/projects/` e checkouts privados previamente preparados em `/data/factory-runner/workspaces/<id>/source` e `distribution`. Não há clonagem automática nem credenciais Git no add-on. Sem workspace, retorna `503 workspace_or_export_unavailable`.

O preflight não fecha RC nem grava branch; prepare cria somente checkout/branch
local descartável e relatório. Nenhum deles publica na loja. Consulte [OPERACAO-ESTEIRA.md](OPERACAO-ESTEIRA.md).

## Persistência e backup

O log de auditoria fica em `/data/factory-runner/audit.jsonl`.
O `/data` é o volume de dados persistente do add-on.
A API preserva os checkouts provisionados e escreve somente preparações locais
e auditoria. No sandbox, origem e metadados Git são somente leitura.
A disponibilidade real do volume e permissões dependem da instalação física.

## Testes locais (sem GitHub Actions)

```sh
python3 -m unittest discover -s factory-runner/tests -p 'test_factory_runner_*.py' -v
python3 -m py_compile factory-runner/*.py
sh -n factory-runner/run.sh
python3 .github/scripts/validate-addon-registry.py --addon factory-runner
```

O teste de registro exige `PyYAML` no ambiente local. Um build isolado
pode ser testado com `docker build --platform linux/arm64 factory-runner/`
após verificar os recursos disponíveis, sem fazer push nem instalar.

## Esteira e governança

- O workflow já existente `.github/workflows/validate-addons.yml` foi
  estendido com opção manual `factory-runner`; builds ARM64 não rodam no PR.
- O `main` da loja permanece inalterado até publicação especificamente
  autorizada. Apenas a `main` alimenta a loja instalada no HA.
- A política do Orquestrador exige testes, autorização canônica de Issue,
  branch, SHA e operação e proíbe force-push.
- Execuções de teste/build/smoke e seus SHAs ficam no PR #43, sem substituir
  checks remotos não executados.
- Bubblewrap obrigatório, namespaces explícitos, UID não-root e RLIMIT foram
  implementados; disponibilidade e consumo reais têm prova separada dos mocks.
  Sem namespace, prepare retorna 503 com auditoria e CLI retorna erro controlado.
- Portões operacionais: prova positiva de isolamento no ambiente autorizado,
  cgroups agregados/quota rígida, provisão de checkouts, homologação no destino
  e rotação coordenada dos segredos antigos. RLIMIT não substitui cgroup/quota.

**Sem autorização de deploy, merge ou Actions nesta entrega.** Testes em
`factory-runner/tests/` executam no estágio Docker `validation` e não são
copiados para a imagem de runtime.
