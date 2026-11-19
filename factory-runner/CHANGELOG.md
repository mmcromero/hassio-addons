# Changelog

## 0.1.0-rc.2 — Candidata de pré-verificação multi-projeto (19/11/2026)

- Factory Runner permanece add-on independente do Avisaqui.
- Perfis JSON por projeto; Avisaqui é somente o primeiro perfil registrado.
- API autenticada somente leitura: lista de projetos e preflight por SHA fixado.
- Dockerfile incorpora Git, CLI de preflight e perfis versionados.
- Operações de publicação, push/merge e alteração autônoma permanecem bloqueadas.
- Porta externa 9876 continua não mapeada e bind localhost; nenhum deploy.

**NÃO testado em ARM64 ou HA. Requer checkouts previamente provisionados para usar o preflight. Não realiza fechamento de pacote.**


## 0.1.0-rc.1 — Candidato restrito (18/11/2026)

- Integração estrutural ao catálogo central Home Assistant.
- Registro próprio no cadastro da loja e na seleção de build ARM64 manual.
- API com autenticação obrigatória e operações privilegiadas bloqueadas.
- Remoção de credenciais fixas e redução de dependências e volumes.
- Testes de regressão de segurança incluídos para execução isolada.

**Não homologado no hardware. Não equivale à versão funcional do worker.**
