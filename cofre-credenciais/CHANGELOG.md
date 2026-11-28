# Changelog — Cofre de Credenciais

## 0.1.0-rc.2 — 2026-11-27

- Corrigida dependência NGINX para Debian Trixie security `1.26.3-3+deb13u11`, alinhada com `nginx-common` disponível no repositório.

## 0.1.0-rc.1 — 2026-11-27

- Primeira distribuição própria no catálogo mmcromero/hassio-addons.
- Base do wrapper Home Assistant Community App Vaultwarden (MIT), commit `de6e0aa5193634a3f3da79bf78905aa320ce4b2c`.
- Servidor Vaultwarden `1.37.5`, imagem multi-arquitetura fixada por digest.
- Cadastro, convites, Sends, SSO signup, organizações e painel administrativo desativados por padrão.
- Removida a geração/exibição de token administrativo nos logs.
- Porta 7277 sem mapeamento para o host; acesso previsto exclusivamente por proxy HTTPS dedicado.
- Opção de cadastro temporário para bootstrap da conta proprietária.
- Domínio público configurável por opção do app.
- POC ainda não homologada; somente dados sintéticos.
