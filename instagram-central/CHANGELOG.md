## Incidente de homologação — cookie probe 0.1.14 ausente — 20/11/2026

- **Evidência do proprietário:** `OAuth cookie probe failed: OAuth cookie probe missing (host_ok=True, https_ok=True)`.
- Host público e encaminhamento HTTPS foram reconhecidos pelo handler. O parser não encontrou o cookie com o nome derivado do nonce. Isso não prova se o navegador não armazenou, não enviou, se um intermediário removeu ou se o nome recebido divergiu.
- **Lacuna dos testes:** `tests/test_http.py` extrai `Set-Cookie` e injeta manualmente `Cookie` na callback. Não reproduz o armazenamento e o envio automático do cookie por um navegador real após o 302.
- **Evento separado:** `Meta OAuth callback rejected at stage=exchange_code: Meta authorization exchange failed`. Como o caminho do probe retorna antes da troca, essa mensagem pertence a outra callback. Ela passou por parse/consumo do state e falhou depois, na troca do código. Não há timestamp/correlation ID para ordenar os eventos nem detalhe da resposta original da Meta.
- **Ação:** análise controlada do Codex, somente leitura e testes offline sintéticos; sem mudança em HA, NGINX, Ingress, credenciais ou opções; sem chamada Graph real, novo OAuth, webhook, Direct, respostas automáticas ou publicação.
- Relatório detalhado: [INCIDENTE-OAUTH-COOKIE-PROBE-20261120.md](../docs/instagram-central/INCIDENTE-OAUTH-COOKIE-PROBE-20261120.md).

## 0.1.14 — probe usa o mesmo cookie de estado do OAuth — 21/11/2026

- O probe emite nonce sintético e cookie com o mesmo nome derivado do state e usa o mesmo helper de leitura do callback.
- `/health` e a página de probe identificam a versão em execução.
- O PR #67 foi mesclado na main; versão 0.1.14 confirmada instalada e em execução no Home Assistant.
- O teste real no navegador falhou conforme a evidência acima. Não declarar homologação do cookie aprovada.
- A suíte embutida no Dockerfile é executada no build do Supervisor; os logs individuais dos testes não foram capturados nesta verificação. O CI geral do catálogo não equivale à execução da suíte específica da Central.
- Não repetir OAuth real. Webhook, Direct, respostas automáticas e publicações permanecem desativados.

