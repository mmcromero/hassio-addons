# Portal de Governança — add-on Home Assistant

Painel central de portfólio, evidências e homologações do ecossistema mmcromero. Interface web acessada pelo Home Assistant Ingress.

## Estado da candidata

- Versão: `0.1.0-dev.5`
- Arquitetura: `aarch64` (Raspberry Pi 4)
- Ingress: porta interna `8099`; sem portas publicadas no host.
- Identidade: `Fábrica de Ideias - Portal de Governança`.
- Ícone e logotipo: `icon.png` e `logo.png` incluídos na distribuição.

## Segurança

- Ingress obrigatório, painel restrito a administradores.
- O servidor aceita somente conexões do proxy Supervisor em `172.30.32.2` e exige o cabeçalho `X-Ingress-Path`.
- GitHub é opcional; token Fine-grained somente leitura é informado nas opções do app.
- Não solicita API do Supervisor/Home Assistant, Docker API, host network ou permissões privilegiadas.
- Nenhuma rota para escrita GitHub, Supervisor ou n8n.

## Acesso

Abra o app pelo botão **Abrir interface** na página do app no Home Assistant. O endereço de Ingress é dinâmico e não deve ser substituído por uma rota inventada como `/app/<slug>`.

## Proveniência

A fonte canônica é `mmcromero/portal-governanca`, branch `desenvolvimento`. O pacote deste catálogo é somente a distribuição autorizada; não é uma segunda fonte de código.
