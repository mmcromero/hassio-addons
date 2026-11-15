# AVISAQUI-PRINT-HA-001 — Preparação controlada da integração de impressão

**Estado:** branch de preparação, sem merge ou publicação. **Origem:** [PR #16 no repositório privado](https://github.com/mmcromero/pager-virtual/pull/16), base técnico/visual PR #14.

## Escopo sincronizado
- `src/routes/integracao-impressao.js`: API autenticada por chave de agente, isolamento por restaurante, registro de eventos e criação de pedido com SSE.
- `src/public/impressao.html`: gestão de credenciais e últimos recebimentos, restrita a gerente/master.
- `src/server.js`: registro das rotas e proteção da página.
- `src/public/kds.html`: atalho para a integração, preservando interface recente de administração.
- `tests/integracao-impressao.test.js`: cobertura de autenticação, revogação, idempotência, evento duplicado e isolamento multi-restaurante.

Os scripts Python do agente Windows continuam no **repositório privado** `pager-virtual/scripts/impressao_windows/` e no artefato CI do PR #16. Não são copiados para o add-on ARM64: rodam exclusivamente no computador do caixa. A nova API recebe número e itens extraídos, não dados RAW/fiscais.

## Invariantes operacionais
- **Versão do add-on em branch: 0.1.11, sem bump ainda.** Uma próxima versão deve ser definida quando a publicação for autorizada.
- Preservados slug `pager_virtual`, nome de pasta `pager-virtual/`, porta 8095, `/data`, Dockerfile, run.sh, options, esquema de autenticação existente.
- As duas novas tabelas são criadas aditivamente pela rota durante a inicialização. Nenhuma tabela legada é apagada nem dados migrados destrutivamente.
- Não executar scripts que alterem o Raspberry Pi; nenhuma instalação automática via este PR.
- CI existente: `.github/workflows/validate-addons.yml` para lint/manifestos, build Docker ARM64, smoke com volume descartável e `npm test`. O workflow **não publica** uma imagem e não instala o add-on.
- Antes de publicar: verificar backup recuperável consistente de SQLite/WAL e testes de restore, versão proposta e changelog; instalar somente após autorização separada.

## Evidência do repositório de origem
- PR #16: https://github.com/mmcromero/pager-virtual/pull/16
- CI do código-fonte: https://github.com/mmcromero/pager-virtual/actions/runs/43663237830 — 42/42 testes Node, checagem Python e artefato Windows.
- O teste de impressão física do pedido 135 foi aprovado em laboratório, **mas NÃO comprova** fluxo Windows→API→KDS no HA.
- Esta branch deverá receber evidências próprias da CI add-on antes de ser considerada validada.

## Limitações e critérios da próxima homologação
1. API + UI no add-on ainda não foram testadas no HA real. O projeto fonte não contém a correção do histórico de pedidos entregues; bug conhecido permanece fora desta entrega.
2. Monitor Windows observa um `captura.prn` de nome fixo. Não há garantia de capturar todos os trabalhos consecutivos; operação humana real deverá ser medida.
3. OCR inicial extrai o número da comanda; itens ficam vazios. Não criar pedido por reconhecimento incerto.
4. Conflitos de número ativo entram como pendência; painel exibe evento, mas ainda não oferece classificação visual completa de reimpressão vs novo pedido.
5. Encaminhamento físico automático e QR injetado **não fazem parte** deste sincronismo. A impressora física não foi modificada.
6. Homologação: primeiro provar pedido sintético capturado no Windows aparecendo no KDS do ambiente de teste. Em seguida validar reinício e persistência, sem comprometer dados existentes.
7. **Condição de publicação:** revisão do diff contra a main atual, CI verde, avaliação de backup e autorização explícita de merge/instalação. No estado atual, não executar nem anunciar como recurso disponível do piloto.

## Recuperação e reversão
O add-on instalado permanece na versão corrente e com seus dados. Se a nova rota não passar nos testes, corrigir esta branch sem mexer em `main` nem em `/data`. O backup do banco real e eventual retorno à versão anterior devem ser preparados e verificados no momento da instalação futura, não simulados como concluídos neste documento.
