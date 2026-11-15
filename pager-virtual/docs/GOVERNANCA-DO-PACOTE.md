# Governança obrigatória do pacote Avisaqui

> **PACOTE 002 ABERTO (15/11/2026):** candidato `0.1.19-rc.1`. Esta branch `release/avisaqui-rc-distribuicao-002` é **somente a distribuição derivada** da RC privada `mmcromero/pager-virtual:release/avisaqui-rc-002`. Não publicar ou mesclar este PR enquanto o código privado não estiver integrado, exportado com origem/hashes atualizados e aprovado. Os arquivos atuais servem como base de preparação, **não como exportação final validada**. A fábrica independente de jogos permanece isolada. Plano completo na fonte privada: `docs/governanca/AVISAQUI-PACOTE-002.md`.


> **Atualização 15/11/2026 — FECHADO TECNICAMENTE:** pacote `AVISAQUI-CONSOLIDACAO-RC-001`, versão `0.1.18-rc.1`, PR privado #20 e PR público #32 integrados. O proprietário confirmou a versão instalada e em execução no Home Assistant do Raspberry Pi de **homologação**. **Homologação funcional ainda em andamento**; divergências de UX serão tratadas em novo pacote. Não reutilizar os PRs/branches de RC antiga. Aguardar Governança registrar o novo pacote principal. Referência canônica: `mmcromero/pager-virtual/docs/governanca/AVISAQUI-CONSOLIDACAO-RC-001-FECHAMENTO.md`.


Enquanto um pacote estiver aberto, todos os desenvolvedores do aplicativo devem concentrar código, correções, testes e documentação na **mesma RC privada**. Este diretório público recebe somente a distribuição derivada de um commit privado identificado. Não criar branches remotas por pessoa, funcionalidade, correção ou documento.

Registro vigente: `.governance/package-policy.json`.

- Um pacote principal aberto, uma branch privada compartilhada e uma distribuição pública.
- Reaproveitar as branches/PRs durante o pacote; abrir o próximo somente depois do fechamento registrado.
- Branches locais isoladas são permitidas; push remoto somente para a RC e sem reescrever histórico.
- Não continuar em branch cujo PR já foi integrado. Não criar nova branch para contornar conflitos ou CI.
- Emergência exige motivo, autorização, responsável, versão, validade e destino registrados; não é uma permissão permanente de fragmentação.
- A governança coordena escopo/revisão/encerramento; o desenvolvedor resolve programação e conflitos. Publicações e exclusões exigem a autorização/delegação aplicável.
- Publicar somente o SHA aprovado e testado, preservar dados/HTTPS e não alterar outros produtos deste repositório.

Pacote anterior: `AVISAQUI-CONSOLIDACAO-RC-001`, **fechado**. A distribuição **0.1.18-rc.1** foi integrada pelo PR #32. Pacote atual: **`AVISAQUI-PACOTE-002`**, versão candidata `0.1.19-rc.1`, com branch/PR únicos registrados na política. Não reutilizar a branch `release/avisaqui-rc-distribuicao-001`.

O check `scripts/check-package-policy.py` valida branch, versão e escopo. O workflow dedicado é preparado por origem privada e não modifica outros produtos. **CI/documentação não impedem fisicamente criar branches ou fazer merge sem proteção nativa.** A governança deve conferir plano, acessos, revisores e checks obrigatórios antes de declarar os controles ativados.

Branches históricas permanecem preservadas até revisão/encerramento autorizado. O inventário e a passagem de bastão completos ficam no repositório privado, em `docs/governanca/`. Nenhuma branch é apagada por este documento.
