# ChatGPT ↔ n8n (Home Assistant) — MCP V2 e recuperação

**Data de validação:** 19/11/2026 (BRT)  
**Estado:** APROVADO COM RESSALVAS (somente leitura)  
**Origem da evidência:** comandos e logs do proprietário; relatório de validação funcional entregue após o teste do plugin V2.  
**Escopo:** conexão ChatGPT → Secure MCP Tunnel → n8n do Raspberry Pi; não é auditoria geral do Home Assistant.

## 1. Fonte da verdade e responsabilidade

- **Infraestrutura compartilhada:** este repositório (`mmcromero/hassio-addons`) e [inventário n8n](N8N-HOME-ASSISTANT-INVENTARIO.md). O inventário operacional do Raspberry continua no documento central do HA; não duplicar os cadastros.
- **Instância viva de workflows:** n8n no Raspberry. O Git contém JSONs históricos, mas **não** é backup completo e automático dos 14 workflows atuais nem do banco/credenciais.
- **Segredos:** não registrar token MCP do n8n, chave de runtime OpenAI, variáveis expandidas, arquivos de credenciais, session cookies, hashes ou dumps de execução com dados pessoais.
- **Separação:** o túnel não publica portas do Home Assistant; não alterar NGINX/DuckDNS/Avisaqui/Artesão Digital apenas para reconstruir esta conexão.

## 2. Arquitetura validada

```text
ChatGPT (plugin personalizado V2, conexão Túnel)
  → túnel OpenAI: tunnel_6aff3b9de67c8191aeb46dbc00ae123c
  → tunnel-client Windows v0.0.21, perfil n8n-home-assistant
  → http://homeassistant.local:5678/mcp-server/http
  → n8n MCP Server 1.2.0, Home Assistant / Raspberry Pi
```

**Identificadores não secretos:** plugin V2 `plugin_asdk_app_6aff6472aaa881918fd4686166218967`; túnel conforme acima. O plugin antigo `n8n — Home Assistant` foi desinstalado após a homologação do V2 (ação observada pelo assistente na integração de plugins). O V2 permaneceu instalado.

**Endereço do painel local do cliente:** `http://127.0.0.1:8080/ui` (disponível somente enquanto `tunnel-client run` está ativo).

**Configuração local:** `%APPDATA%\tunnel-client\n8n-home-assistant.yaml`. Referência ao segredo da OpenAI no perfil: `env:CONTROL_PLANE_API_KEY`, não valor literal.

## 3. Passos reproduzíveis no Windows (CMD)

Pré-requisitos: n8n com **Instance-level MCP** habilitado; workflow explicitamente disponível via MCP; túnel de mesmo ID existente e chave OpenAI de runtime com autorização apropriada; Windows alcança `homeassistant.local:5678`.

1. Obter `tunnel-client.exe` versão Windows AMD64 compatível, do projeto oficial `openai/tunnel-client`. A versão **verificada nesta operação** foi `0.0.21`.
2. Na pasta do executável, criar perfil **somente se não existir**:

   ```cmd
   tunnel-client.exe init --sample sample_mcp_with_dcr --profile n8n-home-assistant --tunnel-id tunnel_6aff3b9de67c8191aeb46dbc00ae123c --mcp-server-url http://homeassistant.local:5678/mcp-server/http
   ```

