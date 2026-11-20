## 0.1.8 — patch de UX e legendas locais (PUBLICADO NO GITHUB; INSTALAÇÃO PENDENTE) — 20/11/2026

- **Publicação no feed:** uma única opção visível; 1 foto gera `feed`, 2 a 20 fotos geram `carousel` automaticamente. O formato interno e rascunhos anteriores continuam compatíveis.
- **Legendas:** escolha de uma legenda geral ou texto separado para cada imagem de carrossel. Persistência local aditiva no SQLite e na API privada (`captionMode`, `slideCaptions`); rascunhos 0.1.7 são preservados com modo geral por padrão. Nenhuma legenda individual é enviada à API Meta; publicação externa segue desativada.
- **Prévia de celular:** navegação anterior/próxima e indicador de posição em carrossel, incluindo texto da imagem selecionada.
- **Aprovações:** miniatura da primeira mídia, título derivado do início da legenda, resumo curto, tipo e estado nessa ordem. Clique na miniatura ou descrição abre modal central com celular grande, prévia completa e navegação apenas para leitura. Botões Editar/Aprovar/Agendar/Cancelar agenda preservados.
- **H11 — falha intermitente de mídia após sessão longa:** H11 passou por relato do proprietário depois de F5 (Story com MP4 já existente, prévia, reprodução, salvamento e aprovação), mas antes de recarregar a aba o MP4 não carregou e operações de upload/salvar produziram erro técnico de JSON. O patch passa a destacar mídia não carregada diretamente na miniatura/prévia, apresentar erro persistente junto ao formulário/Biblioteca quando uma operação falha e explicar resultados HTTP não confirmados sem afirmar que algo foi gravado ou descartado. **Causa HTTP exata ainda não identificada; não houve logs do HA.**
- **H10 — agendamento contextual:** janela de agendamento mostra a **primeira mídia**, um título derivado do início da legenda, um resumo da legenda e o tipo da publicação, sem alterar o esquema de dados. Data anterior à atual (horário de São Paulo) é recusada com mensagem clara dentro do modal, imediatamente acima de **Confirmar agenda**. Em falhas HTTP/servidor, a janela e o horário digitado permanecem, o erro fica visível e o sistema não exibe texto técnico de parsing JSON. Backend continua validando e recusando datas vencidas.
- **H09 — aviso persistente de conflito:** a API já rejeita versão antiga com HTTP 409, preservando a edição mais recente. O feedback antigo usava toast temporário, na mesma aparência de sucesso, e o proprietário não percebeu uma recusa. A candidata mostra agora **erro destacado e permanente junto ao formulário**, mantém o texto não salvo no campo, e orienta reabrir a publicação antes de tentar novamente. Os toasts de outros erros passam a ter apresentação distinta dos sucessos; contrato de versionamento e dados não foi alterado.
- **Visual unificado da Central:** Mensagens usa o tema escuro aprovado do Editorial (paleta, marca, menu lateral, topo conciso, painéis de conexão e tabela responsiva), sem trocar HTML do login nem ações internas de handoff/Meta. Ambos os módulos agora exibem botão **Sair** no cabeçalho, usando o mesmo `POST /auth/logout` existente; sem autenticação adicional.
- **Calendário após edição:** reserva anterior de data/hora é preservada em campo não executável; a publicação aparece no calendário com destaque **Aguardando nova aprovação** e botão **Aprovar** direto na lista. Reaprovação restaura automaticamente o horário se ainda futuro; se passou, mostra horário expirado e permite reagendar. Cancelar agenda continua limpando a reserva.
- **Persistência e segurança:** migração sem exclusão de dados, CSRF e mesma sessão administrativa, arquivos de mídia privados, nenhuma porta ou serviço novo. Limite de JSON de rascunho de 256 KiB para até 20 legendas de 2.200 caracteres; demais ações permanecem limitadas a 16 KiB.
- **Testes direcionados adicionados:** migração de base anterior, rascunhos persistentes, validação de payloads/limites, fluxo HTTP e roteiro Chromium de carrossel/modal. **Ainda não executados nesta conversa:** não declarar PASS, build de imagem ou homologação 0.1.8.
- **Situação da distribuição:** publicada em `hassio-addons:main/instagram-central/` no commit `a666f3e7dc837d68a2a80392fb8d9c2e8fb0e928`, com 13 arquivos do add-on atualizados, ícones preservados e sem Actions, merge da fonte privada ou alteração de outros apps. **Instalação e homologação 0.1.8 ainda pendentes**; Meta permanece desativada. A 0.1.7 foi instalada e testada manualmente pelo proprietário com ressalvas (H02/H09/H10/H11); referência: Issue #1.
- **Navegação após F5 no Ingress:** o retorno à tela de Mensagens foi relatado como não bloqueante. Não foi identificado mecanismo do wrapper HA que explique a troca; nenhuma mudança especulativa de roteamento/Ingress foi feita neste patch.

