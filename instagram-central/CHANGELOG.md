## 0.1.17 — HTTPS independente da origem do HA — 21/11/2026

- Adiciona listener TLS 1.2+ em 9443 com certificado/chave de `/ssl` montado somente para leitura; ativado ao preencher `public_base_url`. Certificados são relidos em novas conexões. Falhas não abrem HTTP público e preservam o listener interno 8099.
- Declara porta HTTPS e webui; mantém Ingress opcional e acrescenta links para janela própria no login/painel. Reutiliza Handler, autenticação, sessão, CSRF e `/data`, sem migração de dados nem segunda conta.
- Reconhece TLS nativo sem depender de X-Forwarded-Proto, mantendo Secure/HttpOnly/SameSite=Strict na sessão e SameSite=Lax nos cookies OAuth.
- Bloqueia OAuth se `meta_oauth_redirect_uri` divergir da origem independente; recusa Host antigo antes de iniciar/consumir autorização ou trocar código. Não altera Meta, webhook, NGINX, service worker do HA ou outros aplicativos.
- Chromium inclui worker sintético ativo na origem antiga e acesso na nova porta sem bypass, login real local, probe e autorização simulada. Instruções de certificado, porta/NAT e callback no README. Infraestrutura/Meta reais não foram alteradas nem homologadas.

## 0.1.16 — não perder cookies em campos HTTP separados — 21/11/2026

- Corrige perda comprovada de cookies quando um intermediário envia múltiplos cabeçalhos Cookie: o servidor lia só o primeiro. Agora reúne todos os pares antes de sessão, CSRF, probe e callback OAuth.
- Rejeição de cookie de state duplicado é mantida, inclusive entre campos separados; não escolhe arbitrariamente primeiro/último valor do state.
- Acrescenta à tela flags de cookie OAuth presente e múltiplos campos; log inclui somente contagem limitada, sem valores/nomes/nonce/state/códigos.
- Testes: 189 Python PASS; Chromium com nove cenários de probe, incluindo fragmentação no proxy, e regressões de abas concorrentes/configuração PASS. Provedor e infraestrutura simulados, sem Meta/HA real.
- Sem mudança em dados, esquema, tokens, atributos/path/TTL do cookie, Ingress/NGINX, opções ou demais add-ons. O teste real da 0.1.15 não provou fragmentação no HA; esta versão corrige a falha de parser reproduzida e permite verificar se ela explica o caso do operador.

## 0.1.15 — diagnóstico seguro e vínculo da configuração OAuth — 21/11/2026

- Sincroniza na fonte privada o probe e os testes da distribuição 0.1.14, preservando cookies por tentativa e identificação de versão.
- Diferencia ausência de cabeçalho Cookie de nome esperado ausente; mostra resultado e versão na tela do probe. Logs de emissão/retorno contêm somente flags, atributos fixos e contagem limitada, sem cookies, nonce, state, códigos OAuth, tokens, URLs ou segredos.
- Separa falhas HTTP, TLS, DNS, timeout, rede e JSON em `exchange_code`; registra apenas status e códigos/subcódigos inteiros saneados, descartando mensagens/corpos/cabeçalhos remotos. Preserva `redirect_uri` idêntico e resposta pública genérica.
- Adiciona fingerprint de configuração pública em `meta_oauth_states.authorization_context`, migração aditiva. Tentativa emitida com outro app/redirect/versão/negócio/conta é recusada antes do exchange; estados antigos em voo são invalidados, sem alteração de tokens, contas ou dados existentes.
- Testes locais: 185 Python PASS; Chromium com 8 cenários de cookie, duas abas concorrentes e config drift PASS. Sem Meta real, Actions ou build/instalação no HA nesta execução.
- Publicação autorizada pelo proprietário pela esteira rápida P0, somente `instagram-central/`, preservando slug, opções, arquitetura, Ingress, ícones oficiais e demais add-ons. O Supervisor executará o build durante a atualização do operador.
- Não declara a causa do transporte no HA corrigida nem OAuth homologado. Primeiro teste do operador: **Testar navegador e proxy (sem Meta)** na versão 0.1.15; nenhuma ativação de Meta/webhook/DM/posts integra esta entrega.

