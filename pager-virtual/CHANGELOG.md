# Changelog — Pager Virtual (Add-on Home Assistant)

Todas as mudanças relevantes e marcos de versão deste complemento são registrados neste arquivo.
Padrão de versionamento: [SemVer](https://semver.org/).

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
