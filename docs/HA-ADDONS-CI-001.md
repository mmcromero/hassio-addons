# HA-ADDONS-CI-001 — Contrato de build e publicação de add-ons Home Assistant

**Estado:** proposta técnica aplicada em branch; homologação e adoção universal pendentes.
**Responsável:** Tech Lead / Infraestrutura / Governança. **Regra:** não executar build, CI, merge, instalação ou publicação por simples edição deste documento.

## Inventário verificado em 16/11/2026
| Aplicativo | Loja/repositório confirmado | Configuração confirmada | Build/CI no catálogo compartilhado |
|---|---|---|---|
| Avisaqui / Pager Virtual | mmcromero/hassio-addons | pager-virtual/config.yaml | Sim |
| Evolution API | mmcromero/hassio-addons | evolution-api/config.yaml | Sim |
| Artesão Digital | mmcromero/fabricacao-e-orcamentos-ha | repository.yaml | Não comprovado no hassio-addons |
| Fábrica de Ideias Kanban | mmcromero/fabrica-de-ideias-kanban | repository.yaml | Não comprovado no hassio-addons |
| Portal WhatsApp | A identificar | Não verificada | Não verificado |

**Atenção:** repository.yaml confirma a definição de uma loja, não a instalação, publicação de versão ou localização de cada pasta de add-on. Não migrar projetos automaticamente.

## Regras obrigatórias para novo aplicativo ou nova versão
1. Identificar **repositório de origem**, **repositório de distribuição**, **diretório do add-on**, **slug**, **versão**, **arquiteturas**, **responsável**, **workflow** e **comando de build**. Se faltar algum dado, registrar NÃO VERIFICADO e bloquear apenas a publicação, não o desenvolvimento.
2. Alteração de um add-on não deve compilar outros sem dependência compartilhada comprovada. Testes de sintaxe/segurança do catálogo podem rodar em todo PR; builds pesados são específicos por add-on.
3. Durante desenvolvimento: testes locais e dirigidos, com SHA e resultado. Antes da publicação: testes de integração, build da arquitetura de destino, verificação de imagem/manifesto, segurança, integridade e autorização explícita.
4. Builds ARM64 em emulação QEMU: somente sob gate autorizado, com timeout e observação de duração; anomalias exigem cancelamento e diagnóstico, não reruns automáticos.
5. Concurrency cancela somente execuções obsoletas de PR; não cancela release ou publicação. Não usar labels/tags sem validar os gatilhos reais. Verificar required checks antes de editar filtros de paths.
6. Respeitar franquia gratuita. Nunca habilitar cobrança, runners pagos, contorno de proteção, CI falso ou aprovação presumida.
7. Exportação para loja compartilhada: conferir proveniência, hashes, versão, changelog e escopo; não substituir código-fonte por cópia sem rastreabilidade.
8. Todo novo workflow deve passar por revisão de gatilhos, paths, matrix, timeout, permissões mínimas, artefatos, cache, concorrência, logs sanitizados e impacto financeiro antes de integrar.
9. Se Actions estiver indisponível, continuar desenvolvimento e revisão local, marcar CI PENDENTE e bloquear merge/publicação que exija o check. Escalonar para Tech Lead com SHA, log sanitizado e motivo.
10. **Ao criar novo projeto:** copiar este contrato para a documentação operacional do projeto, preencher o cadastro abaixo e adaptar os testes; não presumir que a loja central seja obrigatória.

## Cadastro de novo add-on (preenchimento obrigatório)
- Produto / responsável:
- Origem (repositório + branch + SHA):
- Distribuição (repositório + diretório):
- Slug / versão / arquiteturas:
- Workflow rápido / testes locais:
- Workflow build final / acionamento autorizado:
- Timeout baseado em histórico (ou provisório identificado):
- Dependências compartilhadas:
- Checks obrigatórios / aprovação:
- Evidência de proveniência e integridade:

## Estado do Avisaqui
A branch `release/avisaqui-rc-distribuicao-002` do `mmcromero/hassio-addons` contém contenção inicial em `.github/workflows/validate-addons.yml`: build ARM64 manual com escolha explícita de Avisaqui ou Evolution, limites de execução e cancelamento de PRs substituíveis. **Ainda não homologada nem aplicada à main.** A arquitetura definitiva deve evoluir para registro de aplicativos, sem hardcode de apenas dois nomes.

