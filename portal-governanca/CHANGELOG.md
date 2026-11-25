# Changelog — Portal de Governança

## 0.1.0-dev.6 — 25/11/2026

- Corrige compatibilidade do Ingress quando o proxy preserva ou remove o prefixo dinâmico antes de encaminhar ao app.
- Mantém validação do peer confiável e do cabeçalho `X-Ingress-Path`.
- Não declara `ingress_entry`; entrada permanece na raiz.
- Acrescenta testes para raiz, barra final, assets, API e caminhos internos nos dois formatos.

## 0.1.0-dev.5 — 25/11/2026

- Inclui `icon.png` quadrado e `logo.png` horizontal no padrão de apresentação dos apps Home Assistant.
- Corrige o empacotador de origem para incluir os dois assets.
- Não altera o runtime nem as permissões do Portal.

## 0.1.0-dev.4 — 25/11/2026

- Remove `ingress_entry: /` redundante: a página inicial já está na raiz e o Supervisor concatena esse valor ao URL base, produzindo `//`.
- Mantém Ingress na porta 8099, sem publicar portas no host.

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
