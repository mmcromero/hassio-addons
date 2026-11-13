# Padrão para novos add-ons

## Organização

- Uma pasta por add-on diretamente na raiz, por exemplo `meu-addon/`.
- `repository.yaml` somente na raiz.
- `config.yaml` com `name`, `version`, `slug` único, `arch`, portas, opções e esquema.
- `Dockerfile` quando o Supervisor deve construir a imagem; `run.sh` quando necessário.
- `README.md` (loja), `DOCS.md` (operação) e `CHANGELOG.md` (versões).
- Não exigir `build.yaml` sem motivo: o Dockerfile pode usar imagem base explícita.

## Fluxo

1. Abrir branch isolada; não alterar a main diretamente.
2. Implementar e documentar caminhos de persistência, rede, credenciais e backup.
3. Fixar a tag de imagem upstream; confirmar suporte para a arquitetura desejada.
4. Rodar validações YAML, shell e build ARM64 na CI.
5. Abrir PR com riscos e evidências. Merge apenas após validação pertinente.
6. Testar no dispositivo real e registrar resultados. O build da CI não prova uso do WhatsApp.

Cada add-on tem sua própria versão SemVer e histórico. Não alterar outros add-ons em mudanças não relacionadas.

## Segurança

Não versionar `options.json`, tokens, senhas, bancos, sessões, backups, arquivos de mídia privados ou `.env`. Dados persistentes pertencem ao volume `/data`, não ao repositório. Evitar expor portas na Internet sem autenticação e TLS.

## Referências

- https://contributors.home-assistant.io/apps/guides/repository/
- https://contributors.home-assistant.io/apps/reference/files/
- https://github.com/home-assistant/developers.home-assistant/blob/master/docs/apps/configuration.md
