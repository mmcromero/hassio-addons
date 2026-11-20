# 12Labs Central de Atendimento — LAB Home Assistant

**Situação:** candidata experimental na branch `chore/central-publicacao-p0-20261120` do catálogo. **Não publicada na `main`, não instalada e não homologada.**

**Objetivo:** validar o código do PR privado [#10](https://github.com/mmcromero/whatsapp-automacoes/pull/10) em uma segunda instância de HA, sem modificar a Central existente.

## Identidade criada nesta candidata, conforme cadastro único do catálogo

- `name`: Fábrica de Softwares - 12Labs Central de Atendimento (LAB)
- Pasta: `umdoislab-central-lab/`
- `slug`: `umdoislab_central_lab`, **diferente** de `umdoislab_central`
- Versão candidata: `0.4.1-rc.1`; `aarch64`; Ingress interno `8099`
- `icon.png` e `logo.png`: blobs de identidade padronizada no catálogo; mesmos bytes da Central existente.
- `panel_icon`: `mdi:message-processing-outline` (ícone da barra lateral, não o arquivo PNG).
- **Origem congelada:** `mmcromero/whatsapp-automacoes` commit `15bd84919f996f865c98b132268da2a80d309c71` do PR #10. Esse SHA identifica o código fonte, não um merge.

## Limites obrigatórios e verificação

- `Dockerfile` define `ENV CENTRAL_LAB_NO_WHATSAPP=1`. O backend recusa **ambos** os caminhos de envio: resposta automática e resposta manual. Não editar esta variável para testar o LAB.
- A instância não configura credenciais por padrão, não tem porta de host exposta e não recebe webhook de cliente. `boot: manual`.
- **Não** substituir ou atualizar `umdoislab-central/`. Cada add-on terá `/data` isolado pelo próprio Supervisor; comprovar essa separação na instalação antes de qualquer teste.
- Não reutilizar token/credencial da Central antiga, não apontar Evolution ou n8n ativos ao LAB e não ativar o worker de recuperação por padrão.
- Para rodar os testes, instalar somente esta instância pelo Supervisor **após publicação autorizada na `main`**; capturar resultado de build, boot, Ingress, logs e teste de bloqueio de envio.
- Um build ARM64 em Actions/QEMU não é portão automático; o Supervisor pode compilar Dockerfile diretamente no Raspberry.

**Publicação:** cumprir [CONTRIBUTING.md](../CONTRIBUTING.md) e [AGENTS.md](../AGENTS.md). A nova pasta exige sua própria entrada em `.github/addon-registry.json`, que será preparada na mesma branch. Não abrir PR/rodar Actions/merge/publicar automaticamente.
