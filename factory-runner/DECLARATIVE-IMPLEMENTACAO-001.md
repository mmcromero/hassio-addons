# FACTORY-RUNNER-DECLARATIVE-001 — Preparação determinística sem executar exportador

**Controle:** Issue #2 do Orquestrador. **Atualizado:** 19/11/2026. **Estado:** implementação em branch de desenvolvimento; NÃO PUBLICADA / NÃO INSTALADA / NÃO HOMOLOGADA. Produto independente dos projetos atendidos.

## Decisão e escopo

A falha `bwrap: Failed to make / slave: Permission denied` impede executar um exportador Python dentro de um sandbox de montagens no contêiner Home Assistant. **Não** tentar corrigir com `SYS_ADMIN`, Docker privilegiado, desativação do AppArmor ou execução sem isolamento de código de origem.

Para o **preparo mecânico de pacotes**, substituir a execução de scripts fornecidos pelo repositório por **cópia declarativa de blobs Git** realizada somente pelo código confiável do Factory Runner. Isso **não** libera execução de código gerado por IA, testes de código não confiável, publicação Git ou `/api/corrigir-issue`.

## Implementação em andamento

**Fonte privada canônica:** `mmcromero/orquestrador-projetos-base:feat/factory-runner-esteira-001/factory-runner-add-on/` (PR #3).

**Espelho de desenvolvimento, NÃO catálogo instalado:** `mmcromero/hassio-addons:feat/factory-runner-declarative-preparation/factory-runner/`.

- `declarative_export.py`: seleciona arquivos por regras confiáveis e por árvore Git fixada; valida tipos, caminhos, symlinks, SHA, versão, tamanho, quantidade e tempo; copia blobs sem executar scripts; valida SHA-256 e escreve bundle local temporário.
- `rc_fastlane.py`: valida perfis declarativos, caminhos compartilhados, condições e contrato de CI; preserva o preflight e as regras de pacote aberto.
- `server.py`: `POST /api/prepare-declarative` exige token e exatamente projeto/SHA, aplica o preflight, valida o blob aprovado do exportador e a compatibilidade do workflow de CI, gera provenance e registra auditoria; **não publica**. A rota antiga `/api/prepare` mantém Bubblewrap obrigatório e falha fechada.
- `projects/avisaqui.json`: **exemplo real de perfil**, com as regras retiradas do exportador aprovado. É configuração do produto atendido, não acoplamento do núcleo Factory Runner.
- `Dockerfile`: inclui o módulo no build de validação e no runtime; preserva `landlock_probe.py` e `trusted_export_plan.py` da fonte privada.
- Testes sintéticos versionados: seleção de árvores, política, HTTP com Bearer, bloqueios, arquivos compartilhados, manifesto e integração com repositórios temporários.

**Registro de proveniência:** o bundle local usa `DECLARATIVE_BUNDLE_MANIFEST.json` próprio, separado do `SOURCE_PROVENANCE.json` de distribuição. O pacote final exige validação independente; nenhum sucesso de preparação equivale a publicação.

## Evidências verificadas até agora

1. O exportador original do primeiro perfil tem blob Git `e67c816405707545b21b0e6863814ada7b26d0f1`, idêntico ao SHA confiável fixado no perfil.
2. O commit de referência da fonte `a4b97c1d353e6111dc48933806f13c77d0dec6f9` foi inspecionado por metadados de árvore Git completos (320 entradas, 295 blobs). Confrontando a seleção do script original e da receita nova: **135/135 arquivos padrão correspondentes, zero diferenças**, mais **1 workflow compartilhado** condicionado.
3. Todos os **136 arquivos** são regulares, presentes, com caminhos aceitos pela validação; total dos bytes informados pela árvore Git: **996.451 bytes**, abaixo dos limites declarados. **Não foi feita comparação dos bytes de todos os 136 arquivos**.
4. O workflow já presente na distribuição `main` tem os três marcadores de compatibilidade exigidos; quando a versão local não tiver compatibilidade, a rota deve falhar, sem aplicar patches do repositório cliente.
5. **18 testes locais PASS**, executados em uma **reprodução fiel das funções do núcleo declarativo com Git sintético**, incluindo symlink, traversal, versão divergente, condições, arquivo compartilhado e manifesto. Essa execução **não comprova execução da suíte integral da branch GitHub**. Testes adicionais de HTTP e integração foram escritos e versionados, mas **ainda não executados contra o checkout completo**.

## Pendências objetivas para homologar

- Executar de fato `python3 -m unittest discover -s factory-runner-add-on/tests -p 'test_factory_runner_*.py' -v` e `python3 -m py_compile factory-runner-add-on/*.py` sobre o checkout do SHA da branch privada. Não usar Actions ou afirmar PASS sem resultado.
- Prova de equivalência **byte a byte** com exportador canônico e manifesto final; confirmar tratamento do workflow compartilhado e do contrato de CI no destino em checkout descartável.
- Testar a nova rota e cenários negativos HTTP de ponta a ponta, incluindo falta de workspace, pacote fechado, divergência de SHA, falha da auditoria, concorrência e ausência de mapeamento.
- Revisão de segurança e limites de recursos no HA. A nova rota não usa Bubblewrap, mas não serve para código desconhecido. A versão de pacote/RC e instalação devem passar pelo procedimento universal do catálogo, sem repetir RCs por tentativa.

**Nenhuma mudança** foi realizada na `main`, no Home Assistant físico, no Forja 01, no n8n ou em credenciais. Não abrir nova Issue. **Próximo responsável:** DEV do Factory Runner executa os testes e corrige diferenças; Segurança revisa; Homologação testa no dispositivo após publicação específica de candidata pronta.

## Verificação adicional — CI por commit imutável

- Corrigida a leitura do workflow compartilhado: a versão anterior lia o arquivo do checkout de trabalho; a revisão agora usa `git show <public_main_sha>:<workflow_path>` no **commit público fixado pelo preflight**, sem executar o arquivo. Isso impede que alterações locais não registradas satisfaçam artificialmente o contrato de compatibilidade.
- Adicionados dois testes de regressão à suíte de segurança para confirmar a consulta ao commit fixado e o bloqueio de workflow incompatível. **Esses dois testes foram versionados, mas não executados neste ambiente.**
- Releitura via GitHub dos arquivos `server.py`, `rc_fastlane.py`, `declarative_export.py`, `projects/avisaqui.json` e quatro arquivos de testes nas branches privada e de distribuição: **8/8 hashes Git de blob idênticos**.
- Tentativa de acesso ao repositório GitHub via terminal deste ambiente retornou erro de DNS. O acesso do conector GitHub permite leitura/commit, mas não fornece execução de shell ou Docker. Assim, **não declarar como PASS** a suíte integral ou os testes HTTP do checkout. A validação física/ARM64 continua não executada.
- A origem privada possui seu próprio planejador histórico `trusted_export_plan.py`; a implementação nova o preserva, assim como o diagnóstico Landlock e o comportamento fail-closed do Bubblewrap para código não confiável.
