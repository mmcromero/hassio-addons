# Central Instagram Umdoislab — 0.1.14 (probe do cookie OAuth)

**Estado:** versão 0.1.14 publicada pelo PR #67 e confirmada no Home Assistant como **Em execução**. A homologação real do navegador/proxy foi executada e **falhou**. O log recebido foi: `OAuth cookie probe missing (host_ok=True, https_ok=True)`. O parser não encontrou o cookie com o nome derivado do nonce; isso não distingue, por si só, cookie não armazenado, não enviado, removido no caminho ou enviado com nome inesperado. O log também contém uma ocorrência separada em `stage=exchange_code`; ela indica que outra callback passou por validação/consumo do state e falhou na troca do código Meta. Não correlacionar as duas ocorrências sem timestamps/IDs.

**Relatório e passagem para análise controlada:** [Incidente OAuth cookie probe 0.1.14](../docs/instagram-central/INCIDENTE-OAUTH-COOKIE-PROBE-20261120.md). A análise deve usar os blobs exatos registrados no relatório e não deve alterar HA, NGINX, Ingress, credenciais nem repetir OAuth real.

- Repositório privado de origem: `mmcromero/instagram-automacoes`.
- Candidata privada: [PR #9](https://github.com/mmcromero/instagram-automacoes/pull/9), branch `fix/instagram-oauth-state-cookie-binding-001`, HEAD `723b423069c18a19c1053aecaf3bcef399b0efbb` (código privado 0.1.13; não presumir que já contém o delta de probe da distribuição pública 0.1.14).
- Publicação: [PR #67](https://github.com/mmcromero/hassio-addons/pull/67), merge commit `418ca163c7534273c5d4ed906c835ac424d47d8b`.
- Identidade de distribuição preservada: nome **Fábrica de Softwares - Central Instagram**, slug `umdoislab_instagram`, arquitetura `aarch64`, Ingress habilitado na porta interna `8099`.

**Limites:** não repetir OAuth real; não habilitar webhook, assinatura, Direct, respostas automáticas ou publicação. Mensagens e Editorial permanecem no mesmo add-on, painel e sessão.