## Evidência de homologação — probe 0.1.14 falhou no navegador — 21/11/2026

- O Home Assistant mostra a versão `0.1.14` em execução.
- O proprietário executou **Testar navegador e proxy (sem Meta)**. O navegador chegou a `/oauth/meta/callback?probe=...`, mas recebeu `Cookie não retornou corretamente. Verifique navegador e proxy antes da autorização Meta.`
- No código, essa resposta é emitida quando `check_cookie_probe()` lança `OAuthError`; ainda não distingue, na tela, cookie ausente, duplicado, divergente ou nonce inválido.
- O log registra a causa fixa (`OAuth cookie probe failed: ...`) e `host_ok`/`https_ok`, sem registrar nonce ou valor do cookie. A linha do log ainda não foi coletada.
- A falha mostra que o teste automatizado anterior não reproduziu o transporte real do navegador: o teste HTTP injeta manualmente o cabeçalho `Cookie`, em vez de validar que o navegador armazenou e devolveu o `Set-Cookie` após o redirecionamento 302.
- **Próxima ação:** coletar a linha `OAuth cookie probe failed` nos logs do add-on e corrigir o ponto comprovado. Não alterar NGINX/Ingress nem opções por tentativa. Não repetir OAuth real. Mensagens e Editorial permanecem preservados.
## 0.1.14 — probe usa o mesmo cookie de estado do OAuth — 21/11/2026

- **Incidente:** após a atualização relatada para 0.1.13, o callback real continuou falhando em `parse_callback` com `OAuth browser state mismatch`, embora `redirect_authority_match=True` e `forwarded_https=True`.
- **Falha de cobertura identificada:** o teste `probe=1` ainda usava cookie fixo `ig_oauth_probe`, diferente do cookie derivado de `state` usado pelo OAuth 0.1.13. Portanto, o PASS anterior validava host/HTTPS/escopo genérico, mas não validava o mecanismo de cookie que falhava no callback.
- **Correção de diagnóstico:** o probe passa a emitir e validar `ig_oauth_state_<hash>` com valor sintético de 256 bits, usando exatamente `_state_cookie_name` e o mesmo leitor de cookie do callback. Não grava estado OAuth no SQLite e não acessa a Meta.
- **Identificação da versão:** `/health` passa a retornar `version: 0.1.14`; a página de probe informa a versão em execução, para confirmar que o Supervisor carregou a candidata.
- **Testes:** acrescentada cobertura unitária e HTTP para nome/valor derivados do state, cookie de outra tentativa, valor divergente, atributos e marcador de versão.
- **Segurança e escopo:** mantém `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/oauth/meta/callback`; sem mudança de NGINX, Ingress, opções, credenciais, banco, webhook, Direct, respostas automáticas ou publicações.
- **Publicação:** PR #67 mesclado em `main` em 21/11/2026, commit `418ca163c7534273c5d4ed906c835ac424d47d8b`.
- **Instalação:** tela de informações do Home Assistant consultada em 21/11/2026 mostra `Versão atual: 0.1.14` e estado `Em execução`. O manifesto não declara imagem pré-compilada; o Supervisor constrói pelo Dockerfile, que executa `py_compile` e `unittest` antes do runtime. O serviço em execução confirma que o gate de build foi ultrapassado; os logs individuais dos testes não foram capturados nesta consulta.
- **Homologação restante:** executar no navegador autenticado **Testar navegador e proxy (sem Meta)**. Não repetir OAuth real.
- **Consulta Supervisor via n8n:** workflow de leitura recebeu HTTP 401 com as credenciais disponíveis; não foi usado para confirmar a instalação. A confirmação foi feita pela tela Info do add-on no Home Assistant.

## 0.1.13 — isolamento do cookie de estado OAuth por tentativa — 20/11/2026

