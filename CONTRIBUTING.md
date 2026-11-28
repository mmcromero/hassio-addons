# Procedimento universal de publicação — Home Assistant Add-ons

**Regra P0 vigente — 19/11/2026.** Aplica-se a **qualquer profissional, agente, DEV, Codex, Tech Lead, Governança, novo integrante ou executor delegado**, e a **qualquer add-on** distribuído por `mmcromero/hassio-addons`. A função não cria rito alternativo. A rotina específica de um produto pode acrescentar cuidados justificados, mas não substituir arbitrariamente este procedimento. Segurança e autorizações obrigatórias continuam válidas.

**Antes de declarar impedimento:** identificar sintoma, repositório, versão/HEAD, add-on e etapa; consultar este arquivo e a documentação específica vigente; executar o procedimento autorizado; verificar alternativas já aprovadas, inclusive GOV-BLK-002. Sem evidência de que a rotina não atende ao caso, um NO-GO é **DESVIO DE PROCEDIMENTO**, e deve ser devolvido para corrigir apenas a etapa necessária. Não presumir que hardware, CI, Actions, QEMU ou virtualização ausentes bloqueiam a publicação.

## P0 — Identidade visível obrigatória

Todo add-on deste catálogo deve usar o prefixo literal **`Fábrica de Ideias - `** no campo `name` do `config.yaml` e também em `panel_title`, quando declarado.

Exemplos: `Fábrica de Ideias - Portal de Governança`, `Fábrica de Ideias - Design System Lab`, `Fábrica de Ideias - Kanban`.

Antes de empacotar/publicar, conferir os dois campos tanto na fonte quanto no artefato exportado. Qualquer ausência ou variação do prefixo reprova a validação. Não aceitar `Fábrica de Softwares` nem variações. A regra não altera `slug`, diretório, IDs técnicos ou origem do repositório; não renomear instalações existentes nem executar instalação/atualização por causa desta conferência.


### P0 — Assets oficiais de identidade visual

Todo add-on distribuído neste catálogo deve preservar os dois assets oficiais compartilhados:
- `icon.png`: blob Git obrigatório `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a`.
- `logo.png`: blob Git obrigatório `7e500016222b0a5bf395be8ed17447edeb3e2af9`.

Os arquivos devem estar na raiz da pasta do add-on publicado. Não criar iniciais, logotipos alternativos, versões redesenhadas ou cópias visualmente semelhantes. A validação deve comparar o Git blob SHA dos dois arquivos na fonte e no pacote exportado com os valores acima; conferir apenas nome, extensão ou existência não basta. Quando a interface web do add-on também exibir a marca, usar o asset oficial do catálogo, respeitando o caminho/base dinâmica do Ingress. Esta regra complementa o prefixo obrigatório de `name` e `panel_title`; não altera slug, diretório ou IDs técnicos.

## P0 — Contrato completo de Home Assistant Ingress (25/11/2026)

Aplica-se a todo add-on com `ingress: true`. A configuração do manifesto e a compatibilidade do servidor são requisitos distintos e ambos devem ser atendidos.

### Manifesto
- Para entrada na raiz, manter `ingress: true` e `ingress_port: <porta-interna>` e **omitir completamente** `ingress_entry`.
- Não declarar `ingress_entry: /`, string vazia, `./` ou substituto. O Supervisor concatena o valor configurado ao URL-base e `/` pode produzir barra duplicada (`//`).
- Declarar `ingress_entry` somente para uma subrota real, com o caminho dessa subrota.
- Após instalar/atualizar, ler `ingress_url` do Supervisor; para raiz, conferir que termina com uma única barra.

