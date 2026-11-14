# UMDOISLAB — Protocolo de continuidade e entrega documental

**Aprovado pelo proprietário:** 14/11/2026.  
**Escopo:** desenvolvimento da Central de Atendimento, Evolution API, workflows n8n e integrações da Umdoislab.  
**Finalidade:** impedir perda de decisões técnicas entre chats, desenvolvedores, PRs, pacotes e versões instaladas.

## Princípio

**Uma entrega técnica importante não está documentalmente encerrada enquanto não houver passagem de bastão atualizada, no mesmo PR/pacote de trabalho, refletindo fatos, decisões, testes, pendências e versões.** Não depender de memória do assistente nem do nome de um JSON para determinar qual sistema está em uso.

## Eventos que exigem atualização da passagem de bastão

- Conclusão de implementação, alteração de comportamento ou mudança de arquitetura/regras de negócio.
- Novo PR, merge, release, build distribuído, atualização do add-on, publicação/despublicação de workflow.
- Mudança em credenciais/integração, endpoints, webhook, política de contatos, estados de atendimento ou autorização.
- Decisão técnica tomada, recusada, adiada ou substituída, **mesmo sem código**.
- Diagnóstico relevante, testes que revelam divergência e correção de documentação anteriormente imprecisa.

## Procedimento mínimo por pacote

1. **Antes de iniciar:** ler `ESTADO-ATUAL-UMDOISLAB.md`, documentos de continuidade e código relevante. Consultar versões/capturas atuais. Se houver divergência, descrevê-la antes de implementar.
2. **Durante:** registrar escolhas e sua origem; distinguir proposta do assistente, decisão do proprietário, implementação, teste e implantação. Não declarar uma decisão “nova” se já foi tomada e documentada.
3. **Antes de fechar o PR/pacote:** atualizar o inventário em `ESTADO-ATUAL-UMDOISLAB.md`; manter o histórico sem sobrescrever evidências anteriores; atualizar README, instruções de instalação e arquitetura afetadas. Referenciar PR/commit, nome **interno** e arquivo real do workflow, versão de add-on e versão do software upstream separadamente.
4. **Evidenciar:** informar o que foi verificado no GitHub (commit/CI), o que foi confirmado em HA/n8n (captura/log sem segredos), o que foi apenas relatado e o que continua não verificado. Resultado “Success” de CI não equivale a implantação; mensagem “encaminhei” não equivale a ficha registrada.
5. **Encerrar:** garantir que outro desenvolvedor saiba o estado atual, como reproduzir a verificação sem segredos, os riscos, as próximas ações autorizadas e as decisões adiadas. Se não houver acesso ao ambiente, registrar a limitação, não preencher lacunas.
6. **No merge:** só afirmar que a main está atualizada depois de conferir o merge. Se o PR ainda estiver aberto, usar “preparado em branch/PR”.

## Quadro mínimo de atualização

A cada evento relevante, registrar:
- **Data BRT e escopo**; PR/commit/documentos afetados.
- **Estado anterior → novo**: código versionado; versão do pacote; versão instalada; workflow atual *Published*; nome do arquivo de origem e webhook.
- **O que mudou e por quê**; quem originou a preocupação/decisão; critérios aceitos.
- **Testes e evidências** (unitários/CI/simulação/HA/n8n/WhatsApp) + limitações.
- **Implantação**: não feita / feita (prova) / desconhecida; impacto e rollback.
- **Pendências explícitas** e respectivas restrições (adiado, sem autorização, bloqueado, pronto para revisão).

## Regras contra gaps

- **Documentação de estado atual é única:** `docs/ESTADO-ATUAL-UMDOISLAB.md`. Documentos antigos preservam valor histórico, mas devem apontar para essa página e não se declarar canônicos quando obsoletos.
- Não renomear ou inferir versão em execução pelo nome do arquivo; o workflow chamado v1.6 pode estar salvo num JSON chamado v1.5.
- Não dizer que uma funcionalidade está implantada porque existe em código/PR.
- Não apagar discussões arquivadas nem convertê-las em hipóteses próprias. Quando a arquitetura original não estiver recuperável, deixar a lacuna clara e registrar somente requisitos sustentados pelas fontes.
- **Alterações documentais não autorizam** automaticamente execução de deploy, merge, configuração, remoção de add-ons, uso de dados pessoais ou desenvolvimento de itens adiados.
- Não publicar números, tokens, senhas, dados de clientes, transcrições privadas ou nomes de usuários na documentação.
- Tratar o validador de contatos como **decisão técnica registrada e trabalho adiado**; não voltar a exigir testes manuais e nem chamar uma simples coleta de contatos de validação completa.

## Checklist de revisão de PR

- [ ] Passagem de bastão atualizada no mesmo PR, ou justificativa explícita caso mudança seja estritamente cosmética sem impacto.
- [ ] Inventário atual do ambiente e versões lógicas corrigido.
- [ ] Decisões e pendências anotadas sem reabrir debates decididos.
- [ ] CI/testes e implantação identificados separadamente.
- [ ] Sem segredos ou identificadores de clientes.
- [ ] Modo /pair: branch isolada, main preservada até aprovação; sem Codex/Work.
- [ ] PR revisado e somente então integrado quando expressamente autorizado.
