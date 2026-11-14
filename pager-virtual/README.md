# Pager Virtual — Add-on Home Assistant

Sistema de Pager Virtual ultraleve e em tempo real para restaurantes, praças de alimentação e food service.

## Funcionalidades
- **Notificações em Tempo Real (SSE):** Alerta sonoro de alta frequência (Web Audio API) e vibração ritmada no bolso do cliente quando a comida fica pronta.
- **Página Casca (< 50 KB):** Carrega instantaneamente em smartphones com conexão 3G de subsolo, lendo itens e comanda diretamente dos parâmetros do QR Code.
- **Painel KDS da Cozinha:** Visualização multi-pedidos com fila cronológica rigorosa (FIFO) e ações rápidas com 1 toque.
- **Banco de Dados Resiliente:** SQLite em modo WAL gravado com segurança na partição persistente `/data`.

## Instalação
1. Adicione este repositório à Loja de Add-ons do Home Assistant.
2. Localize **Pager Virtual** e clique em **Instalar**.
3. Inicie o complemento e acesse via porta externa `8095` ou pela interface WebUI.

## Histórico — correção KDS 0.1.4 (incluída na 0.1.5)
- Corrige o erro em que os pedidos existentes não apareciam ao entrar novamente ou atualizar o KDS, mas reapareciam após cadastrar outro pedido.
- Causa verificada no código: referência obsoleta a `orderCounter` dentro de `carregarPedidos()` interrompia a renderização da lista após a resposta da API.
- Os pedidos e os tokens já registrados no SQLite não precisam ser apagados.
- A correção do carregamento do KDS foi incorporada à versão 0.1.5.
- A versão 0.1.5 adiciona autenticação e isolamento entre restaurantes. Exposição pública via proxy ainda não foi testada em aparelho real.
- Consulte `CHANGELOG.md` neste diretório para o histórico completo, incluindo as versões 0.1.2 e 0.1.3.

## Procedimento de fechamento de futuras versões
Antes de concluir uma entrega:
1. Atualizar `CHANGELOG.md` deste add-on e `CHANGELOG.md` da aplicação principal, com a mesma versão e descrição compatível.
2. Atualizar a documentação técnica relevante e registrar limites e pendências reais.
3. Conferir a versão em `config.yaml` e `package.json` e sincronizar os arquivos entre os dois repositórios.
4. Executar e conferir testes e esteira aplicáveis; não declarar homologação no Home Assistant sem evidência da instalação.
5. Preservar o banco e registrar o PR/commit que contém cada entrega.

## Versão 0.1.5 — autenticação e KDS
A versão 0.1.5 reúne a correção do KDS 0.1.4 com:
- Login de Master Admin, gerente e terminal operacional;
- Primeiro acesso do proprietário mediante código temporário dos logs privados;
- Isolamento de pedidos e SSE por restaurante;
- Cadastro e revogação de terminais pelo gerente;
- Alteração da própria senha e redefinição de senha de terminal com revogação de sessões.

O código foi sincronizado com o repositório principal e os testes automatizados do add-on foram adicionados à esteira.
O teste de primeiro acesso foi ampliado e aprovado no GitHub Actions, incluindo tentativa por hostname público e cadastro inicial único. O teste automatizado não substitui o teste real de acesso pelo proxy HTTPS nem a instalação no Raspberry Pi.
A versão 0.1.5 é uma entrega de desenvolvimento: os testes automatizados foram aprovados. A publicação no GitHub não altera o Raspberry Pi automaticamente. O uso via proxy HTTPS real deve ser avaliado separadamente.

## Migração da versão 0.1.3 — dados existentes
- Teste automatizado `tests/legacy-upgrade.test.js` reproduz o esquema SQLite 0.1.3 e confirma que o upgrade não altera registros de restaurante nem pedidos.
- Após criar um acesso de gerente para o restaurante já cadastrado, os pedidos antigos nos estados `preparo` e `pronto` reaparecem no KDS autenticado. Pedidos `entregue` seguem no banco, fora da lista ativa.
- O novo banco **não cria contas automaticamente**. Após a primeira entrada como Master Admin, é necessário cadastrar o gerente do restaurante existente, sem cadastrar outro restaurante para substituir o anterior.
- Como precaução, recomenda-se um backup do complemento antes de atualizar se houver pedidos de teste que você deseja guardar. O teste sintético não comprova a restauração do banco real do Home Assistant.
- Atualizar os arquivos no GitHub não instala automaticamente a versão no Home Assistant.

## Segurança dos dados antes do upgrade (procedimento de homologação)
O banco de pedidos é `pager_virtual.db`, no diretório persistente `/data` do complemento. O SQLite usa modo WAL, por isso **não basta copiar só o arquivo `.db` enquanto o processo escreve**. Para obter um snapshot consistente, usar o mecanismo de backup do SQLite com o banco aberto ou interromper o serviço e fazer cópia consistente dos arquivos relacionados, conforme o procedimento de backup do Home Assistant verificado na instalação.

