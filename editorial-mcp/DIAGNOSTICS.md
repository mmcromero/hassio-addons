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

Branch `diag/editorial-mcp-funnel-001`. Não mergeada, não publicada e não instalada. A ativação depende de autorização para publicar/instalar a candidata 0.1.1 e habilitar a opção `diagnostics_enabled`.
