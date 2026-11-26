# Portal de Governança — add-on Home Assistant

Add-on independente para Home Assistant OS, acessado exclusivamente pelo Ingress. A pasta é um artefato de distribuição gerado pelo repositório-fonte portal-governanca; não é uma segunda fonte de código.

## Segurança

- Somente aarch64 nesta candidata, alvo Raspberry Pi 4.
- Ingress obrigatório, painel restrito a administradores e sem portas publicadas.
- O servidor aceita somente conexões do proxy Supervisor em 172.30.32.2 e exige o cabeçalho X-Ingress-Path válido.
- Sem login Basic duplicado no Ingress.
- GitHub é opcional; token Fine-grained somente leitura é informado nas opções do add-on e permanece no servidor.
- Cadastro de projetos usa, se configurado, token Fine-grained separado (`github_write_token`) com Metadata read e Contents read/write; a única escrita é criar o marcador `.portal-governanca.json` em repositório do owner autorizado.
- Não solicita hassio_api, homeassistant_api, Docker API, host network ou permissões privilegiadas.
- Não há rotas de escrita GitHub além do cadastro controlado do marcador; sem escrita Supervisor ou n8n.
- O health check local em /healthz não retorna configuração nem credenciais.

## Instalação e homologação

Versão publicada candidata: `0.1.0-dev.23`. A atualização no Home Assistant OS aarch64 (Raspberry Pi 4) será confirmada pelo Supervisor após a publicação. A homologação visual/funcional pelo botão **Abrir interface** permanece como verificação separada. O endereço de Ingress é dinâmico; não use rotas inventadas como `/app/<slug>`.