### Contrato do servidor
- O Supervisor usa prefixo dinâmico semelhante a `/api/hassio_ingress/<token>/`. Nunca fixar, fabricar ou persistir o token.
- Ler `X-Ingress-Path` como base dinâmica da sessão e validar a origem do proxy confiável **antes** de aceitar caminhos relativos.
- Implementações podem receber o caminho com o prefixo ainda presente ou já removido pelo proxy. O servidor deve tratar ambos sem perder o isolamento da sessão.
- Remover somente o prefixo exato correspondente à sessão; rejeitar prefixo/token divergente, caminho malformado e conexões de peers não confiáveis.
- Gerar URLs de assets, CSS, JavaScript, imagens, fontes, API, links internos e redirecionamentos de forma compatível com o prefixo atual. Evitar referências absolutas à raiz do domínio quando elas escaparem do Ingress.
- Tratar barra final sem criar `//`, redirecionamento circular ou perda de sessão.

### Homologação obrigatória
- Abrir pelo botão oficial **Abrir interface** do Home Assistant; não usar URL/token copiado de sessão anterior como link permanente.
- Conferir HTML, CSS, JS, imagens/fontes, navegação e redirecionamentos sob o prefixo dinâmico.
- Conferir `/api/health` e as APIs funcionais do app (por exemplo `/api/v1/portfolio`) dentro do Ingress.
- Confirmar respostas esperadas (200 ou status funcional documentado), ausência de 400/404/502 indevidos e ausência de loop.
- Inspecionar requisições do navegador, logs do add-on e logs do Supervisor.
- `state: started`, build concluído, teste direto à porta ou chamada de diagnóstico fora do proxy **não comprovam** Ingress funcional. Um 401 de token antigo e um 403 de acesso direto à porta também não substituem o teste pelo botão oficial.
- Não remover allowlist de IP, validação do peer, cabeçalho de sessão ou outras proteções para fazer a página abrir.

**Caso comprovado — Portal de Governança (25/11/2026):** o manifesto do Portal já omitia `ingress_entry`, mas o servidor precisava aceitar tanto o caminho ainda prefixado quanto o caminho relativo após o proxy remover o prefixo. A correção dev.6 preservou a validação do peer Supervisor e de `X-Ingress-Path`, e o proprietário confirmou a abertura pelo botão oficial do Home Assistant. A homologação complementar de assets, APIs e navegação deve ser registrada separadamente; não inferir aprovação completa apenas pela abertura inicial.

**Referência comparativa:** Design System Lab `0.1.0-test.6`, cujo manifesto publicado omite `ingress_entry` para entrada na raiz.


## P0 — Assets de apresentação dos apps

Como convenção visual do catálogo `mmcromero/hassio-addons`, cada app distribuído deve incluir na raiz da pasta do app:
- `icon.png`: PNG quadrado (128×128 px recomendado).
- `logo.png`: PNG horizontal (aproximadamente 250×100 px recomendado).

A validação deve conferir existência, formato e dimensões recomendadas no pacote exportado e na pasta publicada. O campo `panel_icon` é o ícone MDI do atalho lateral e é independente desses dois arquivos. Se o app não possuir assets aprovados, isso deve ser tratado antes da publicação, não omitido silenciosamente.

## 1. Organização e fonte

- Cada add-on possui sua **pasta própria na raiz**, `config.yaml` com `name`, `version`, `slug` único e `arch`, e documentação/versão próprias; `repository.yaml` fica **somente na raiz**.
- `Dockerfile` quando se usa build local; `run.sh` quando necessário. `build.yaml` só quando a configuração exigir.
- **Fonte de desenvolvimento e catálogo não são a mesma coisa.** Consultar o procedimento do produto para obter branch de desenvolvimento, corte de SHA, candidata, exportação e manifesto. Para o Avisaqui, seguir `pager-virtual:desenvolvimento` → `release-candidate` privada → exportação auditável → `hassio-addons:main/pager-virtual/`. **Não impor branches ou PRs próprios do Avisaqui a outros add-ons.**
- Publicar na `main` pública **somente a pasta do add-on autorizado**, preservando outros add-ons, `repository.yaml`, workflows e arquivos compartilhados. A loja configurada com a URL sem `#branch` acompanha essa `main`. Branch pública alternativa, por si só, não atualiza essa loja.
- Não fazer publicação, merge de fonte privada, execução de Actions, instalação ou alteração no Raspberry sem a autorização aplicável. Normas documentais aprovadas têm ciclo de atualização próprio, conforme GOV-STD-001.

