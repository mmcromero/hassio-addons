# AVISAQUI-WEBUI-PROXY-017 — destino exato do botão

## Evidência fornecida pelo proprietário

Após instalar 0.1.16, o botão gerou `http://romeropi.duckdns.org:8090/webui`. As capturas confirmam que o destino desejado, funcionando, é **https://romeropi.duckdns.org:8443/avisaqui/landing.html**, mesmo com sessão autenticada. A tentativa anterior dependia do acesso à porta HTTP 8090; essa condição não havia sido comprovada e falhou no uso real.

## Correção determinada pelo comportamento oficial

`webui: "https://[HOST]:[PORT:8443]/avisaqui/landing.html"`.

O getter original do Supervisor usa o mapeamento de portas somente quando encontra a chave correspondente. A instalação mapeia `8095/tcp → 8090`; não mapeia `8443/tcp`. Por isso `[PORT:8443]` permanece **8443**, sem criar ou expor qualquer porta nova. `[HOST]` continua sendo preenchido pelo frontend com `romeropi.duckdns.org`, como já foi observado na captura do botão. Não se usa hostname fixo inválido no manifesto.

O botão vai direto para o proxy e a landing; não chama `/`, `/webui` ou KDS. Assim o destino não depende de estar logado nem da disponibilidade da porta 8090. A rota `/webui` existente é preservada por compatibilidade, mas deixa de participar da abertura do botão.

Essa configuração corresponde ao ambiente DuckDNS/NGINX existente do proprietário. Não é um padrão universal para instalações sem esse proxy. Nenhum DNS, proxy, mapeamento de porta, banco ou serviço é alterado.

## Testes baseados no caso observado

O fixture `tests/fixtures/supervisor-webui-2026.01.1.py` contém o regex e getter originais do Supervisor, extraídos do commit fixo `ec0f7c2b9ca3de7793fbbbcefa5bba5b9820efda`. O restante é apenas isolamento da entrada; licença e origem acompanham o fixture.

Com `ports={"8095/tcp":8090}` e hostname observado, o teste reproduz a saída antiga **http://romeropi.duckdns.org:8090/webui** e exige que o manifesto corrigido produza exatamente **https://romeropi.duckdns.org:8443/avisaqui/landing.html**. A URL HTTPS final também foi consultada com validação TLS e respondeu HTTP 200 com a landing Avisaqui. O acesso HTTP 8090 não respondeu no teste externo, coerente com a dependência problemática; a correção não depende desse acesso.

A versão é incrementada para 0.1.17 porque o proprietário já instalou 0.1.16. A RC maior, ainda não publicada, passa a 0.1.18-rc.1 para manter a ordem das versões. Servidor e dependências do pacote mínimo permanecem idênticos aos da 0.1.16.

## Rastreabilidade e limite

A alteração nasce na branch privada de consolidação e é exportada por lista explícita/commit. A branch pública nova é necessária porque o PR anterior #33 já foi integrado e não deve receber novos commits. Seu escopo é somente a correção deste mesmo botão; a RC maior continua separada. Não apagar branches nem instalar remotamente. A disponibilidade no catálogo será verificada após publicação autorizada; a homologação no botão real exige a confirmação do proprietário.
