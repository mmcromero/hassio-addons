# Changelog

## 0.1.0-dev.43 — 27/11/2026
- Centraliza homologações, evidências, decisões/histórico e recursos no contexto de cada projeto.
- Adiciona seletor universal de projeto e rotas recarregáveis, com filtros no backend para registros e missões.
- Mantém Missões, Automações, Ambientes e Agentes como áreas globais, com filtro contextual.
- Adiciona links diretos ao GitHub nos cards e links de recursos do repositório; inclui inventário inicial Cloudflare/Artesão Digital com proveniência e data de observação.
- Adiciona testes de navegação e isolamento por projeto.

## 0.1.0-dev.42 — 27/11/2026
- Gera relatório JSON do build ARM64 somente após a suíte Vitest, o build do Design System e a compilação TypeScript/Vite concluírem com sucesso.
- Vincula o relatório ao SHA do Portal, SHA do Design System, versão do add-on, digest do lockfile, arquitetura e versão Node.
- Exibe na área Homologações a contagem real de testes/suítes aprovados, falhos e pendentes, sem converter build em homologação funcional.
- Adiciona testes para validação estrita da proveniência e do resultado do build.

## 0.1.0-dev.41 — 27/11/2026
- Na tela Cadastrar projeto, lista os repositórios já cadastrados primeiro.
- Agrupa separadamente os repositórios ainda disponíveis para cadastro e os que estão em outros estados (marcador inválido/desativado, arquivado ou indisponível).
- Aplica a mesma ordem no seletor do formulário; repositórios já cadastrados continuam desabilitados para evitar cadastro duplicado.
- Ordena alfabeticamente dentro de cada grupo e não altera os dados recebidos do GitHub.
- Adiciona testes unitários para prioridade, estabilidade dos dados e grupos apresentados na interface.

# Changelog

## 0.1.0-dev.40 — 27/11/2026
- Acrescenta ao contexto de nova conversa a última Issue criada em cada repositório relacionado: número, título, estado, link, datas de criação e atualização.
- Orienta o agente a abrir a Issue e ler seus comentários antes de iniciar o trabalho, confirmando se ela continua sendo a mais recente.
- Distingue repositório sem Issues de consulta indisponível; não declara ausência quando a consulta falha ou a primeira página está ocupada por Pull Requests.
- Obtém a Issue mais recente pela API de Issues do GitHub, sem depender da Search API.
- Adiciona testes para composição do prompt e descoberta da Issue.

# Changelog

## 0.1.0-dev.39 — 27/11/2026
- Adiciona link “Conversar sobre este projeto” em todos os cards.
- Abre uma nova conversa no ChatGPT Web com resumo limitado do projeto, status, justificativa, idade e referências GitHub.
- Não inclui credenciais, tokens ou conteúdo privado dos repositórios; orienta o ChatGPT a verificar acesso antes de assumir que pode ler repositórios privados.
- Limita o tamanho do contexto e a quantidade de repositórios para evitar URLs excessivamente longas.
- Adiciona testes unitários para composição, codificação e limites do prompt.

# Changelog

## 0.1.0-dev.38 — 27/11/2026
- Adiciona etiqueta automática de ciclo de vida aos cards: EM DESENVOLVIMENTO, EM TESTE, HOMOLOGADO, FINALIZADO e CANCELADO.
- Usa commits, Pull Requests não rascunho, workflows ativos, releases prévias, homologações PASS e eventos terminais explícitos.
- Exibe STATUS NÃO IDENTIFICADO quando as evidências não permitem classificação segura.
- Adiciona registro explícito de cancelamento no histórico do projeto; finalização e cancelamento são estados terminais distintos.
- O contador de idade congela também no cancelamento.
- Adiciona testes unitários para classificação, precedência e desfechos.

# Changelog

## 0.1.0-dev.37 — 26/11/2026
- Exibe a idade em dias nos cards de todos os projetos, reutilizando a timeline histórica existente.
- Carrega os históricos de forma sequencial; atualiza os contadores automaticamente a cada minuto.
- Usa somente inícios confirmados ou estimados; marca estimativas com ≈ e não calcula idade quando a confiança é desconhecida.
- Congela o contador em encerramento explícito registrado no ledger.
- Adiciona testes unitários para início confirmado, estimado, desconhecido, ausência de início e encerramento.

## 0.1.0-dev.36 — 26/11/2026
- Corrige o fixture do teste multi-projeto para extrair owner/repository sem incluir o sufixo do endpoint.
- Mantém a implementação da timeline e toda a cobertura de segurança; repetir o build/testes no Supervisor ARM64 antes de homologar.

## 0.1.0-dev.35 — 26/11/2026
- Implementa histórico cronológico por projeto com coleta GitHub incremental, persistência append-only e deduplicação no ledger existente.
- Registra criação de repositório, primeiro commit, primeira Issue/PR, primeira release e marcos significativos com links e confiança explícita.
- Agrega dias ativos por data local de São Paulo, sem exibir cada commit; preserva cursor por repositório e sinaliza histórico parcial.
- Exibe início, existência, período com atividade, dias ativos e tempo desde o último marco; contador atualiza automaticamente a cada minuto.
- Permite registrar encerramento explícito e congelar o contador; não infere encerramento por inatividade.
- Adiciona testes para evidências, paginação, atualização incremental, início desconhecido, múltiplos projetos, BRT, deduplicação e encerramento. A primeira construção no Supervisor executou 82 testes: 81 passaram e 1 falhou por erro no fixture de caminho do cenário multi-projeto; a correção está na dev.36.