3. Criar em `https://platform.openai.com/settings/organization/api-keys` uma chave de **runtime** com permissões `Tunnels: Read + Use`. Configurar `CONTROL_PLANE_API_KEY` **apenas localmente**, sem compartilhá-la. Em CMD o comando `set /p` lê a entrada na própria sessão; não abrir outra janela presumindo herança de variáveis.
4. Autenticação do MCP n8n: o V2 funcional foi criado no ChatGPT com **Autenticação = Sem autenticação**, enquanto o cliente Windows foi configurado para autenticar no n8n por token de acesso. Token nunca deve aparecer no histórico de chat. O usuário confirmou a presença local das variáveis `N8N_MCP_TOKEN`, `MCP_EXTRA_HEADERS`, `CONTROL_PLANE_API_KEY`. A atribuição de cabeçalho realizada na sessão CMD foi `MCP_EXTRA_HEADERS=Authorization: Bearer <token local>`. **Atenção:** essa configuração foi observada funcionalmente para este ambiente; antes de adaptar a outra versão, conferir os parâmetros efetivos da versão instalada. A configuração do método de descoberta OAuth foi desativada no cliente durante esta tentativa, como confirmado pelo log.
5. Validar: `tunnel-client.exe doctor --profile n8n-home-assistant --explain`. Resultado verificado antes da mudança final: `RESULT ok`, alvo HTTP 401 (resposta normal antes de autenticação), metadados OAuth HTTP 200. Após configuração com token, log de runtime confirmou sessão MCP.
6. Iniciar `tunnel-client.exe run --profile n8n-home-assistant` na **mesma sessão CMD** que contém as variáveis. Manter o processo aberto; fechar CMD interrompe conexão. Não foi configurado serviço Windows nem início automático.
7. No ChatGPT, criar **novo** servidor personalizado `n8n — Home Assistant V2`: conexão **Túnel**, ID acima, autenticação **Sem autenticação**, sem opções OAuth avançadas; aceitar confirmação e criar. **Não reutilizar a configuração antiga que falhou.**
8. Validar listagem em leitura apenas. O teste efetivo do V2 retornou autenticação/comunicação e listagem de workflows bem-sucedidas.

**Não repetir o procedimento inteiro se o cliente já estiver ativo.** Diagnosticar a etapa específica. O botão verde «conectado» sozinho não prova leitura de ferramentas.

## 4. Evidências e limites

- `doctor`: perfil e túnel válidos; n8n acessível; metadados OAuth anunciados.
- Log de **19/11/2026 17:33:12 BRT**: `mcp session initialized`; `server_name: n8n MCP Server`, `server_version: 1.2.0`; `protocol_version: 2026-07-28`.
- Teste funcional de V2, **relatado pelo proprietário e detalhado em relatório**: comunicação OK, autenticação OK, 14 workflows, leitura de metadados, estrutura/nós, execuções e detalhes de falhas. O assistente não obteve uma captura independente desse relatório diretamente do MCP neste chat.
- **Resultado:** 3 workflows ativos; 11 inativos; 4 habilitados para MCP; 10 indisponíveis para MCP. A contagem é um retrato de 19/11, não sincronização automática.
- T13: acesso a workflow não habilitado via MCP rejeitado. Operações de execução, edição, publicação/desativação e acesso direto ao Home Assistant **não testadas**.
- **102 execuções com erro/crashed** na consulta global histórica; não representam 102 incidentes distintos ou problemas ativos. As 62 execuções do Roteador Central e cinco sucessos recentes são dados relatados na validação.
- **Falha anterior:** plugin V1 era reconhecido na UI, mas falhava ao chamar ferramentas; no Windows aparecia «Conectar». Testes de OAuth com `issuer` e `authorization_endpoint` em `http://homeassistant.local:5678` não resultaram em conexão operacional. Criar o plugin V2 limpo, com o mesmo túnel e sem OAuth no lado ChatGPT, resolveu o teste funcional relatado. Não há evidência para atribuir a falha à versão Windows, NGINX ou a bug confirmado do ChatGPT.

## 5. Segurança, recuperação e próximos passos

- Não publicar workflows integrais sem inspecionar primeiro se carregam PII, dados de clientes, headers, URLs com segredos, código embutido ou credenciais em texto.
- Antes de modificar qualquer workflow ativo: exportar instantâneo **sanitizado**, registrar ID e versão, inventariar gatilhos e dependências, planejar rollback, preservar a operação WhatsApp e evitar execuções em produção durante auditoria.
- Confirmar cobertura de backup do banco e chave de criptografia do n8n **sem revelar seus valores**; restauração não foi homologada neste registro.
- Repetir os testes funcionais somente quando configuração mudar ou houver falha, registrando data, estado e evidências; não usar `doctor` como substituto de `tools/list`.
- Documento subordinado às regras de governança do repositório e ao [inventário n8n](N8N-HOME-ASSISTANT-INVENTARIO.md). Atualizar ambos em PR revisado quando a arquitetura ou o inventário mudar.
