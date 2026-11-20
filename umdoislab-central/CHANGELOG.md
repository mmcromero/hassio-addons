# Histórico da distribuição — Central Umdoislab

Este arquivo registra **somente o pacote de distribuição** em `mmcromero/hassio-addons/umdoislab-central/`.
O desenvolvimento, os testes funcionais e o PR #10 pertencem à fonte privada `mmcromero/whatsapp-automacoes`.
Consulte o procedimento P0 do catálogo em [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

## 0.4.0 — manifesto atualmente na loja

- Identificação publicada: `Fábrica de Softwares - 12Labs Central de Atendimento`.
- Slug registrado: `umdoislab_central`; arquitetura `aarch64`; Ingress interno `8099`.
- Pacote existente na `main` do catálogo: `Dockerfile`, `server.py`, `static/`, `icon.png`, `logo.png`, `config.yaml`.
- Este registro **não confirma** a versão instalada no Raspberry Pi.

## Preparação ainda não publicada — PR privado #10

- Recuperação da fila, reconciliação de histórico PN/LID e bloqueio após atendimento humano foram preparados na fonte privada.
- **Não exportado nem instalado.** Uma futura distribuição precisa de versão nova, seleção explícita do SHA da fonte, testes proporcionais e conferência dos arquivos do pacote.
- Uma instalação paralela exige **outro slug e outra pasta registrada**, distintos dos utilizados pela Central atual. O catálogo não define até o momento um identificador oficial dessa instalação de laboratório; não inventar nem publicar um por inferência.
- Para ensaio com imagem ARM64, o Supervisor pode construir diretamente no Raspberry porque este pacote usa `Dockerfile` sem `image`; QEMU/Actions não são requisitos automáticos.

**Ícone e logo da loja:** manter os blobs documentados no inventário do catálogo: `icon.png` SHA `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a`; `logo.png` SHA `7e500016222b0a5bf395be8ed17447edeb3e2af9`. `panel_icon: mdi:message-processing-outline` é outra propriedade e não altera esses arquivos.