## 0.1.0-dev.33 — 26/11/2026
- Adiciona seção Missões para cadastrar e consultar prompts de ativação.
- Adiciona API `GET/POST /api/v1/missions` e persistência append-only no ledger com estado inicial `received`.
- Valida prompts, bloqueia padrões conhecidos de credenciais e preserva prompts UTF-8 de até 8.000 caracteres.
- Adiciona testes de persistência, limites, UTF-8, preservação do prompt e integração arquitetural. Testes/build desta versão ainda não executados.

## 0.1.0-dev.27 — 26/11/2026
- Implementa a Fase 6B: Protocolo de Comunicação de Agentes e Portal como Centro de Comando.
- Corrige compatibilidade de abertura cross-platform do ledger NDJSON (`O_CREAT` / `O_APPEND` / `O_WRONLY`).
- Adiciona rotas backend `/api/v1/agent-events` (POST com idempotência via UUID e GET filtrado) e `/api/v1/system-status`.
- Adiciona nova seção "Centro de comando" e painel "Estado das Integrações" na interface web.
- Suíte expandida para 50 testes automatizados, todos aprovados.

## 0.1.0-dev.26 — 26/11/2026
- Corrige a tipagem do tipo de registro enviado pela interface; a compilação TypeScript volta a validar o formulário do ledger.
- Mantém a suíte com 45 testes aprovados no build ARM64.


## 0.1.0-dev.25 — 26/11/2026
- Corrige quebra literal `\\n` na declaração do ledger em `src/main.ts`, que interrompia o TypeScript.
- Mantém os 45 testes da suíte e permite prosseguir ao build Vite.


## 0.1.0-dev.24 — 26/11/2026
- Corrige as flags de abertura do ledger; permissões de arquivo passam como modo, sem O_EXCL acidental.
- Corrige os dois casos de teste que falharam no build ARM64 dev.23.


## 0.1.0-dev.23 — 26/11/2026
- Entrega o módulo de homologações, evidências e decisões com histórico append-only e integridade SHA-256.
- Inclui API e interface do ledger; a suíte completa será executada no build ARM64 do Supervisor.


## 0.1.0-dev.22 — 26/11/2026
- Corrige os testes arquiteturais após a inclusão dos quatro indicadores n8n.
- Ajusta a localização do `run.sh` no pacote de distribuição, compatível com a raiz usada pelo Docker build.


## 0.1.0-dev.21 — 26/11/2026
- Inicia a Fase 4 com conector n8n somente leitura para workflows e metadados de execuções.
- Adiciona opções protegidas independentes para URL base e API key n8n; nenhuma credencial é enviada ao frontend.
- Acrescenta a seção Automações n8n com estados, contagens e últimas execuções sem dados internos.


## 0.1.0-dev.20 — 26/11/2026
- Corrige a integração Supervisor: o papel `default` não autoriza `/v2/apps/status` (403 confirmado em produção).
- Substitui a listagem global por consultas GET allowlisted `/addons/{slug}/info`, compatíveis com papel `default`, usando lista declarativa de slugs conhecidos.


## 0.1.0-dev.19 — 26/11/2026
- Corrige a asserção da suíte de build: a tela contém quatro indicadores na visão geral e quatro no inventário Home Assistant.


## 0.1.0-dev.18 — 26/11/2026
- Adiciona inventário read-only de apps Home Assistant pelo endpoint Supervisor v2 `/apps/status`, usando papel `default`.
- Isola o token Supervisor em processo bridge local; o BFF principal permanece sem a credencial.
- Inclui vínculo declarativo entre add-ons e projetos e exibe estado/versões na seção Ambientes.
- Adiciona testes de normalização, allowlist e isolamento de credenciais.


## 0.1.0-dev.17 — 26/11/2026
- Inclui `config.yaml` no contexto de build do Supervisor para que os testes de segurança validem o manifesto efetivamente distribuído.
- Mantém a validação do manifesto, do entrypoint e das permissões sem retirar testes.


## 0.1.0-dev.16 — 26/11/2026
- Corrige os testes de segurança do cadastro para localizar os arquivos de configuração e entrypoint tanto no checkout-fonte quanto no pacote distribuído.
- Mantém a suíte executada no build real do Supervisor, sem retirar os testes de segurança.


## 0.1.0-dev.15 — 26/11/2026
- Adiciona cadastro controlado de projetos com criação de `.portal-governanca.json` na branch padrão selecionada.
- Mantém o token de leitura e adiciona credencial de escrita opcional e separada, sem ampliar permissões automaticamente.
- Restringe POST ao Ingress confiável e à origem same-origin; recusa marcador existente e valida consistência do projeto.
- Inclui tela de cadastro, inventário de repositórios e testes de segurança/integração.


## 0.1.0-dev.14 — 26/11/2026
- Mantém o cabeçalho das seções alinhado ao topo entre navegações e posiciona o rodapé no fim da área útil em páginas curtas, sem centralização vertical do workspace.


## 0.1.0-dev.13 — 26/11/2026
- Corrige a identidade visual do Portal usando o ícone oficial compartilhado pelo catálogo; substitui o marcador textual provisório.
- Reorganiza os quatro indicadores da visão geral em blocos verticais com espaçamento e hierarquia tipográfica próprios.
- Inclui os assets públicos da interface no pacote e no estágio de build do Supervisor.
- Corrige a quebra de linha literal acidental no empacotador que impedia sua execução.
- Inclui icon.png e logo.png no estágio de testes do Docker, garantindo que o teste de integridade dos assets execute no Supervisor.

## 0.1.0-dev.12 — 25/11/2026

- Corrige tipagem do snapshot opcional e do getter de projetos identificados; TypeScript passa a validar o estado vazio e navegação dinâmica.

## 0.1.0-dev.11 — 25/11/2026

- Inclui Dockerfile e entrypoint no contexto de teste do estágio de build para executar as verificações de arquitetura e isolamento.

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

