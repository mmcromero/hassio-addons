# FACTORY-RUNNER — RC6: teste interno de ponta a ponta

**Controle:** [Issue #2](https://github.com/mmcromero/orquestrador-projetos-base/issues/2) • **Estado:** CANDIDATA DE DESENVOLVIMENTO; **NÃO PUBLICADA / NÃO INSTALADA / NÃO HOMOLOGADA NO HOME ASSISTANT** • 19/11/2026 (BRT)

## Contexto e objetivo
A RC5 foi confirmada no HA pelo Supervisor: `slug: 45c28620_fabrica_software`, `version: 0.1.0-rc.5`, `state: started`; o log continha `[DECLARATIVE] PASS` e `[API] READY`. Isso comprova **preparação sintética de Git blobs no HA**, mas o log dizia `project workspaces NOT tested`. A API da RC5 atende `127.0.0.1:9876` dentro do contêiner; o shell `core-ssh` do Home Assistant não compartilha esse loopback. Não abrir portas nem exigir acesso ao Docker socket ou aos diretórios reais para simular o teste.

## Solução RC6
O novo `factory_e2e_probe.py` executa uma única verificação de início a fim no **próprio contêiner do Factory Runner**, antes da API principal:
1. Roda como **runner não-root**, em processo com ambiente esvaziado via `env -i`; não recebe `RUNNER_AUTH_TOKEN` verdadeiro.
2. Cria repositórios `source` e `distribution` **sintéticos** em diretório privado e temporário em `/tmp`, com refs Git, pacote aberto, política/versão e proveniência fictícias. Nenhuma credencial ou clonagem remota.
3. Usa apenas o código Python confiável da imagem; o `scripts/export.py` sintético contém erro deliberado se fosse executado.
4. Inicia `ThreadingHTTPServer` com o **Handler real da API** em `127.0.0.1:0` (porta efêmera interna), token aleatório criado apenas para o teste, sem interface externa ou ingress.
5. Verifica negação sem Bearer (`401`), preflight efetivo (`200` elegível), preparação declarativa via rota **padrão** `POST /api/prepare` (`200`, `PREPARED_NOT_PUBLISHED`, cinco blobs), hashes e manifesto; compara ref/status dos repositórios antes/depois e preservação de sentinela no destino.
6. Verifica que SHA ausente não prepara (`503`), operação `/api/fechar-pacote` continua proibida (`403`), e política de pacote fechado resulta em `409 NO_OPEN_PACKAGE` após alteração intencional **apenas do repositório sintético**. Audita estados sem vazar o token.
7. Encerra servidor de teste, apaga artefatos temporários, restaura variáveis de processo, limita execução a 75 segundos e emite `[E2E] PASS: ... NO real workspaces` ou `[E2E] BLOCKED: ...`. Falha de teste não habilita fallback inseguro e não bloqueia o diagnóstico da API por si só.

**Limite:** um `PASS` no HA para este teste comprovará o **caminho completo e seguro com workspaces locais sintéticos**, mas **não** provisionamento de checkouts privados reais, acesso a políticas de projeto fechadas, publicação de pacotes ou isolamento de código gerado por IA.

## Evidências executadas em laboratório
- `factory_e2e_probe.py` com Python `-I`, ambiente limpo e usuário Linux `nobody` (UID não-root): **PASS, exit 0**, cinco blobs sintéticos, recusa de publicação/pacote fechado, sem credenciais de projeto.
- **4/4 testes novos PASS**: fluxo HTTP e política; proibição de UID 0; subprocessos Git sem tokens/remotos; bind somente `127.0.0.1:0`.
- **56/56 testes locais PASS** no conjunto de regressões executado com reproduções idênticas por SHA Git dos módulos relevantes (`server.py`, `rc_fastlane.py`, `declarative_export.py`, probe E2E). Este total é do laboratório e **não** a suíte integral do checkout no Docker.
- Hash Git do novo código `factory_e2e_probe.py`: `ece0f6e348035de4e99ba543149683d589ebdf7c`; novo teste `test_factory_runner_e2e_probe.py`: `4f4aae54b87b4e491a438521873d35ed252a845e`. Iguais na origem privada e na branch pública.
- Falha encontrada em revisão do Dockerfile: o teste novo estava no estágio `validation`, mas não na imagem final. **Corrigido antes de publicar**: `COPY --from=validation` e `RUN test -r /app/factory_e2e_probe.py` agora ambos presentes.
- `run.sh` executa o probe com `env -i`, `su-exec runner` e `python3 -I -u`, antes de iniciar a API regular.

## Limites restantes
- **Não** foi feito Docker build, Action, QEMU, merge, publicação na `main` ou instalação no Raspberry nesta tarefa.
- Para validar no HA: publicar **RC6** apenas após autorização própria e conferir `config.yaml` + commit; atualizar o add-on via Supervisor; observar `[E2E] PASS/BLOCKED` no bloco atual dos logs. `[DECLARATIVE] PASS` da RC5 **não substitui** o novo teste.
- A RC6 não libera `/api/fechar-pacote`, `/api/corrigir-issue`, scripts externos/IA ou Git push. Mantém a RC5 instalada até escolha do proprietário.
- Se ocorrer `[E2E] BLOCKED`, registrar a razão curta e corrigir apenas o componente; não alterar permissões AppArmor/host por tentativa.

**Responsáveis:** desenvolvimento do Factory Runner implementa e revisa; Segurança avalia limites; operador valida instalação física. Continuar na Issue #2, sem issue duplicada.
