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
