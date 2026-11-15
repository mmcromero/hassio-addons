# AVISAQUI-WEBUI-CATALOGO-016 — correção emergencial mínima

## Problema demonstrado

O manifesto público anterior da 0.1.16 usa um hostname fixo em `webui`. A regra oficial do Supervisor requer `http(s)://[HOST]:[PORT:porta]...`. A validação rejeita o valor absoluto; o carregador do catálogo registra o erro e ignora o complemento inválido. Isso explica tecnicamente por que um pacote presente no GitHub pode não ser oferecido, embora o aplicativo HTTPS já esteja acessível. Sem ler o log do Supervisor real, não afirmamos ter confirmado o evento nessa instalação.

Fontes: Home Assistant Supervisor tag `2026.01.1`, `supervisor/addons/validate.py` (ATTR_WEBUI); código atual `supervisor/apps/validate.py` e `supervisor/store/data.py`. O CI anterior validava YAML e build, mas não esse requisito. A regressão foi acrescentada ao `npm test`, executado pela CI existente.

## Solução

- `webui: "http://[HOST]:[PORT:8095]/webui"`: formato aceito pelo Supervisor, mantendo a porta existente.
- `GET /webui`: redireciona para `public_url + /landing.html`, sem aceitar destino da query e sem cachear o redirecionamento. Sem URL pública configurada, mantém a landing local e o prefixo do proxy.
- O ambiente observado já informa `public_url` HTTPS em `romeropi.duckdns.org:8443/avisaqui`; nenhuma alteração de proxy, DNS, porta ou opção real é necessária para essa configuração.

O navegador precisa alcançar a porta local do add-on para receber o primeiro redirecionamento. A abertura a partir de fora da rede depende da disponibilidade desse endereço; o link HTTPS direto continua sendo a entrada externa. Não declarar homologação do botão sem teste na interface real do Home Assistant.

## Escopo e rastreabilidade

Correção baseada em `hassio-addons@e6e3a31f756acb0eb60a4e770f9caf579be9a40f`, preservando a versão 0.1.16 aguardada pelo proprietário (não instalada/homologada conforme seu relato). Não renomeia a RC 0.1.17 nem reescreve commits/tags existentes. Código nasce na branch privada de consolidação; o exportador gera somente a sobreposição mínima identificada em `SOURCE_PROVENANCE.json`.

A branch pública de emergência é necessária para oferecer uma correção pequena da 0.1.16, sem publicar as funcionalidades/dependências da RC do PR #32. Não é uma segunda frente de desenvolvimento: deriva de um commit privado, com destino e encerramento explícitos. A RC maior permanece nos PRs #20/#32 e recebe a mesma correção de origem.

Não altera SQLite, autenticação, dados, agente Windows, Pong ou dependências. Não instala no Raspberry. Publicação na main pública exige a autorização específica prevista na missão inicial; preparar o PR não oferece automaticamente uma nova atualização ao Supervisor.

## Validação

Teste de regressão falhou antes da correção: manifesto rejeitado e `/webui` inexistente. Cenários automatizados: formato/porta do manifesto, rejeição do valor antigo, destino HTTPS configurado, fallback HTTP local e prefixo do proxy. Conferir CI do HEAD da correção antes de publicar. Após publicação autorizada, verificar o catálogo, atualizar para 0.1.16 e testar o botão; a instalação e a impressão física não foram executadas nesta preparação.
