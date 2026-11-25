# Design System Lab — laboratório temporário

App experimental para executar a validação do repositório privado mmcromero/design-system no Home Assistant OS ARM64 e disponibilizar a Demo pelo Ingress.

## Segurança e escopo

- O código privado é baixado em tempo de execução; nenhum arquivo do Design System é copiado para este catálogo público.
- Requer Fine-grained PAT limitado ao repositório design-system, com permissão **Contents: Read-only**.
- O token fica somente em /data/options.json, gerenciado pelo Supervisor e mascarado na UI de configuração. Não é devolvido pela API do app, escrito no log ou incluído no Git.
- O app não tem Docker socket, HA API, Supervisor API, host network, host mounts ou portas publicadas. A interface usa Ingress e é restrita a administradores.
- O executor clona somente a branch desenvolvimento, registra o SHA exato e executa o script de validação do próprio repositório.
- A Demo só fica disponível depois de build e testes automatizados concluírem com sucesso.
- O código de teste roda dentro do container isolado do app, sem privilégios adicionais ou acesso aos arquivos do host.

## Instalação e uso

1. Instale o app pela loja central mmcromero/hassio-addons.
2. Crie um Fine-grained PAT no GitHub com acesso somente ao repositório design-system e permissão Contents: Read-only.
3. Em Configuração do app, preencha github_read_token. Não compartilhe o valor.
4. Inicie o app e abra Design System Lab pelo Ingress.
5. Clique em Executar validação. O executor faz clone raso da branch desenvolvimento, registra o SHA, executa npm ci, quatro builds, o build da Demo com caminhos relativos, Vitest (66 testes esperados) e Playwright/Chromium.
6. Após PASS, use Abrir Demo para homologação manual e execute SR-07 integrado e SR-08 a SR-11 com Narrador do Windows + Chrome.
7. Baixe o log para evidência, se necessário. Revise e sanitize antes de registrar no Git.

## Construção ARM64

O Supervisor constrói a imagem no Raspberry Pi durante instalação/atualização porque o manifest não declara uma imagem pré-compilada. A imagem usa Node.js 22 oficial sobre Debian Bookworm slim, sem S6. O servidor Node é o processo PID 1 do container; Playwright 1.57.0/Chromium é instalado no build ARM64. A ausência de um job QEMU/Actions dedicado não substitui nem impede o build real no hardware alvo.

## Limpeza

Ao final, pare e desinstale o app pelo Supervisor. Ele não cria dados persistentes de projeto; checkout, build e evidências ficam no filesystem efêmero do container. A remoção do app não altera os demais add-ons. A pasta pública do catálogo pode permanecer como utilitário experimental, até decisão de aposentadoria própria.
