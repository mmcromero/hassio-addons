# AGENTS.md — Instruções universais do catálogo Home Assistant

> **AMBIENTE COMPARTILHADO — FONTE CENTRAL (19/11/2026):** antes de perguntar sobre Raspberry Pi, Home Assistant, apps instalados, repositórios da loja, ARM64 ou homologação, consulte o [inventário operacional central](https://github.com/mmcromero/hassio-addons/blob/main/docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md). Não copie a lista de apps para outros projetos; confirme no Supervisor apenas dados voláteis ou decisões críticas. Essa referência não autoriza remover, reiniciar, atualizar ou instalar apps.


## P0 — Procedimento único para qualquer publicação no Home Assistant (19/11/2026)

**Aplica-se a todas as pessoas e agentes, independentemente do cargo, experiência ou projeto.** Ao receber ordem para criar, fechar, testar, empacotar ou publicar **qualquer add-on** por `mmcromero/hassio-addons`, consulte **antes de agir** a [rotina canônica do catálogo](https://github.com/mmcromero/hassio-addons/blob/main/CONTRIBUTING.md) e o manual vigente do add-on. O procedimento cobre fechamento do lote, validações proporcionais, publicação isolada em `hassio-addons:main/<pasta-do-add-on>/` mediante autorização, verificação remota e homologação real no Home Assistant. O manual do produto define sua fonte, branch e exportação; **não aplicar nomes de branch exclusivos do Avisaqui aos demais add-ons**.

**Proibição de falso bloqueio:** ausência de QEMU, emulador, máquina ARM64 externa, Actions ou build ARM64 em CI **não é impedimento automático**. Para add-ons com Dockerfile sem `image` pré-compilada, o Supervisor **pode executar o build no dispositivo-alvo na instalação/atualização**; o teste real ocorre na fase apropriada de homologação. Mudança com binário nativo, imagem pré-compilada, falha demonstrada ou risco de segurança pode exigir teste adicional justificado. Nunca marcar teste não executado como PASS nem confundir publicação com instalação/homologação. Antes de NO-GO, identificar causa, fonte/revisão consultada, tentativa autorizada, alternativa GOV-BLK-002 e razão objetiva de não resolver. Sem isso, classificar como **DESVIO DE PROCEDIMENTO** e corrigir só a etapa afetada. Bloqueios reais de segurança, permissão e autorização permanecem.

**Fiscalização:** Governança/Tech Lead exigem evidência em tarefa real e anotação na Issue existente; publicação desta instrução não comprova que chats externos a carregaram.

## Aplicação obrigatória

- Toda tarefa recebida sobre pacote/add-on deste catálogo começa pela leitura do `CONTRIBUTING.md` **vigente na main** e do manual do add-on.
- Valide versão, SHA/HEAD, arquivos, arquitetura declarada, segredos e integridade conforme o diff e o risco. Não impor gates externos genéricos.
- Publique apenas a pasta do add-on autorizado na `main` do catálogo, mantendo os demais arquivos e add-ons intactos. Fonte privada e procedimentos próprios do produto devem ser respeitados.
- Registre o commit público e o resultado de verificação na Issue existente. Publicação, instalação, execução e homologação são estados distintos.
- Se houver instrução antiga contraditória, corrija-a no documento de origem quando autorizado; não invente novos fluxos. Normas superiores de segurança e autorizações prevalecem.