- Cada início OAuth gera um cookie com nome próprio derivado do SHA-256 do `state`; a callback valida somente o cookie correspondente ao estado recebido.
- Evita que duas tentativas/abas simultâneas sobrescrevam o mesmo cookie global. O log real anterior comprova um cookie presente e divergente, mas não comprova que concorrência foi a causa.
- Mantém o `state` aleatório de 256 bits, expiração de 10 minutos, consumo único no SQLite, comparação constante e atributos `Secure`, `HttpOnly`, `SameSite=Lax` e `Path=/oauth/meta/callback`.
- Sem alteração de NGINX, Ingress, opções, banco, credenciais, slug, porta, interface Mensagens/Editorial ou outros add-ons.
- Testes do módulo OAuth: 18/18 passaram em execução offline isolada com os arquivos do SHA de origem. Build do Dockerfile pelo Supervisor e teste real no HA ainda pendentes.
- Não repetir autorização Meta nem habilitar webhook, assinatura, envio de Direct, respostas automáticas ou publicações nesta etapa.

## 0.1.12 — diagnóstico de cookie OAuth e contexto do proxy — 20/11/2026

- **Distribuição:** versão 0.1.12 publicada em `mmcromero/hassio-addons:main/instagram-central/` em 20/11/2026. O build do Supervisor, a suíte integral do Dockerfile, a instalação e a homologação real continuam pendentes. A publicação não altera o Raspberry, NGINX ativo, opções ou credenciais.
- Inclui as correções já publicadas em 0.1.11: `redirect_uri` na troca do código, armazenamento por `account_registry.credential_root`, tratamento de erro de verificação e testes de regressão.
- Distingue no callback três situações sem registrar valores: cookie `ig_oauth_state` ausente, duplicado ou divergente do `state`.
- Adiciona teste de navegador e proxy **sem Meta**: `/oauth/meta/start?probe=1` exige a mesma autenticação administrativa, emite cookie temporário (60 s) com o mesmo escopo do OAuth e redireciona à rota pública existente de callback. A callback confirma cookie, host e HTTPS sem criar estado OAuth, trocar token ou abrir o Facebook.
- Exibe **Testar navegador e proxy (sem Meta)** na Central, em nova aba; nenhuma rota pública nova nem alteração de NGINX exigida.
- Registra apenas indicadores booleanos `redirect_authority_match` e `forwarded_https` para separar origem/Host e encaminhamento HTTPS do NGINX.
- Mantém `Path=/oauth/meta/callback`, `Secure`, `HttpOnly` e `SameSite=Lax`; não amplia o escopo do cookie sem evidência.
- Não altera configuração ativa do NGINX, Ingress, opções do Home Assistant ou painel da Meta. Não habilita mensagens, webhook, envio ou publicação.
- Testes dirigidos adicionados; execução ainda não comprovada nesta etapa.

## 0.1.11 — correção da troca de código OAuth Meta (redirect_uri obrigatório) — 20/11/2026

- **Diagnóstico da causa raiz (P0):** a requisição de troca de código por token de acesso (`oauth_meta.exchange_code`) para a Meta Graph API (`https://graph.facebook.com/{version}/oauth/access_token`) omitia o parâmetro `redirect_uri`. Conforme a especificação OAuth 2.0 (RFC 6749 §4.1.3) e as regras da Meta Graph API, quando `redirect_uri` é informado na autorização inicial (`/dialog/oauth`), o mesmo valor idêntico é obrigatório na requisição de troca do código. A ausência causava rejeição pela Meta (HTTP 400), levantando `OAuthError("Meta authorization exchange failed")` na etapa `exchange_code` e retornando ao navegador `{"error":"OAuth refused or expired"}`.
- **Correção da troca de código:** inclusão explícita de `"redirect_uri": cfg["meta_oauth_redirect_uri"]` nos parâmetros de `oauth_meta.exchange_code`, alinhado à documentação e ao endpoint de autorização.
- **Isolamento de credenciais multi-contas:** padronização da gravação de tokens criptografados (`store_token`) em `server.py` utilizando `account_registry.credential_root(...)`, assegurando compatibilidade retroativa para a conta primária `umdoislab` (`/data`) e isolamento nativo para futuras contas secundárias (`/data/accounts/<business_id>`).
- **Diagnóstico ampliado de conexão:** tratamento específico de `instagram_connection.ConnectionError` no callback para registro seguro do motivo da rejeição da conta Instagram nos logs sem expor tokens ou segredos.
- **Testes de regressão:** adicionados testes em `test_oauth_meta.py` e `test_http.py` comprovando envio do `redirect_uri` correto na chamada Graph API e sucesso de autenticação no fluxo ponta a ponta.
- **Compatibilidade:** preservados slug (`umdoislab_instagram`), SQLite, dados em `/data`, Ingress, portas, Editorial, Mensagens e arquitetura multi-contas. Sem migrações destrutivas.

