# Procedimento universal de publicação — Home Assistant Add-ons

**Regra P0 vigente — 19/11/2026.** Aplica-se a **qualquer profissional, agente, DEV, Codex, Tech Lead, Governança, novo integrante ou executor delegado**, e a **qualquer add-on** distribuído por `mmcromero/hassio-addons`. A função não cria rito alternativo. A rotina específica de um produto pode acrescentar cuidados justificados, mas não substituir arbitrariamente este procedimento. Segurança e autorizações obrigatórias continuam válidas.

**Antes de declarar impedimento:** identificar sintoma, repositório, versão/HEAD, add-on e etapa; consultar este arquivo e a documentação específica vigente; executar o procedimento autorizado; verificar alternativas já aprovadas, inclusive GOV-BLK-002. Sem evidência de que a rotina não atende ao caso, um NO-GO é **DESVIO DE PROCEDIMENTO**, e deve ser devolvido para corrigir apenas a etapa necessária. Não presumir que hardware, CI, Actions, QEMU ou virtualização ausentes bloqueiam a publicação.

## P0 — Identidade visível obrigatória

Todo add-on deste catálogo deve usar o prefixo literal **`Fábrica de Ideias - `** no campo `name` do `config.yaml` e também em `panel_title`, quando declarado.

Exemplos: `Fábrica de Ideias - Portal de Governança`, `Fábrica de Ideias - Design System Lab`, `Fábrica de Ideias - Kanban`.

Antes de empacotar/publicar, conferir os dois campos tanto na fonte quanto no artefato exportado. Qualquer ausência ou variação do prefixo reprova a validação. Não aceitar `Fábrica de Softwares` nem variações. A regra não altera `slug`, diretório, IDs técnicos ou origem do repositório; não renomear instalações existentes nem executar instalação/atualização por causa desta conferência.

## P0 — Contrato de URL do Home Assistant Ingress

**Regra obrigatória para todos os add-ons com `ingress: true`:**

1. Se a página inicial da aplicação estiver na raiz `/` (caso padrão), **omitir completamente a chave `ingress_entry`** do `config.yaml`. Não declarar `ingress_entry: /` nem `ingress_entry: ""`.
2. Declarar `ingress_entry` somente quando a página inicial estiver em uma subrota real. Nesse caso, informar apenas o caminho da subrota, sem repetir o prefixo do token e sem barra final desnecessária.
3. Conferir o valor efetivamente retornado pelo Supervisor em `ingress_url` depois da instalação/atualização. Para entrada na raiz, o URL deve terminar em uma única barra: `/api/hassio_ingress/<token>/`.
4. Testar a interface pelo botão **Abrir interface** do Home Assistant; verificar página inicial, CSS, JavaScript, imagens, chamadas de API e navegação. Estado `started` e build concluído não comprovam Ingress funcional.
5. Nunca aceitar apenas um teste direto à porta interna como homologação de Ingress. A autenticação e o roteamento reais passam pelo proxy do Supervisor.

**Causa técnica documentada (25/11/2026):** o Supervisor monta o URL como `/api/hassio_ingress/<token>/` e concatena o valor de `ingress_entry` quando a chave está presente. Assim, declarar explicitamente `ingress_entry: /` gera um URL terminado em `//`. No Raspberry Pi 4, os manifests do Design System Lab e Portal de Governança declaravam `/` e o Supervisor retornava URLs com `//`; o add-on WhatsApp Umdoislab, que omite a chave para a raiz, retornava URL com uma única barra. A comparação foi confirmada nos manifests e na API de estado dos três apps. O campo foi removido dos dois manifests afetados.

Referências oficiais: [configuração de apps — Ingress](https://contributors.home-assistant.io/apps/reference/configuration/) e [guia oficial de Ingress](https://contributors.home-assistant.io/apps/guides/ingress/).


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
