# Governança obrigatória do pacote Avisaqui

Enquanto um pacote estiver aberto, todos os desenvolvedores do aplicativo devem concentrar código, correções, testes e documentação na **mesma RC privada**. Este diretório público recebe somente a distribuição derivada de um commit privado identificado. Não criar branches remotas por pessoa, funcionalidade, correção ou documento.

Registro vigente: `.governance/package-policy.json`.

- Um pacote principal aberto, uma branch privada compartilhada e uma distribuição pública.
- Reaproveitar as branches/PRs durante o pacote; abrir o próximo somente depois do fechamento registrado.
- Branches locais isoladas são permitidas; push remoto somente para a RC e sem reescrever histórico.
- Não continuar em branch cujo PR já foi integrado. Não criar nova branch para contornar conflitos ou CI.
- Emergência exige motivo, autorização, responsável, versão, validade e destino registrados; não é uma permissão permanente de fragmentação.
- A governança coordena escopo/revisão/encerramento; o desenvolvedor resolve programação e conflitos. Publicações e exclusões exigem a autorização/delegação aplicável.
- Publicar somente o SHA aprovado e testado, preservar dados/HTTPS e não alterar outros produtos deste repositório.

Pacote atual: `AVISAQUI-CONSOLIDACAO-RC-001`, candidata **0.1.18-rc.1**. Distribuição de trabalho: `release/avisaqui-rc-distribuicao-001`, PR #32. A versão **0.1.17** publicada é a correção mínima do botão e não a liberação desta RC maior.

O check `scripts/check-package-policy.py` valida branch, versão e escopo. O workflow dedicado é preparado por origem privada e não modifica outros produtos. **CI/documentação não impedem fisicamente criar branches ou fazer merge sem proteção nativa.** A governança deve conferir plano, acessos, revisores e checks obrigatórios antes de declarar os controles ativados.

Branches históricas permanecem preservadas até revisão/encerramento autorizado. O inventário e a passagem de bastão completos ficam no repositório privado, em `docs/governanca/`. Nenhuma branch é apagada por este documento.