## 0.1.10 — diagnóstico seguro de retorno OAuth e nova aba — 20/11/2026

- **Correção de experiência:** o link `Conectar Instagram pela Meta` abre em nova aba com `target="_blank"` e `rel="noopener noreferrer"`, evitando que a interface incorporada do Home Assistant tente abrir a autorização Meta dentro de iframe.
- **Diagnóstico de falha real:** a Meta retornou a `/oauth/meta/callback`, mas a Central exibiu `OAuth refused or expired`; a conta permaneceu não verificada. O callback agora registra **somente a etapa interna** de falha (`parse_callback`, `consume_state`, `exchange_code`, `verify_instagram_account` ou `store_credential`) e uma razão interna segura. A resposta pública continua genérica e não expõe credenciais.
- **Teste de regressão adicionado:** valida presença de nova aba e mensagem de etapa `exchange_code` sem imprimir state ou código OAuth. O teste foi incluído na suíte de build do Supervisor, mas sua execução ainda precisa ser comprovada no hardware alvo.
- **Compatibilidade:** preservar slug, nome da loja, `ingress`, portas, opções, chaves, credenciais, bancos, mídias, Mensagens, Editorial e demais add-ons. Sem migração destrutiva. Não habilita publicações externas nem respostas automáticas.
- **Esteira:** procedimento `hassio-addons/CONTRIBUTING.md` P0. Sem Actions. Publicação no catálogo e instalação no Supervisor são fases separadas.

## 0.1.9 — correção de falha de compilação no Supervisor (hotfix) — 20/11/2026

- **Erro real confirmado:** a atualização 0.1.8 falhou no passo Dockerfile `python3 -m py_compile`, em `tests/test_http.py:224`: `SyntaxError: bytes can only contain ASCII literal characters`. Nenhum teste da 0.1.8 foi executado pelo Supervisor após essa falha.
- **Correção restrita:** troca `b'aria-label="Módulos"'` por `'aria-label="Módulos"'.encode("utf-8")`, mantendo a verificação exata do cabeçalho. A origem foi inspecionada nos 22 arquivos Python da candidata; não foram encontrados outros literais bytes com caracteres não ASCII pelo verificador textual (não equivale ao `py_compile` integral).
- **Identidade e compatibilidade:** incremento de versão 0.1.8 → 0.1.9; sem alteração nos módulos de execução, Dockerfile, login, bancos, dados persistidos, SVG/PNG, slug, arquitetura, opções ou Meta.
- **Esteira:** seguir `hassio-addons/CONTRIBUTING.md` P0; sem GitHub Actions ou build ARM64 externo obrigatório. A prova final será o build e suíte no Supervisor durante a atualização autorizada.

## 0.1.8 — patch privado de UX e legendas locais (NÃO PUBLICADO/INSTALADO) — 20/11/2026

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
- **Situação:** desenvolvimento em branch privada `feat/instagram-editorial-ux-patch-001`, sem merge, publicação, atualização Home Assistant, ativação Meta ou GitHub Actions. A 0.1.7 foi publicada no catálogo (commit `b39f9edf2772f295d13180b456ff040271071329`), instalada e teve abertura visual e H01 aprovados **por relato do proprietário**; H02 passou por relato, com falha de preservação da agenda registrada.
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
