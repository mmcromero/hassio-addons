# Regras obrigatórias da distribuição Avisaqui

> **Publicação excepcional autorizada — 17/11/2026:** distribuição de teste `0.1.20-rc.2` derivada do merge privado PR30 `9bc8802f`, com atualização somente de metadados. Proprietário dispensou os gates pendentes exclusivamente para esta publicação; não são PASS. Sem instalação/ativação do Raspberry. PR30 está integrado; não continuar desenvolvimento em sua branch. Referências de preparação/restrição anteriores abaixo são históricas e não revogam a ordem expressa desta entrega.

> **Lote vigente PR30:** fonte `fix/avisaqui-impressao-ux-rc003`, versão `0.1.20-rc.1`. Preparar somente exportação local e validação ARM64 no SHA final. Não atualizar o repositório público por esta tarefa, nem fazer merge/deploy/instalação. Preservar opt-in OFF e exigir configuração explícita; PR28 é histórico.


> **Fechamento 15/11/2026:** `AVISAQUI-CONSOLIDACAO-RC-001` / 0.1.18-rc.1 está **fechado tecnicamente**, PR público #32 integrado. Versão relatada pelo proprietário como instalada e em execução no Raspberry Pi de homologação; homologação funcional permanece **em andamento**. Proibido continuar desenvolvimento em `release/avisaqui-rc-distribuicao-001` ou reabrir o PR #32; novos ajustes exigem **novo pacote** coordenado e registrado na fonte privada. Não tocar na fábrica isolada de jogos (Issue #21).


## P0 — Separação das três áreas de publicação (decisão 18/11/2026)

- **Fonte privada `mmcromero/pager-virtual:main`:** código-fonte do PG Virtual protegido. Só incorporar código homologado e autorizado. Desenvolver em `desenvolvimento` e preparar RC na `release-candidate` privada.
- **Catálogo de add-ons `mmcromero/hassio-addons:main`:** pode receber versões RC para instalação/testes **somente dentro de `pager-virtual/`**, após congelamento, exportação, conferência de versão/hashes e autorização de publicação do lote. A publicação da RC no catálogo **não é homologação nem merge da fonte privada**. A instalação existente acompanha esta `main` pública, não as branches RC alternativas. Não modificar outros add-ons ou arquivos compartilhados.
- **Laboratório público `mmcromero/fabrica-de-ideias-prototipos:main`:** publicação direta de protótipos navegáveis permitida para todos os projetos, limitada a `projetos/<id>/` e ao registro correspondente em `prototipos.json`. Nunca publicar segredos, dados reais ou código privado indevido. Preservar áreas dos demais projetos e conferir a URL navegável.

**Precedência:** esta regra posterior substitui a antiga proibição de atualizar a `main` do repositório de add-ons. A restrição da `main` privada do PG Virtual permanece. Para esta RC6, autorização e evidências estão na Issue privada #39; commit público `0846cea5d39b844187a30690d7e536b7e55ee6b4`.

**É terminantemente proibido desenvolver o Avisaqui de forma fragmentada ou independente neste diretório.** A fonte canônica é `mmcromero/pager-virtual`, privado. O responsável técnico deve resolver integração, conflitos, testes e documentação antes da entrega; não deixar a organização para o proprietário.

- Toda alteração deve ter origem privada identificada e revisada. Usar exportação explícita, conferir `SOURCE_PROVENANCE.json` e comparar os arquivos. Emergência expressamente autorizada exige sincronização imediata de volta ao privado.
- Continuar na branch/PR existente da tarefa. Não abrir branches paralelas para cada correção; não continuar numa branch com PR já integrado. Auditar conteúdo real, inclusive alterações posteriores ao merge, antes de considerar uma branch incorporada.
- Regra de pacote: todos os desenvolvedores entregam na única RC privada compartilhada enquanto o pacote estiver aberto. A distribuição usa uma única branch e PR correspondentes. Não criar branches remotas por pessoa/correção/documento. Branches locais isoladas são permitidas; nova branch normal só depois do fechamento do pacote. Consultar `.governance/package-policy.json` e `docs/GOVERNANCA-DO-PACOTE.md`.
- Preservar `/avisaqui/`, HTTP local, WebUI, login/redirecionamentos, SSE, Web Push, KDS, agente de impressão, slug e dados em `/data`. Não substituir diretórios por versões antigas nem apagar configurações de HTTPS para resolver conflitos.
- Executar testes pertinentes e conferir CI do HEAD final. Registrar o que não foi testado; não confundir código disponível, atualização oferecida, versão instalada e homologação.
- No botão WebUI, validar o endereço efetivamente gerado pelo Supervisor com hostname/mapeamento observados. O destino deste ambiente é diretamente HTTPS :8443 `/avisaqui/landing.html`, inclusive com sessão autenticada. Não entregar um redirecionamento que dependa de porta HTTP cuja acessibilidade não foi comprovada.
- Não alterar outros produtos deste repositório. Não versionar credenciais, bancos reais ou logs privados.
- A `main` **privada do PG Virtual** permanece estável e protegida. A `main` **pública deste catálogo** pode receber a distribuição de RC autorizada dentro de `pager-virtual/`. Instalação no HA, proxy/DNS, exclusão/reescrita de branches/tags e alterações fora do escopo exigem suas autorizações próprias. Nenhuma autorização é necessária para resolver escolhas técnicas rotineiras dentro da tarefa já autorizada.
- A governança coordena revisão/encerramento e registra responsáveis/delegações. Exceção emergencial exige motivo, aprovação, prazo, versão e destino; uma publicação anterior não autoriza novas exceções.
- Documentação/CI não bloqueiam fisicamente criação de branches. Não declarar proteção nativa ativa sem evidência administrativa. Não apagar branches/PRs nem alterar permissões por iniciativa própria.

Estas regras registram a determinação do proprietário após a emergência de HTTPS e a fragmentação das branches. A revisão deve exigir origem, testes, destino e documentação para cada alteração antes de concluir o trabalho.
