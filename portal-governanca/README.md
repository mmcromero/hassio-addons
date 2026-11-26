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

Versão instalada: `0.1.0-dev.13` no Home Assistant OS aarch64 (Raspberry Pi 4). O Supervisor concluiu o build ARM64; `npm ci`, compilação do Design System, suíte de testes (15/15) e TypeScript/Vite passaram. O app está `started` e sem atualização pendente. A homologação visual/funcional pelo botão **Abrir interface** permanece como verificação separada. O endereço de Ingress é dinâmico; não use rotas inventadas como `/app/<slug>`.
