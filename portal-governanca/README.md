# Portal de Governança — add-on Home Assistant

Add-on independente para Home Assistant OS, acessado exclusivamente pelo Ingress. A pasta é um artefato de distribuição gerado pelo repositório-fonte portal-governanca; não é uma segunda fonte de código.

## Segurança

- Somente aarch64 nesta candidata, alvo Raspberry Pi 4.
- Ingress obrigatório, painel restrito a administradores e sem portas publicadas.
- O servidor aceita somente conexões do proxy Supervisor em 172.30.32.2 e exige o cabeçalho X-Ingress-Path válido.
- Sem login Basic duplicado no Ingress.
- GitHub é opcional; token Fine-grained somente leitura é informado nas opções do add-on e permanece no servidor.
- Não solicita hassio_api, homeassistant_api, Docker API, host network ou permissões privilegiadas.
- Nenhuma rota para escrita GitHub, Supervisor ou n8n.
- O health check local em /healthz não retorna configuração nem credenciais.

## Instalação e homologação

Versão instalada: `0.1.0-dev.14` no Home Assistant OS aarch64 (Raspberry Pi 4). O Supervisor confirmou build ARM64 concluído, execução encadeada de `npm ci`, build do Design System, `npm test` e TypeScript/Vite, app `started` e sem atualização pendente. A homologação visual/funcional pelo botão **Abrir interface** permanece como verificação separada. O endereço de Ingress é dinâmico; não use rotas inventadas como `/app/<slug>`.
