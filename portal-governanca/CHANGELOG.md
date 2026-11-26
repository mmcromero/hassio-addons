# Changelog — Portal de Governança (add-on)

## 0.1.0-dev.10 — 25/11/2026

- Corrige testes com quebras de linha válidas e rejeita explicitamente prefixos de Ingress com token de sessão divergente.

## 0.1.0-dev.9 — 25/11/2026

- Corrige a separação das instruções COPY no Dockerfile multi-stage; mantém build npm e testes no Supervisor.

## 0.1.0-dev.8 — 25/11/2026\n\n- Remove a dependência de checkout irmão do Design System; inclui snapshot somente leitura no SHA fixado.\n- Move compilação do Design System, testes do Portal e build Vite para estágio multi-stage do Dockerfile executado pelo Supervisor.\n- O pacote de distribuição leva fontes, lockfile e proveniência; a imagem runtime recebe somente o frontend compilado e backend.\n- Mantém testes, validações de segurança, identidade e Ingress.\n\n## 0.1.0-dev.7 — 25/11/2026

**Estado:** candidata na branch `desenvolvimento`; build/test/package e instalação HA ainda não comprovados.

- Substitui o catálogo estático de quatro projetos pela descoberta opt-in via `.portal-governanca.json`.
- Lista os repositórios do proprietário autorizado, examina a raiz da branch padrão e ignora os que não possuem o marcador.
- Agrupa repositórios pelo mesmo `project.id`; não inclui projetos desativados.
- Exibe estado vazio quando nenhum projeto foi identificado.
- Mantém GitHub somente leitura e token exclusivamente no servidor.

## 0.1.0-dev.5 — 25/11/2026

- Inclui `icon.png` quadrado e `logo.png` horizontal, conforme o padrão de apresentação dos apps Home Assistant.
- Empacotador passa a incluir os dois arquivos de identidade no artefato de distribuição.
- Não altera o runtime nem as permissões do Portal.

## 0.1.0-dev.4 — 25/11/2026

- Remove `ingress_entry: /` redundante: a página inicial já está na raiz e o Supervisor acrescenta esse valor ao URL base, produzindo uma barra duplicada.
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


## 0.1.0-dev.8 — 25/11/2026

- Remove a dependência de checkout irmão do Design System; inclui snapshot somente leitura no SHA fixado.
- Move compilação do Design System, testes do Portal e build Vite para estágio multi-stage do Dockerfile executado pelo Supervisor.
- O pacote de distribuição agora leva fontes, lockfile e proveniência; a imagem runtime recebe somente o frontend compilado e backend.
- Não reduz testes nem remove validações de segurança; falhas de npm ci, testes ou build interrompem a construção da imagem.