## 2. Testes obrigatórios, proporcionais à mudança

1. **Inspecionar diff, sintaxe e configuração** alterados (YAML, shell, JavaScript/Python, Dockerfile etc. conforme o caso).
2. **Executar teste dirigido do comportamento modificado** no ambiente disponível. Se alterar autenticação, banco ou API, acrescentar casos positivos/negativos pertinentes. Não chamar teste não executado de PASS.
3. **Verificar segurança e distribuição:** segredos ausentes; versão e arquitetura coerentes; dependências e caminhos corretos; manifesto/proveniência/hash quando o exportador do produto os fornece; alterações públicas limitadas ao add-on autorizado.
4. **ARM64:** `arch: [aarch64]` informa suporte declarado, **não comprova compatibilidade real**. Não exigir **por rotina** CI ARM64, QEMU, VM, Codespaces, runner externo ou Actions. Se o `config.yaml` não aponta para imagem pré-compilada (`image`) e o add-on usa Dockerfile, o Supervisor do Home Assistant pode realizar o build na máquina alvo durante a instalação/atualização; esse **teste real é etapa de homologação**, não pré-requisito genérico de emulação externa.
5. **Exceções justificadas:** imagem pré-compilada, dependência binária nativa, comportamento específico de arquitetura, falha concreta de build ou risco de segurança podem exigir build/ensaio extra antes da publicação. Registrar motivo, teste mínimo necessário, alternativa, responsável e autorização. Não confundir impossibilidade de emular com impossibilidade de publicar RC de teste, se autorizada.
6. **Não repetir** testes já válidos para artefato/SHA não alterado sem causa técnica. Não converter SKIP ou build antigo em PASS.

### P0 — Transferência controlada da fonte para o catálogo

Quando a fonte do add-on estiver em outro repositório, a publicação é uma **exportação de pacote**, não um merge entre repositórios:

1. Consultar o manual e as instruções do produto; identificar branch/SHA da fonte e a seleção oficial de arquivos do pacote.
2. Construir ou preparar o pacote pelo executor documentado pelo produto. Não impor Codespaces, Actions, QEMU, checkout limpo ou ferramenta externa sem requisito técnico comprovado.
3. Atualizar exclusivamente `<slug-do-app>/` na `main` deste catálogo. Preferir Git Data API (blobs + tree baseado no HEAD atual + commit) ou mecanismo equivalente que preserve o restante da árvore.
4. Nunca fazer merge da branch-fonte neste repositório, substituir a árvore completa, remover arquivos compartilhados ou alterar outros apps como efeito colateral.
5. Antes do commit, revisar o diff e validar manifesto, versão, identidade, arquitetura, assets, dependências, segredos e proveniência. Depois, reler o HEAD e conferir que o diff ficou limitado ao app autorizado.
6. Usar atualização condicional do ref (expected SHA/lease). Se a `main` avançar durante a operação, reler e reconciliar; não usar force push para contornar concorrência.
7. Só depois da confirmação do commit, atualizar o índice do Supervisor, conferir a versão disponível e executar a instalação/atualização autorizada. Acompanhar build e logs no hardware-alvo e registrar separadamente publicação, instalação, build e homologação.

**Regra de conduta:** não discutir com o proprietário a existência de uma rota já documentada nem pedir que ele repita instruções. O executor deve consultar o manual, escolher a ferramenta disponível, executar e apresentar evidência. Se houver falha real, apontar a etapa e a mensagem observada e corrigir essa etapa. Um NO-GO sem tentativa do procedimento e sem evidência concreta é desvio de procedimento.

## 3. Fechamento, publicação e homologação

