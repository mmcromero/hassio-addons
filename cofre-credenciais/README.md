# Fábrica de Ideias — Cofre de Credenciais

Distribuição Home Assistant do Vaultwarden, com configuração de segurança e operação mantida por mmcromero.

- Pacote: `0.1.0-rc.2`
- Vaultwarden: `1.37.5` (imagem fixada por digest)
- Arquiteturas: ARM64 e AMD64
- Acesso: hostname HTTPS dedicado via NGINX; sem Ingress e sem publicação direta da porta do serviço.
- Cadastro, convites, Sends, SSO signup e painel administrativo desativados por padrão.

Consulte [DOCS.md](DOCS.md) antes de instalar ou configurar. Esta RC deve ser homologada com dados fictícios; não cadastrar credenciais reais antes da aprovação de backup/restore e segurança.

Baseado no [Home Assistant Community App Vaultwarden](https://github.com/hassio-addons/app-vaultwarden) (MIT) e no [Vaultwarden](https://github.com/dani-garcia/vaultwarden) (AGPL-3.0). Não é um produto oficial da Bitwarden.