## Implementação de cadastro — 16/11/2026
- Fonte de verdade no catálogo: `.github/addon-registry.json`, com IDs, diretórios, slugs, arquiteturas e job de build.
- Verificador: `.github/scripts/validate-addon-registry.py`. Compara cadastro com manifests reais e exige que **todo diretório com config.yaml** tenha cadastro. Valida seleção manual e falha quando ID não cadastrado.
- Workflow `.github/workflows/validate-addons.yml`: valida cadastro após instalação de PyYAML e antes de builds ARM64; a seleção manual atual continua restrita a `pager-virtual` e `evolution-api`. Para um terceiro add-on, cadastrar e adaptar job/input em revisão própria: **não existe ainda geração automática de jobs para novos aplicativos**.
- Repositórios consultados no inventário: `mmcromero/hassio-addons`, `mmcromero/fabricacao-e-orcamentos-ha`, `mmcromero/fabrica-de-ideias-kanban`, `mmcromero/fabricacao_e_orcamentos`, além de pesquisa de código em repositórios acessíveis. **Portal WhatsApp**: origem/distribuição não identificadas com evidência suficiente. Não confundir com Evolution API, que usa WhatsApp.
- A adoção em lojas independentes depende de PRs/branches próprios, testes e revisão de compatibilidade. Nenhuma migração foi autorizada.
- **Evidência pendente:** execução local do verificador sobre checkout completo e validação de YAML; CI e builds finais não executados. Sem homologação nem publicação.

## Revisão de integração e riscos — 16/11/2026

**Artesão Digital identificado com evidência direta:** fonte `mmcromero/fabricacao_e_orcamentos/apps/umdoislab/pilot/config.yaml`; workflow `.github/workflows/artesao-publicar-ha.yml`; pacote de destino `mmcromero/fabricacao-e-orcamentos-ha/apps/artesaos-piloto`; slug `artesaos_piloto` segundo script `scripts/prepare-ha-aarch64.py`. O workflow aceita `workflow_call`, `workflow_dispatch` e push em `publish/ha/**`; executa QEMU ARM64, timeout 120 min, e faz commit/push na main da loja após validações. **Não disparar como teste**. O histórico `pix-qr-ha.yml` também publica na main por push de branch específica, com versão fixa; manter inativo, não usar como fluxo genérico.

**Kanban confirmado:** loja `mmcromero/fabrica-de-ideias-kanban`, add-on `kanban/config.yaml`, slug `kanban`; `validar.yml` executa testes e Docker build em PR/push (timeout 20 min); `gerar-pacote.yml` é manual, exige SHA+versão, gera ZIP e hashes (timeout 15 min), sem publicação automática. Não substituir sem revisão.

**Portal WhatsApp:** buscas de código por portal/whatsapp e nomes de diretórios conhecidos não produziram prova de add-on separado. Status NÃO IDENTIFICADO; nenhuma migração ou cadastro inventado.

**Riscos dos required checks e do validador:**
1. O job `syntax` existente permanece com o mesmo ID, mas passou a depender do novo cadastro. Se existir um terceiro diretório `config.yaml` não cadastrado, o check passará a falhar; é comportamento seguro, mas exige inventário completo da árvore antes de merge.
2. A escolha manual do `workflow_dispatch` permanece hardcoded em dois IDs. O cadastro JSON **não** cria jobs automaticamente. Novo add-on requer revisão de workflow e check de build apropriado.
3. `avisaqui-governance.yml` só roda em PR quando caminhos de Avisaqui mudam. Um PR que altere apenas o validador/registro pode não gerar esse check; se ele for obrigatório, verificar regras de proteção antes de integrar. Não mudar filtros para forçar bypass.
4. Builds ARM64 agora são pulados em PRs; caso algum deles seja required check, pode bloquear a integração. Confirmar branch protection/rulesets e contexto real de checks antes do merge. O conector disponível não demonstrou leitura dessas regras.
5. O `syntax` instala PyYAML dinamicamente; falhas de dependência/rede ou timeout de 10 min podem bloquear PRs. Fixar versão/cache apenas após revisão de compatibilidade.
6. O `test-pager-auth` continua rodando para mudanças em outros add-ons. Melhorar isolamento por paths sem suprimir required checks; pendente.
7. Não há prova de execução do script remoto exato em checkout completo; **validação local integral e CI continuam pendentes**.

## Preparação de homologação sem fechamento do pacote — 16/11/2026
- **Autorização recebida:** corrigir riscos de CI e preparar homologação, **sem encerrar o pacote Avisaqui**, sem merge/deploy/publicação. Desenvolvimento de outras equipes continua.
- `validate-addons.yml`: job `test-pager-auth` mantém seu nome/ID para preservar o contexto do check. Novo passo de detecção de mudanças usa base de PR ou SHA anterior do push; se a base não estiver disponível ou o evento não for reconhecido, **executa os testes**. Em alteração exclusiva de outros add-ons, mantém o job presente e evita npm/testes Pager. O job de sintaxe/cadastro continua obrigatório na mesma execução. O comando de instalação passa de `npm install` para `npm ci` (lockfile existente). Commit `2ff878d8bf502c471319870817fe475429ce614a`.
- **Risco residual:** o job de auth pode ficar verde sem executar npm em PR sem alterações do Pager; antes de homologar, revisar required checks reais e se a política aceita esse contexto condicional. Alterações em dependências compartilhadas fora dos caminhos monitorados podem exigir ampliar a lista. Não fazer merge sem essa revisão.
- O check `package-policy` mantém seus filtros; não foram removidos nem houve alteração de proteção. O catálogo JSON não cria jobs automaticamente. Builds ARM64 permanecem manuais.
- **Homologação pendente:** checkout completo, análise sintática de YAML/expressões, testes locais do detector em cenários PR/push/sem base, leitura das regras de proteção e execução final de CI somente após restauração de capacidade e autorização. **Não significa fechamento do pacote.**