1. Concluir o lote completo na fonte aprovada e verificar o HEAD. Se houver processo de congelamento/candidata/exportação, aplicá-lo conforme o manual do produto; não inventar comandos, branches ou gates novos.
2. Conferir versão, configurações, Dockerfile, arquivos da distribuição, escopo e integridade. Atualizar changelog do add-on.
3. Mediante autorização de publicação, atualizar apenas a pasta correspondente na `main` do catálogo. Conferir remotamente commit, arquivos e versão e registrar a evidência na Issue existente.
4. **PUBLICADO NO GITHUB NÃO SIGNIFICA INSTALADO OU HOMOLOGADO.** A instalação/atualização no Home Assistant é uma etapa separada feita pelo operador autorizado. Ali são observados build real quando aplicável, inicialização, logs e comportamento da função no hardware alvo. Resultado real deve voltar ao registro da tarefa.
5. Falha de build ou execução real deve ser diagnosticada com logs/versão e corrigida na fonte do produto; repetir a esteira somente na parte afetada. Não alterar dados do host, add-ons alheios ou serviços por inferência.

## 4. Registro mínimo de bloqueio

Registrar na **Issue existente**: procedimento e revisão consultados; ambiente/HEAD/sintoma; tentativa autorizada e resultado; evidência concreta do que permanece bloqueado; por que as alternativas aprovadas não resolvem; próxima ação e responsável. Bloqueios reais de segurança, credenciais, permissões e autorização permanecem válidos. Não inventar aprovação nem criar Issue duplicada.

## 5. Segurança e referências

Não versionar `options.json`, tokens, senhas, bancos, sessões, backups, mídia privada ou `.env`; dados persistentes pertencem ao volume configurado, não ao Git. Não expor portas sem controles adequados. Mudanças destrutivas exigem confirmação do destino e autorização própria.

- [README do catálogo](README.md)
- [Home Assistant — repositório de apps](https://developers.home-assistant.io/docs/add-ons/repository/)
- [Home Assistant — estrutura de apps](https://developers.home-assistant.io/docs/add-ons/configuration/)
- [GOV-STD-001](https://github.com/mmcromero/fabricacao_e_orcamentos/blob/main/docs/operacao/GOV_STD_001.md)
- [GOV-BLK-002](https://github.com/mmcromero/fabricacao_e_orcamentos/blob/main/docs/operacao/GOV_BLK_002.md)
- [Avisaqui — rotina específica](https://github.com/mmcromero/pager-virtual/blob/main/docs/governanca/ROTINA-DO-DESENVOLVEDOR.md)


## Artesão Digital — esteira específica

- Fonte privada: `mmcromero/fabricacao_e_orcamentos`.
- Distribuição única Home Assistant: pasta raiz `artesaos-piloto/` neste repositório.
- Identidade do add-on: nome `Fábrica de Ideias - Artesão Digital`; slug `artesaos_piloto`; manter `icon.png` e `logo.png` oficiais na raiz da pasta.
- A pasta do add-on deve conter o pacote completo exportado da fonte aprovada, sem misturar documentação privada, credenciais, bancos, opções ou dados de runtime.
- Seguir `docs/operacao/AD_ESTEIRA_RAPIDA_001.md` no repositório de fonte para corte de versão, revisão de escopo, exportação e proveniência. Publicar somente `artesaos-piloto/` na `main` deste catálogo.
- O Supervisor do Home Assistant executa o build local quando o add-on usa Dockerfile sem `image`; build ARM64 externo, Actions e Factory Runner não são pré-requisitos genéricos. Instalação e homologação no HA permanecem etapas distintas da publicação Git.

## Estado atual da execução de validações do catálogo

Por decisão do proprietário em 25/11/2026, os workflows deste repositório permanecem versionados e preservados, mas sem gatilhos automáticos de push ou pull_request. Atualmente os três arquivos em `.github/workflows/` aceitam somente `workflow_dispatch`. Não acionar manualmente como parte do fluxo normal de publicação, não restaurar automações e não tratar GitHub Actions como executor disponível. A validação proporcional deve ocorrer pelo executor autorizado e disponível (Factory Runner quando concluído e homologado; até lá, execução manual assistida e homologação no HA). Esta decisão não apaga workflows, scripts nem histórico e não se estende a outros repositórios.