## 0.1.7 — Central Instagram unificada: Mensagens + Editorial (CANDIDATA PRIVADA, NÃO PUBLICADA/INSTALADA) — 20/11/2026

- Entrega a Central Editorial **dentro do mesmo add-on, painel e sessão administrativa** já usados por Mensagens, sem segundo aplicativo, login ou autenticador Meta.
- Integra a interface Editorial privada (biblioteca, upload, rascunhos, revisão, aprovação, agendamento, edição e cancelamento) ao backend HTTP e SQLite persistente. **Agenda não publica posts**; não existe executor de publicação Meta nesta candidata.
- Armazena o Editorial Umdoislab em `/data/editorial/editorial.sqlite3` e mídia em `/data/editorial/media/`. Preserva Mensagens em `/data/instagram.sqlite3`, dados existentes, sessão, chaves e credenciais legadas.
- Adiciona base multicontas com `business_id` interno separado do identificador Instagram. As rotas administrativas e de Mensagens desta entrega continuam limitadas à Umdoislab; **não ativa segunda conta real** nem herda segredos entre negócios.
- Reforça sessão e autorização, CSRF por ação/negócio, validação de upload, CSP, mídia privada, limites, versionamento transacional e bloqueio de reenvio após resultado ambíguo.
- Mantém `slug: umdoislab_instagram`, `arch: [aarch64]`, Ingress/porta interna 8099, padrão `backup: cold` e as opções `ingress_enabled:false`, `drafts_enabled:false`, `meta_oauth_enabled:false`. Não altera a Central WhatsApp, n8n, Gemini ou o NGINX.
- Atualiza Dockerfile com os módulos, interface, Pillow/tzdata e testes do add-on embutidos no build. Preserva a marca pública existente (mesmos `icon.png`/`logo.png` do catálogo).
- **Evidência de código já existente, sem repetição após alteração só documental/versionamento:** Python offline **152/152 PASS**, Chromium E2E PASS; build complementar Alpine **linux/amd64** **149/149 PASS** com CA TLS temporária do executor. O build original no executor falhou por confiança TLS, exit 1; o teste não foi feito em ambiente Codex integralmente independente. Ver [IG-PR7-GATE-001](https://github.com/mmcromero/instagram-automacoes/blob/d4a885460635d5930b8c8a1e4875e94918816dae/docs/evidence/IG-PR7-GATE-001-20261120/RELATORIO.md) e [parecer Issue #1](https://github.com/mmcromero/instagram-automacoes/issues/1#issuecomment-7040960917).
- **Status:** apenas branch privada de candidata 0.1.7, não distribuída, sem merge, Actions, publicação, instalação, ativação OAuth/webhook Meta, recebimento de DM real, envio Direct ou publicação de post. A 0.1.6 do catálogo é o pacote anterior e não inclui Editorial integrado.

## 0.1.6 — Lote 1: conexão oficial Meta e primeira DM (candidata experimental; NÃO ATIVADA) — 20/11/2026
- Corrige troca de código do Login Unificado para o contrato GET da Meta. Valida identidade da conta `@umdoislab` (ID exato) e portfólio antes de armazenar token.
- Adiciona diagnóstico visual de conexão no painel autenticado: configurações faltantes, conta verificada, webhook habilitado, assinatura solicitada, mensagens armazenadas e última entrada.
- Ações administrativas reais `Verificar acesso Meta` e `Assinar mensagens na Meta`; assinatura opt-in só do campo `messages`, nunca envia Direct. Protegidas por sessão e CSRF.
- Integra os testes de contrato Graph, OAuth e HTTP ao Dockerfile. Não altera o esquema existente nem apaga histórico do SQLite.
- Prepara fragmento HTTPS de três rotas exatas no NGINX existente, arquivado somente no repositório privado; **nenhuma alteração aplicada no Raspberry nesta branch**.
- Graph API padrão documentado `v27.0`; entradas OAuth e webhook continuam **false** por padrão. Mantém HTML login, Chrome, senha, marca e slug da 0.1.5.
- Testes locais comprovados: 9/9 Graph, 12/12 OAuth, 9/9 sessão-CSRF; hashes dos arquivos exatos conferidos. Sintaxe NGINX equivalente aprovada isoladamente. Suíte HTTP inteira e execução no Supervisor **pendentes**, sem alegar primeira DM real.
- Requer HTTPS público validado, autorização Meta, assinatura do campo messages e teste com outra conta, com segurança e revogação documentadas em `docs/IG-LOT1-REAL-001.md`.

## Em desenvolvimento — login HTML para Chrome (NÃO PUBLICADO) — 20/11/2026
- Troca a janela HTTP Basic do painel por um formulário HTML com campos `autocomplete=username` e `autocomplete=current-password`.
- Reutiliza `admin` e `panel_password` existentes; não grava nem expõe senha no código.
- Armazena apenas digest HMAC do token aleatório da sessão em SQLite; sessão expira em 12 horas e pode ser encerrada por **Sair**. Alterar senha invalida sessões antigas.
- Limite de tentativas incorretas e testes de login/logout, cookies, segurança e fluxo HTTP adicionados ao build do Supervisor.
- Mantém OAuth Meta, webhook, rascunhos e mensagens automáticas desativados; sem alteração no WhatsApp ou n8n.
- **Ainda não é uma versão de catálogo nem está instalada no Home Assistant**. Depende de revisão e autorização específica antes de publicar ou atualizar o Raspberry.

## 0.1.2 — OAuth Meta unificado (experimental, desativado por padrão) — 20/11/2026
- Adiciona login unificado Meta com `config_id`, `state` descartável, callback HTTPS e troca de código no servidor.
- Armazena credenciais cifradas no volume local do aplicativo; mantém os tokens fora da interface e dos logs.
- Todos os novos campos opcionais ficam vazios ou desativados por padrão; sem mensagens automáticas e sem ações no WhatsApp.
- Preserva painel Ingress, banco SQLite, slug e credenciais da versão 0.1.1; não muda a porta do aplicativo.
- Adiciona o pacote `py3-cryptography` e integra 4 testes de smoke + 11 testes OAuth no build local do Supervisor.
- **A publicação não configura o NGINX nem habilita o OAuth.** Instalação e homologação exigem autorizações próprias.

# Histórico — Central Instagram

## 0.1.1 — padronização da distribuição Home Assistant

- Nome público: `Fábrica de Softwares - Central Instagram`.
- `icon.png` e `logo.png` oficiais do catálogo compartilhado (mesmos blobs Git de Kanban e dos outros add-ons), inseridos na distribuição pública.
- Mantidos `slug: umdoislab_instagram`, dados SQLite, `panel_icon` interno, integração desativada e versão anterior imutável.
- Correção exclusiva de marca e versão; não instalada, nem homologada.

## 0.1.0 — primeira candidata de teste para Home Assistant (não instalada)

- Add-on experimental aarch64 com Dockerfile e Ingress.
- SQLite independente, deduplicação, fila de mensagens com reserva/ACK e handoff.
- Painel HTML autenticado, CSRF, auditoria e visualização de rascunhos.
- API interna de classificação; decisões sem envio e sem Gemini.
- Webhook Meta com HMAC-SHA256 desativado por padrão.
- Quatro verificações dirigidas sem rede executadas **durante futuro build do Supervisor**.
- Nenhum workflow n8n ou integração WhatsApp incluído na distribuição.
- Estado: preparação de candidata; sem instalação e sem homologação.


## Histórico do desenvolvimento — OAuth Meta Unified Login

- Endpoints internos de início e callback OAuth, com `state` de 10 minutos e cookie HTTPS seguro.
- Troca de código por Graph API (inativa até autorização), e token cifrado em arquivo restrito no volume `/data`.
- Metadados `meta_app_id`, `meta_login_config_id` e URL de retorno configuráveis; `meta_oauth_enabled:false` por padrão.
- 11 testes OAuth offline dirigidos, além dos testes HTTP criados para o callback; não ativa webhooks ou mensagens automáticas.
- **Não foi publicado/instalado na versão 0.1.1**. Nenhum arquivo do catálogo público modificado.
