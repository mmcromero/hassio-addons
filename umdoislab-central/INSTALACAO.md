# Instalação controlada — Central de Atendimento Umdoislab

**Status:** preparação para homologação. **Não foi instalado nem ativado no Home Assistant do proprietário.**  
**Versão do add-on:** 0.1.0 (protótipo da Central, parte do projeto v1.5).  
**Escopo autorizado até aqui:** corrigir branch do PR #5 e preparar instalação; **não** modificar v1.4 em produção.

## Critérios obrigatórios antes de instalar

1. Revisão do PR #5 e CI com testes Python + build ARM64 aprovados.
2. Integração do add-on à `main` somente com autorização explícita.
3. Espaço livre/recursos do Raspberry avaliados no Home Assistant antes de instalar. A fonte não foi medida nesta revisão.
4. Definir onde manter backup do SQLite `/data/central.sqlite3`; primeiro testar restauração em ambiente isolado.
5. O add-on não solicita permissões ao Home Assistant Core. A tela usa o Ingress do Supervisor e aparece apenas para administradores.

## Instalação futura (manual, quando autorizada)

- Atualizar o repositório `mmcromero/hassio-addons` na loja de add-ons do Home Assistant, **sem remover** o add-on Evolution API existente.
- Instalar somente o novo add-on **Umdoislab — Central de Atendimento** e configurar opções de forma local:
  - `bridge_secret`: token forte, exclusivo para comunicação n8n→Central; manter apenas no n8n e no add-on, nunca em arquivos versionados ou prints.
  - `evolution_url`: URL da Evolution API acessível **de dentro** do contêiner; o padrão `http://homeassistant.local:8080` é sugestão e deve ser confirmado no ambiente.
  - `evolution_instance`: `umdoislab`.
  - `evolution_api_key`: chave global já existente no Evolution, configurada exclusivamente nas opções do Home Assistant.
- Iniciar somente a Central e abrir **Open Web UI** pelo Home Assistant. Não mapear portas, não criar túnel e não publicar o endereço na Internet.
- Conferir no celular a ordem por atividade recente, busca, filtros e detalhes. Os controles devem funcionar com dados de laboratório.

## Integração com n8n — ainda não realizada

A v1.4 publicada **continua respondendo ao contato de teste**. O painel **não** deve ser usado para assumir conversas reais antes de o n8n respeitar os estados `human`/`done`.

1. Criar workflow de integração **separado** no n8n; não editar a v1.4 atual.
2. Verificar o endereço de rede interno da Central e o acesso HTTPS/HTTP local entre os contêineres, sem expor a porta ao host. Usar exclusivamente `POST /bridge/events` com Bearer secret armazenado em credencial n8n.
3. Enviar evento fictício normalizado com `handoffRequested: true`. Apenas transferências criam uma nova pendência; mensagens recebidas comuns podem atualizar uma pendência existente.
4. Confirmar criação de uma ficha, atualização sem duplicar por `messageId`, ordenação, Assumir, Resolver e Reabrir.
5. Validar envio pelo painel somente a um número de teste autorizado, verificando o destino no backend. O retorno HTTP 2xx da Evolution significa **requisição aceita**, não prova de entrega; verificar recebimento no WhatsApp.
6. Implementar o roteamento da versão de atendimento que consulta o estado humano **antes** de qualquer resposta automática. Se não houver consulta ao estado, **não habilitar atendimento humano real no painel**.
7. Testar anti-loop e transferência com mensagens repetidas antes de liberar para contatos fora do teste.
8. Substituir a v1.4 apenas com autorização e depois de confirmar que não há dois Webhooks com o mesmo path.

## Verificação de segurança

- Ingress: fonte esperada `172.30.32.2`, conforme [documentação oficial do Home Assistant](https://contributors.home-assistant.io/apps/guides/ingress/); acesso direto de outras origens recebe 403.
- Chave Evolution somente no backend; chave `bridge_secret` só no servidor e nas credenciais n8n.
- Mensagens e nomes não entram no log HTTP; nunca enviar credenciais e números reais ao repositório.
- Envio manual registra `requestId` único; clique repetido não reenvia a mesma solicitação. Em falha de rede após a requisição, tratar resultado como **incerto** e consultar WhatsApp antes de reenviar.
- Identificador de destino deve ser individual e verificável, no formato `@s.whatsapp.net`. Contatos `@lid` não são enviados até validar resolução de JIDs.
- Retenção automática ainda não implementada; organizar política de limpeza de dados resolvidos antes de ativar coleta contínua em produção.
- Usar HTTPS remoto do Home Assistant, não expor portas diretamente.
- Testar backup/restore com aplicação parada (cold backup), antes de dados reais.

## Recuperação sem afetar a v1.4

- O add-on é **independente**. Se falhar, parar somente a Central.
- Não deletar add-on ou `/data` antes de coletar backup do banco; não fazer restauração na instalação em produção sem verificar versão.
- Manter a v1.4 como fluxo publicado durante homologação isolada da Central.
- Retornar ao estado anterior apenas desabilitando o novo conector n8n→Central; não alterar Webhook do Evolution em testes do painel.
