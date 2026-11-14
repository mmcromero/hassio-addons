# Changelog — Pager Virtual (Add-on Home Assistant)

Todas as mudanças relevantes e marcos de versão deste complemento são registrados neste arquivo.
Padrão de versionamento: [SemVer](https://semver.org/).

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
