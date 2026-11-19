# Procedimento universal de publicação — Home Assistant Add-ons

**Regra P0 vigente — 19/11/2026.** Aplica-se a **qualquer profissional, agente, DEV, Codex, Tech Lead, Governança, novo integrante ou executor delegado**, e a **qualquer add-on** distribuído por `mmcromero/hassio-addons`. A função não cria rito alternativo. A rotina específica de um produto pode acrescentar cuidados justificados, mas não substituir arbitrariamente este procedimento. Segurança e autorizações obrigatórias continuam válidas.

**Antes de declarar impedimento:** identificar sintoma, repositório, versão/HEAD, add-on e etapa; consultar este arquivo e a documentação específica vigente; executar o procedimento autorizado; verificar alternativas já aprovadas, inclusive GOV-BLK-002. Sem evidência de que a rotina não atende ao caso, um NO-GO é **DESVIO DE PROCEDIMENTO**, e deve ser devolvido para corrigir apenas a etapa necessária. Não presumir que hardware, CI, Actions, QEMU ou virtualização ausentes bloqueiam a publicação.

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