## Incidente pós-publicação Avisaqui 002 — análise de risco proporcional (17/11/2026)

**Fatos verificados:** PR privado #22 integrado no SHA f3e93faa7cdd107d976d7f60c6250103b6e53a1a; PR público #35 integrado em 5977b1b6522dbc7682e1ef8e672c14c52c9c4bd2. Versão do Pager 0.1.19-rc.1 publicada na main da loja GitHub, **não instalada no Home Assistant por esta operação**.

**Análise de risco que deveria ter antecedido o merge:**

| Risco | Evidência real | Decisão proporcional |
|---|---|---|
| Quebrar o runtime Evolution | Nenhum arquivo em evolution-api/ foi alterado pelo PR | Não bloquear a publicação do Avisaqui nem reiniciar Evolution |
| Mudar a geração futura de builds Evolution | Workflow compartilhado passou a usar workflow_dispatch para build ARM64, com seleção manual de evolution-api | Risco operacional de acionamento futuro; proprietário foi informado e aceitou o impacto |
| CI compartilhada falhar | Falha real no run 44067864444: registry omitia umdoislab-central | Corrigir somente o cadastro |
| Instância Evolution no Raspberry ter regressão | Sem inspeção direta do serviço; proprietário relatou que estava funcionando | Não declarar homologação funcional nem tocar em dados/instalação sem evidência |

**Correção e prova:** o arquivo .github/addon-registry.json recebeu só a entrada do add-on **já existente** umdoislab-central, slug umdoislab_central, arquitetura aarch64, commit d12135bd4b353668156d33dc71e8f39b08cdadf3. A execução automática de GitHub Actions [44068193157](https://github.com/mmcromero/hassio-addons/actions/runs/44068193157) concluiu completed/success: jobs syntax e test-pager-auth passaram. Os builds ARM64 ficaram **skipped conforme seleção manual**; não apresentar esses skips como build aprovado na execução.

**Conduta futura mandatória:** aplicar GOV-STD-001 v0.9 §13, publicada no repositório canônico: medir probabilidade, impacto, reversibilidade e custo de atraso; separar hipótese de defeito confirmado; não bloquear produto A por risco hipotético em produto B. Com autorização para o ato e risco residual admissível, executar o lote completo, verificar eventos e logs pós-merge, corrigir apenas problemas concretos. Manter NO-GO para segurança crítica, perda de dados, operação sem autorização ou falta de rollback quando necessário. Não iniciar builds pesados ou cobrança para testar hipótese sem motivo.

**Estados distintos:** GitHub publicado; CI da loja corrigida; runtime Evolution do Raspberry NÃO INSPECIONADO; instalação/homologação do Pager no Raspberry PENDENTE. Não reabrir PRs já integrados para simular progresso.


## Novo fluxo de publicação Avisaqui — main preservada

**Decisão expressa do proprietário em 17/11/2026; política canônica privada:** `mmcromero/pager-virtual/docs/governanca/POLITICA-DE-PACOTES-E-BRANCHES.md`.

- **`main` pública é catálogo ESTÁVEL**, somente versões já testadas em canal RC e homologadas no ambiente de destino, mediante autorização da promoção. Não fazer merge de versão de teste em `main` por conveniência.
- **`release-candidate` pública é canal de testes**, derivado integralmente por `scripts/export-distribution.py` da RC privada, com inventário e hashes; candidatos são publicados para homologação nessa branch. Não alterar Evolution API ou outros add-ons ao atualizar somente Pager.
- **Home Assistant permite `https://github.com/mmcromero/hassio-addons#release-candidate`** como URL de repositório de outra branch *quando ela realmente existir*. Isso cria **identificador de repositório e de add-on diferente** do endereço sem sufixo. A instalação existente não deve ser trocada, removida ou duplicada por esta decisão documental. Exige plano operacional com backup, coexistência/slug, validação de dados e autorização própria.
- **Promoção:** após ensaio real e aceite da candidata, comparar SHA/versão/hashes e integrar o conteúdo aprovado em `main` com autorização. Falha volta a desenvolvimento, sem contaminar main. Os registros antigos de RC publicadas em main permanecem históricos; **não afirmar que todas as versões hoje em main foram homologadas**.
- Esta política está **documentada, sem implantação técnica da nova topologia**. Não criar branch, disparar Actions, mudar canal da loja ou acessar Home Assistant por este adendo.

**Fonte oficial da compatibilidade por branch:** https://contributors.home-assistant.io/apps/guides/repository/
