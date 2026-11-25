# Changelog — Portal de Governança (add-on)

## 0.1.0-dev.3 — 25/11/2026

- Corrige PATH do processo isolado para localizar Node 22 em /usr/local/bin.
- Mantém whitelist de ambiente e remoção das credenciais Supervisor.

## 0.1.0-dev.2 — 25/11/2026

- Corrige a imagem-base ARM64 para Node 22 Alpine explícita, sem depender de BUILD_FROM.
- Inclui Bash no runtime para executar o entrypoint /app/run.sh.
- Mantém acesso exclusivo por Ingress e permissões mínimas.

## 0.1.0-dev.1 — 25/11/2026

- Primeira configuração de add-on para Home Assistant OS.
- Acesso por Ingress, restrito ao proxy Supervisor.
- Painel administrativo; sem portas externas.
- Token GitHub opcional, somente leitura, por opções protegidas do add-on.
- Sem permissões Supervisor adicionais e sem integração n8n nesta fase.
- Bundle da interface gerado a partir do Design System fixado por SHA e incluído no pacote de distribuição como artefato compilado.
