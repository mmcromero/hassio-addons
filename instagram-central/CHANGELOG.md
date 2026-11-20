## 0.1.7 — Central Instagram unificada: Mensagens + Editorial (PUBLICADA NO CATÁLOGO; AINDA NÃO INSTALADA) — 20/11/2026

- Entrega a Central Editorial **dentro do mesmo add-on, painel e sessão administrativa** já usados por Mensagens, sem segundo aplicativo, login ou autenticador Meta.
- Integra a interface Editorial privada (biblioteca, upload, rascunhos, revisão, aprovação, agendamento, edição e cancelamento) ao backend HTTP e SQLite persistente. **Agenda não publica posts**; não existe executor de publicação Meta nesta candidata.
- Armazena o Editorial Umdoislab em `/data/editorial/editorial.sqlite3` e mídia em `/data/editorial/media/`. Preserva Mensagens em `/data/instagram.sqlite3`, dados existentes, sessão, chaves e credenciais legadas.
- Adiciona base multicontas com `business_id` interno separado do identificador Instagram. As rotas administrativas e de Mensagens desta entrega continuam limitadas à Umdoislab; **não ativa segunda conta real** nem herda segredos entre negócios.
- Reforça sessão e autorização, CSRF por ação/negócio, validação de upload, CSP, mídia privada, limites, versionamento transacional e bloqueio de reenvio após resultado ambíguo.
- Mantém `slug: umdoislab_instagram`, `arch: [aarch64]`, Ingress/porta interna 8099, padrão `backup: cold` e as opções `ingress_enabled:false`, `drafts_enabled:false`, `meta_oauth_enabled:false`. Não altera a Central WhatsApp, n8n, Gemini ou o NGINX.
- Atualiza Dockerfile com os módulos, interface, Pillow/tzdata e testes do add-on embutidos no build. Preserva a marca pública existente (mesmos `icon.png`/`logo.png` do catálogo).
- **Evidência de código já existente, sem repetição após alteração só documental/versionamento:** Python offline **152/152 PASS**, Chromium E2E PASS; build complementar Alpine **linux/amd64** **149/149 PASS** com CA TLS temporária do executor. O build original no executor falhou por confiança TLS, exit 1; o teste não foi feito em ambiente Codex integralmente independente. Ver [IG-PR7-GATE-001](https://github.com/mmcromero/instagram-automacoes/blob/d4a885460635d5930b8c8a1e4875e94918816dae/docs/evidence/IG-PR7-GATE-001-20261120/RELATORIO.md) e [parecer Issue #1](https://github.com/mmcromero/instagram-automacoes/issues/1#issuecomment-7040960917).
- **Status:** distribuição 0.1.7 publicada somente no catálogo de add-ons Home Assistant, sem merge dos PRs privados, Actions, instalação, ativação OAuth/webhook Meta, recebimento de DM real, envio Direct ou publicação de post. A versão 0.1.6 é o pacote anterior e não inclui Editorial integrado.

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
