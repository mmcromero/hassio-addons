## 0.1.5 — login HTML no Chrome (experimental) — 20/11/2026
- Substitui o desafio HTTP Basic do painel Ingress por tela HTML com usuário `admin` e senha `panel_password` existente.
- O formulário inclui `autocomplete=username` e `autocomplete=current-password`, permitindo ao Chrome oferecer salvamento/preenchimento; mantém autenticação Basic legada somente nas rotas administrativas.
- Sessões aleatórias de 12 horas, digest HMAC no SQLite, cookies HttpOnly/SameSite=Strict, Secure quando o acesso externo é HTTPS, logout e limite de tentativas.
- Mantém os formulários administrativos protegidos por CSRF, não altera credenciais, banco existente, slug, marca ou ícones.
- Acrescenta testes de login/sessão e contratos HTTP no Dockerfile para validação durante futuro build no Supervisor.
- OAuth Meta, webhook e rascunhos continuam **desativados por padrão**. Não há mensagens automáticas nem alteração de WhatsApp/n8n/NGINX.
- Publicação no catálogo **não instala** o aplicativo; a atualização no Raspberry e a homologação exigem etapa própria. Para salvar senhas no Chrome, preferir a URL HTTPS existente do Home Assistant.

## 0.1.4 — correção do teste de build da 0.1.3 — 20/11/2026
- Corrige o teste HTTP `test_get_routes_do_not_shadow_urlsplit`: ele esperava 503 de um webhook com `ingress_enabled=true`; nesse estado o servidor rejeita a requisição incompleta com 403. O teste agora desativa o webhook antes de verificar 503.
- Nenhuma modificação nas rotas, no banco de dados, na integração OAuth ou em serviços externos.
- A atualização 0.1.3 do Home Assistant falhou com `unknown error while trying to build the image`; o log inicial continha exceções do processo anterior 0.1.2. **O log completo do Supervisor recebido depois confirmou a causa do build**: 28 testes executados, 27 aprovados e 1 falhou no `test_get_routes_do_not_shadow_urlsplit` (linha 90: `AssertionError: 403 != 503`), levando o Dockerfile a terminar com exit code 1.
- **Publicação no catálogo não é instalação nem homologação real no Home Assistant.** Manter OAuth, webhooks e automações desativados.

## 0.1.3 — correção 502 da interface Ingress — 20/11/2026
- Corrige `UnboundLocalError` em todas as rotas GET: `urlsplit` deixou de ser uma variável local sombreada no `Handler.do_GET`.
- Acrescenta teste HTTP de regressão para `/health`, `/panel` e webhook desativado, executado no build local do Supervisor.
- Mantém `meta_oauth_enabled: false`, `ingress_enabled: false`, `drafts_enabled: false` como padrões; preserva o mesmo slug, o volume SQLite e a identidade do add-on.
- **A publicação do hotfix não instala a versão no Raspberry e não autoriza alterar NGINX nem habilitar integrações.**

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
