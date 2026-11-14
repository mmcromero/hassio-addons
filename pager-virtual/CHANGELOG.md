# Changelog — Pager Virtual (Add-on Home Assistant)

Todas as mudanças relevantes e marcos de versão deste complemento são registrados neste arquivo.
Padrão de versionamento: [SemVer](https://semver.org/).

---

## [Próxima entrega — em desenvolvimento, NÃO publicada]
- Teste HTTP integrado de revogação de KDS aprovado: operador desativado perde a conexão SSE antes do próximo pedido; KDS do gerente continua recebendo notificações. Sem homologação no proxy externo real.
- Segurança SSE do KDS: a sessão é revalidada antes de cada evento; terminal desativado deixa de receber imediatamente o próximo aviso, mesmo antes do heartbeat de 25 segundos. Teste de isolamento e revogação aprovado na CI.
- Corrigido o ciclo de vida das conexões SSE para assumir explicitamente a resposta no Fastify e limpar heartbeat ao desconectar. Teste HTTP real aprovado: KDS recebe pedido novo e KDS/cliente recebem transição para pronto. CI aprovada; sem teste ainda no proxy do Raspberry Pi.

- Adicionada verificação de execução da imagem ARM64: inicialização HTTP, escrita SQLite em `/data`, reinício do contêiner e recuperação dos mesmos registros. Etapa `Smoke da imagem ARM64 com volume persistente e reinício` concluída com sucesso no job `build-pager-arm64` (execução 43590737190).

- Teste automatizado de segurança de dados aprovado: backup SQLite pela API nativa com conexão WAL aberta, verificação de integridade, restauração isolada, migração aditiva, preservação de 120 pedidos e simulação de retorno ao backup anterior. **Banco real do Home Assistant não testado.**

- Após a migração, gerente de restaurante preservado consegue entrar e consultar os pedidos antigos ainda ativos; pedido entregue permanece armazenado sem reaparecer no KDS. Teste integrado aprovado.
- Migração aditiva do SQLite 0.1.3 validada em CI: preservados integralmente restaurante, pedidos (em preparo/pronto/entregue), números, tokens, datas e status; novas tabelas de usuários e sessões criadas sem credenciais padrão. Sem execução sobre o banco real do Raspberry Pi.

- Teste de configuração `PUBLIC_URL=https://...` aprovado: login HTTP local sem `Secure`, login pela origem HTTPS declarada com cookie `Secure`, e rejeição de origem externa. Teste automatizado, sem validação do proxy real.

- Teste integrado com servidor real aprovado no GitHub Actions: dois restaurantes, Master Admin, gerentes, terminais, criação e alteração de pedidos, bloqueio cruzado e revogação de sessão. Sem homologação no Home Assistant.

- Teste automatizado de primeiro acesso concluído no add-on: cadastro único, bloqueio de domínio público, login e autorização do painel. **Homologação no Raspberry Pi/HTTPS real ainda pendente.**

- A próxima versão reunirá a correção 0.1.4 do KDS e a autenticação por Master Admin, gerente e terminal operacional.
- O primeiro acesso planejado usa um código temporário nos logs privados do Home Assistant para criar o Master Admin, sem senha padrão.
- Segurança adicional do primeiro acesso: verificação de origem, hostname local e IP privado para impedir que um proxy público seja confundido com acesso local.
- Smoke de primeiro acesso incluído no add-on: inicia o servidor, testa código temporário, bloqueia origem externa e segundo cadastro, valida login e acesso ao painel. Teste automatizado aprovado na esteira do PR #19; teste no Raspberry Pi e no proxy real continua pendente.
- O backend em desenvolvimento já contém sessões revogáveis e isolamento de pedidos/SSE por restaurante; a homologação final ainda está pendente.
- O gerente poderá administrar terminais e redefinir suas senhas; a troca da própria senha revoga sessões anteriores.
- Código e testes da branch `feat/auth-restaurantes-fundacao` foram sincronizados para `feat/pager-auth-staging` neste repositório. **Não estão integrados à main nem distribuídos no Home Assistant.**
- Pendências: testes integrados, fluxo de primeiro acesso no HA, validação HTTPS/proxy, verificação da sincronização final, compilação ARM64, homologação e atualização final de versão.

---

## [0.1.4] — 14/11/2026

### Corrigido
- **KDS sem pedidos ao abrir ou atualizar:** removida a referência ao contador de simulação `orderCounter` do carregamento inicial. A variável inexistente interrompia a renderização mesmo após a API devolver os pedidos salvos no SQLite.
- A criação de outro pedido fazia a lista reaparecer porque o evento SSE executava novamente a renderização.
- Acrescentado teste de regressão no repositório principal para impedir a volta do contador antigo.

### Preservação e validação
- Não apaga pedidos, tokens, banco SQLite nem configurações da instalação anterior.
- O teste visual no Home Assistant após atualização ainda precisa confirmar a correção no aparelho real.

---

## [0.1.3] — 14/11/2026

### Adicionado
- Cadastro manual de pedidos no KDS pelo número da senha, com criação real no SQLite.
- QR Code por pedido com token exclusivo e opção de impressão e reimpressão pelo navegador.
- Campo `public_url` nas configurações do add-on para gerar links de clientes com endereço configurado, aplicável ao reiniciar.

### Alterado
- Eliminados o botão de simulação e os dados fictícios da operação normal.
- Página de acompanhamento adaptada a pedidos sem lista de produtos.

### Limitações atuais
- O KDS ainda não possui login e isolamento por restaurante; não expor as rotas operacionais na internet.
- O endereço público configurado não substitui a configuração de proxy/DNS/HTTPS e exige testes de acesso no celular.

---

## [0.1.2] — 14/11/2026

### Adicionado
- Melhorias de alerta ao cliente: Screen Wake Lock, gerador de áudio de fundo, timbre de alarme e vibração aprimorada.
- A eficácia com o celular bloqueado depende do navegador e deve ser homologada em dispositivos reais.

---

## [0.1.1] — 14/11/2026

### Corrigido
- **Eliminação do conflito `s6-overlay-suexec: fatal: can only run as pid 1`:**
  - Ajustado `init: false` no `config.yaml` seguindo a arquitetura de produção homologada do Artesão Digital.
  - O container agora executa `node src/server.js` diretamente como PID 1 nativo, sem camadas intermediárias.
- **Simplificação e remoção de duplicidade de portas:**
  - Removido o campo redundante `port` da seção `options` no `config.yaml`.
  - O mapeamento de porta agora é gerenciado exclusivamente pela seção nativa `ports` ("Rede") do Home Assistant OS, permitindo ao usuário definir portas customizadas (ex: `8090`, `8095`, `8096`) sem conflitos internos.
- **Dockerfile otimizado:**
  - Imagem base migrada para `node:20-alpine` (ARM64) com build direto e limpo.

---

## [0.1.0] — 14/11/2026

### Adicionado
- **Lançamento inicial do complemento Pager Virtual para Home Assistant OS:**
  - Backend ultraleve em Node.js com Fastify (< 40 MB de RAM).
  - Persistência em banco de dados SQLite com modo WAL ativo, armazenando dados na partição persistente `/data`.
  - Gerenciador de eventos em tempo real via **Server-Sent Events (SSE)** nativo (`/api/pedidos/stream/:token` e `/api/kds/stream`).
  - Frontend integrado servido pelo próprio add-on:
    - `kds.html`: Painel de Cozinha/Balcão multi-pedidos com fila cronológica rigorosa FIFO e botões de chamada/finalização.
    - `cliente.html`: Arquitetura "Página Casca" (< 50 KB) com leitura de dados estáticos diretamente dos parâmetros da URL/QR Code e alertas multissensoriais (Web Audio API, vibração ritmada e Edge Lighting amarelo neon).
  - Manifesto `config.yaml`, script `run.sh` e `Dockerfile` com compilação de dependências nativas C++ para arquitetura `aarch64` (Raspberry Pi 4) e `amd64`.
