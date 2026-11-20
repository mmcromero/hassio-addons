# Operação do laboratório Central

Este add-on é uma candidata de **testes**, sem atendimento automático e **sem envio WhatsApp**.

1. Cumprir a rotina universal do catálogo `../CONTRIBUTING.md`.
2. Confirmar que o Supervisor apresenta duas instalações diferentes: `umdoislab_central` (atual) e `umdoislab_central_lab` (laboratório). **Não atualizar a instalação atual**.
3. Instalar o LAB com `boot: manual`, sem configurar API keys da Evolution e sem conectar webhooks.
4. Iniciar apenas o LAB e conferir Ingress, logs e dados isolados. A porta 8099 é **interna ao contêiner**, não está exposta no host.
5. Testar apenas eventos sintéticos e repetição de ID. A função `CENTRAL_LAB_NO_WHATSAPP=1` deve retornar HTTP 403 em qualquer tentativa de envio, sem comunicação externa.
6. Registrar no PR #10 / Issue #7 execução, versão, resultado e limitação. Não instalar versão nova em lugar do add-on atual.

Este documento **não** autoriza publicação na main nem alteração dos workflows operacionais; a autorização do proprietário para uma instância de testes deve ser respeitada em escopo e identidade.
