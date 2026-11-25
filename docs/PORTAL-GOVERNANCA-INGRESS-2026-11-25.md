# Registro técnico — Correção do Ingress do Portal de Governança

**Data:** 25/11/2026  
**Produto:** Fábrica de Ideias - Portal de Governança  
**Fonte:** `mmcromero/portal-governanca`, branch `desenvolvimento`  
**Distribuição:** `mmcromero/hassio-addons/portal-governanca`, branch `main`  
**Versão instalada:** `0.1.0-dev.6`  
**Slug:** `portal_governanca`  
**Porta interna:** `8099`  
**Arquitetura:** `aarch64`

## Sintoma

A instalação aparecia como iniciada no Supervisor, mas o botão **Abrir interface** retornava Not Found. Um link montado fora da sessão corrente retornava 401. Esses resultados não demonstravam, isoladamente, falha do runtime nem permitiam reutilizar um token de Ingress.

## Diagnóstico separado em duas camadas

### 1. Manifesto

Para entrada na raiz, o Supervisor deve receber `ingress: true` e `ingress_port: 8099`, sem `ingress_entry`. Declarar `ingress_entry: /` provocava URL-base com barra duplicada (`//`). O manifesto do Portal na versão dev.6 omite essa propriedade.

### 2. Encaminhamento no servidor

O Home Assistant encaminha pelo prefixo dinâmico `/api/hassio_ingress/<token>/` e fornece `X-Ingress-Path`. Dependendo do encaminhamento, o caminho recebido pela aplicação pode ainda conter o prefixo ou já ser relativo à raiz do app. A implementação anterior não cobria adequadamente o segundo formato.

A correção em `server/ingress.mjs`:
- preserva o tratamento do prefixo exato quando ele permanece no caminho;
- aceita caminho relativo à aplicação quando o proxy já retirou o prefixo;
- exige que o fluxo de chamada valide antes o peer confiável do proxy Supervisor e o cabeçalho dinâmico `X-Ingress-Path`;
- não fixa nem fabrica tokens;
- não remove a proteção de acesso externo.

## Correção publicada

A versão `0.1.0-dev.6` foi distribuída em `hassio-addons:main/portal-governanca/`. O manifesto mantém `ingress: true`, `ingress_port: 8099` e não declara `ingress_entry`. O changelog registra a mudança.

## Resultado real no Home Assistant

O proprietário confirmou que a interface abriu pelo botão oficial **Abrir interface** após a atualização para dev.6.

**Aprovado:** abertura inicial pelo Ingress oficial.  
**Ainda não declarado aprovado:** verificação detalhada de CSS/JS/imagens/fontes, `/api/health`, `/api/v1/portfolio`, navegação interna, ausência global de 400/404/502 e ausência de loops. Esses itens precisam de evidência própria antes de declarar homologação funcional completa.

## Prevenção de recorrência

1. Omitir `ingress_entry` para entrada na raiz.
2. Validar os dois formatos de encaminhamento no servidor, sem enfraquecer a validação do proxy.
3. Testar o botão oficial do HA; não reutilizar URL/token de sessão anterior.
4. Conferir HTML, assets, APIs, navegação, redirecionamentos e logs.
5. Não confundir `state: started`, resposta 401 de token antigo ou 403 de acesso direto à porta com homologação do Ingress.

## Evidências de referência

- Manifesto distribuído: `portal-governanca/config.yaml` — versão `0.1.0-dev.6`.
- Implementação distribuída: `portal-governanca/server/ingress.mjs`.
- Histórico de versões: `portal-governanca/CHANGELOG.md`.
- Fonte canônica do produto: `mmcromero/portal-governanca`, commit `feeb1cdc3783614f167bccf3266906d8983a7ee2`.
- Confirmação de abertura: retorno explícito do proprietário nesta conversa, após instalação dev.6.
