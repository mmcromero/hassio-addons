# Histórico de versões

## 0.1.0 — candidato inicial

- Home Assistant OS `aarch64`.
- Evolution API `v2.3.7` fixada; PostgreSQL integrado e cache local.
- Configuração de chave, endereço público e webhook via Supervisor.
- Persistência do banco e das sessões em `/data`.
- **Pendente:** smoke test de inicialização PostgreSQL + API na CI e homologação no Raspberry Pi 4, incluindo QR, mídias, webhook e restauração.
