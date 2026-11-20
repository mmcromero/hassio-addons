# Central Umdoislab — pacote de distribuição Home Assistant

**Finalidade deste diretório:** fornecer o pacote instalável da Central de Atendimento ao catálogo público `mmcromero/hassio-addons`. **Não é a fonte de desenvolvimento oficial.**

**Fonte privada oficial:** `mmcromero/whatsapp-automacoes` (acesso autorizado necessário). Workflows n8n, integrações ChatGPT/MCP, histórico de desenvolvimento, decisões e testes detalhados permanecem na fonte privada; **não são distribuídos aqui**.

## Manifesto desta revisão

| Campo | Valor do `config.yaml` |
| --- | --- |
| Nome proposto (branch) | Fábrica de Softwares - WhatsApp Umdoislab |
| Versão | 0.4.0 |
| Slug | `umdoislab_central` |
| Arquitetura | `aarch64` |
| Ingress | Ativado, porta interna `8099` |
| Inicialização | Manual |
| Backup declarado | `cold` |

**Padronização do título preparada em branch (ainda não publicada):** o aplicativo mantém o slug `umdoislab_central`, sem criar nova instalação; somente `name` e `panel_title` mudam. No catálogo `main`, o nome histórico permanece até publicação aprovada. A versão não foi alterada nesta preparação.

**Importante:** a versão do manifesto é a versão do **pacote versionado**, não confirmação da versão instalada no Raspberry. O código de distribuição é validado, publicado e homologado separadamente conforme `CONTRIBUTING.md` da loja.

## Configuração segura

O manifesto dispõe de opções `bridge_secret`, `evolution_url`, `evolution_instance`, `evolution_api_key` e `auto_test_sender`. Segredos devem ser configurados na interface segura do Supervisor, **nunca em arquivos Git**.

Não reutilizar tokens de WhatsApp, ChatGPT ou da Central fora de seu escopo autorizado. Não alterar versões, slugs, volumes persistentes ou endpoints sem plano de atualização e autorização do proprietário.

## Operação e proveniência

O `Dockerfile` contém a receita para a imagem instalável, com `server.py` e `static/` necessários ao build local. **Esses componentes permanecem visíveis neste repositório público**, mesmo com a fonte canônica no Git privado. Distribuição pública não oferece sigilo do código.

Para a documentação de operação, workflows, MCP V2, histórico e recuperação de backups, utilizar o repositório privado `mmcromero/whatsapp-automacoes`. O catálogo público mantém apenas documentação necessária à distribuição.

**Não apagar esta pasta da loja pública enquanto não existir outro canal de atualização do add-on homologado.**
