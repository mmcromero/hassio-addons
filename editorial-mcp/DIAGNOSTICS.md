# Diagnóstico seguro do Funnel — candidata 0.1.1

## Motivo

A versão 0.1.0 inicia o `tailscaled` dedicado com stdout/stderr descartados e valida apenas `BackendState`/hostname. O Funnel CLI pode dizer `Success` mesmo quando o tráfego público fecha durante TLS. A versão 0.1.1 adiciona coleta de evidências somente leitura, sem endpoint HTTP novo.

## Ativação

A opção `diagnostics_enabled` é opt-in e vem desativada por padrão. Quando habilitada, o app imprime linhas `DIAG` no log local do Supervisor logo após configurar o Funnel.

## Dados coletados

- versão do cliente Tailscale;
- `status --json`, reduzido a backend state, online, hostname esperado, presença da capability Funnel e contagem de peers com tag `tag:ingress` (total/online);
- `funnel status --json` e `serve status --json`, somente código de saída, presença de saída, menção a Funnel e porta 443;
- `netcheck`, com campos de conectividade allowlisted e sem endereço IP;
- erros reduzidos ao nome da classe de exceção.

Nenhum JSON bruto, peer identity, IP, chave, state file, token, URL de login, corpo HTTP ou arquivo é impresso. Nenhuma rota pública diagnóstica é criada. Não executa `bugreport`, não envia logs ao Tailscale e não altera Funnel/Serve/ACL.

## Segurança e operação

- Não habilitar em produção sem autorização explícita do proprietário.
- Não reiniciar nem atualizar o Tailscale principal do Home Assistant.
- O app MCP continua usando estado/socket próprios e loopback 127.0.0.1:8765.
- As consultas CLI são locais; `netcheck` executa sondagens de conectividade normais do cliente.
- O diagnóstico não substitui uma sonda HTTPS pública feita de fora do tailnet.

## Estado

Origem histórica: branch pública `diag/editorial-mcp-funnel-001`, preservada como quarentena e não utilizada na esteira. O código 0.1.1 foi recuperado e integrado seletivamente à fonte privada `instagram-automacoes:desenvolvimento`; a opção `diagnostics_enabled` permanece desativada por padrão. A candidata 0.1.2 que preserva este diagnóstico ainda não foi publicada nem instalada.


### Refinamento de sanitização
- Capability Funnel detectada por substring em chaves CapMap, sem imprimir chaves.
- PortMapping reduzido a indicador yes/no/unknown; valores detalhados, IPs, portas e regiões nunca são registrados.
- Teste dirigido atualizado para confirmar que UPnP aparece somente como `yes`.


## Continuidade na candidata 0.1.2

A candidata 0.1.2 mantém integralmente o diagnóstico local opt-in descrito acima e acrescenta a ponte privada de arquivos do host ChatGPT. A coleta Tailscale/Funnel continua desativada por padrão; as novas ferramentas de arquivo não alteram o Tailscale principal, não criam endpoint de diagnóstico e não publicam dados de diagnóstico.

- `test_diagnostics.py` permanece no repositório-fonte e deve continuar sendo executado no build junto de `test_server.py` e `test_host_file_bridge.py`.
- A integração de transporte temporário é específica do host ChatGPT; não substitui o envio Base64 usado por outros clientes MCP.
- A candidata 0.1.2 foi congelada em `release-candidate`; ainda não foi publicada no catálogo, instalada ou homologada.
- Não há nova evidência de acesso HTTPS externo do Funnel. A sonda externa continua pendente.
- Nenhuma autorização para alterar o Home Assistant, reiniciar o app, habilitar diagnósticos em produção ou modificar o Tailscale principal foi presumida.

