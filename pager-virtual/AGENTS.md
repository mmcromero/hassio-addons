# Regras obrigatórias da distribuição Avisaqui

**É terminantemente proibido desenvolver o Avisaqui de forma fragmentada ou independente neste diretório.** A fonte canônica é `mmcromero/pager-virtual`, privado. O responsável técnico deve resolver integração, conflitos, testes e documentação antes da entrega; não deixar a organização para o proprietário.

- Toda alteração deve ter origem privada identificada e revisada. Usar exportação explícita, conferir `SOURCE_PROVENANCE.json` e comparar os arquivos. Emergência expressamente autorizada exige sincronização imediata de volta ao privado.
- Continuar na branch/PR existente da tarefa. Não abrir branches paralelas para cada correção; não continuar numa branch com PR já integrado. Auditar conteúdo real, inclusive alterações posteriores ao merge, antes de considerar uma branch incorporada.
- Preservar `/avisaqui/`, HTTP local, WebUI, login/redirecionamentos, SSE, Web Push, KDS, agente de impressão, slug e dados em `/data`. Não substituir diretórios por versões antigas nem apagar configurações de HTTPS para resolver conflitos.
- Executar testes pertinentes e conferir CI do HEAD final. Registrar o que não foi testado; não confundir código disponível, atualização oferecida, versão instalada e homologação.
- No botão WebUI, validar o endereço efetivamente gerado pelo Supervisor com hostname/mapeamento observados. O destino deste ambiente é diretamente HTTPS :8443 `/avisaqui/landing.html`, inclusive com sessão autenticada. Não entregar um redirecionamento que dependa de porta HTTP cuja acessibilidade não foi comprovada.
- Não alterar outros produtos deste repositório. Não versionar credenciais, bancos reais ou logs privados.
- Main permanece estável. Merge, publicação, instalação, proxy/DNS e exclusão/reescrita de branches/tags exigem autorização específica. Nenhuma autorização é necessária para resolver escolhas técnicas rotineiras dentro da tarefa já autorizada.

Estas regras registram a determinação do proprietário após a emergência de HTTPS e a fragmentação das branches. A revisão deve exigir origem, testes, destino e documentação para cada alteração antes de concluir o trabalho.