**Procedimento recomendado para instalações que precisam preservar dados:**
1. Obter backup do complemento com o banco preservado, sem modificar a instalação de origem.
2. Restaurar em ambiente isolado, verificar `PRAGMA integrity_check` e `PRAGMA foreign_key_check`, e comparar quantidade, IDs, tokens, estados e datas dos pedidos.
3. Iniciar a versão nova apenas na cópia restaurada; comparar dados antes e depois da migração.
4. Criar Master Admin e gerente vinculados ao **mesmo restaurante existente**; confirmar que o KDS mostra os pedidos em preparo e prontos, sem ressuscitar entregues.
5. Ensaiar o retorno ao snapshot anterior em outra cópia, sem substituir os dados da instalação ativa.
6. Para uso em produção, concluir essa homologação antes de liberar o serviço. Em desenvolvimento, esse ensaio é recomendado, não um bloqueio automático para publicar a versão de testes.

**Evidência atual:** `tests/sqlite-backup-restore.test.js` foi aprovado com banco sintético em WAL e 120 pedidos. Isso não comprova a integridade do backup real nem a capacidade de restauração do Raspberry Pi. A homologação real permanece pendente.

## Verificação da imagem ARM64 (CI)
O job `build-pager-arm64` agora carrega a imagem Docker compilada e executa `.github/scripts/smoke-pager.sh` em ambiente descartável. O ensaio deve:
- Iniciar o contêiner ARM64 e verificar `/api/health`.
- Criar um restaurante e um pedido sintéticos no SQLite do volume montado em `/data`.
- Destruir o contêiner, mas **preservar somente o volume de teste**.
- Iniciar um novo contêiner com o mesmo volume, confirmar integridade do SQLite e verificar que o ID, número, token e status do pedido permanecem iguais.
- Remover contêiner e volume sintéticos no encerramento do job.

**Resultado confirmado:** o job `build-pager-arm64`, execução 43590737190, aprovou a compilação e a etapa `Smoke da imagem ARM64 com volume persistente e reinício`.

**Limitação:** o ensaio de CI não acessa o Raspberry Pi, o backup real nem o supervisor Home Assistant. A validação final da instalação e do proxy continua pendente.

## Eventos em tempo real — validação de regressão
- As rotas SSE do KDS e do cliente assumem explicitamente o controle da conexão HTTP no Fastify; o cliente também tem heartbeat com limpeza ao desconectar.
- `tests/sse-http.test.js` conecta dois clientes SSE ao processo real e confirma cadastro de pedido, estado inicial e notificação `pronto` no KDS e no pager público.
- A CI `test-pager-auth` aprovou o teste. O comportamento no proxy HTTPS e em celulares reais ainda precisa ser homologado.

## Revogação de acesso com SSE ativo
- Quando um gerente desativa um terminal, a sessão deixa de ser válida.
- Antes de cada evento de pedido enviado ao KDS, o backend consulta novamente a autorização da sessão. O próximo evento não é enviado ao terminal revogado.
- Se nenhum evento ocorrer, o heartbeat encerra o stream sem autorização em até aproximadamente 25 segundos.
- O teste `tests/sse-scope.test.js` confirma a revogação e a continuidade da conexão de outro restaurante.
- A homologação com navegador real e proxy HTTPS permanece pendente.

## Versão 0.1.6 — notificações em segundo plano (Web Push)

- Quando o cliente acessa o QR Code, o Bipou verifica o suporte do navegador e a permissão de notificações.
- Em navegadores compatíveis com Web Push e HTTPS, aparece **Ativar notificações** quando a permissão ainda não foi concedida. A solicitação só acontece após o toque do cliente.
- Após a permissão e o registro da assinatura, a tela deixa de mostrar essa orientação. O servidor envia uma notificação do sistema quando o pedido muda para **pronto**.
- Se o navegador não oferecer suporte, a permissão for negada ou o iPhone estiver usando a página comum do navegador, a orientação pede que o cliente mantenha a tela aberta e ativa.
- No iPhone, Web Push exige um app web adicionado à Tela de Início (iOS 16.4+). Um QR Code aberto em aba normal não basta. Não prometemos que adicionar o ícone sozinho vincula o pedido ao app instalado.
- O som da notificação depende do dispositivo, modo silencioso e permissões. O aviso SSE e o áudio dentro da página continuam disponíveis quando ela está ativa.
- As chaves VAPID são geradas localmente no primeiro uso e salvas em `/data/push-vapid.json` (fora do Git). Não trocar esse arquivo durante atualizações se quisermos manter as assinaturas.
- A assinatura é vinculada ao token do pedido e não exige identificação pessoal.
- A loja de complementos recebe o código via GitHub; o teste em celular ocorre após atualizar o Home Assistant.

**Nota:** Web Push requer origem HTTPS confiável (ou localhost em ambiente local). Abrir o add-on por IP HTTP da rede não habilita Web Push em navegadores comuns.
