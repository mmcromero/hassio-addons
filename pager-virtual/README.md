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

## Versão 0.1.4 — correção do carregamento do KDS
- Corrige o erro em que os pedidos existentes não apareciam ao entrar novamente ou atualizar o KDS, mas reapareciam após cadastrar outro pedido.
- Causa verificada no código: referência obsoleta a `orderCounter` dentro de `carregarPedidos()` interrompia a renderização da lista após a resposta da API.
- Os pedidos e os tokens já registrados no SQLite não precisam ser apagados.
- **Homologação pendente:** instalar a versão 0.1.4 no Home Assistant e verificar que os pedidos aparecem após recarregar e reabrir o KDS; confirmar criação, QR, impressão, chamada e finalização.
- A aplicação ainda não tem autenticação de operadores nem isolamento de restaurantes. **Não expor o KDS à internet nesta versão.**
- Consulte `CHANGELOG.md` neste diretório para o histórico completo, incluindo as versões 0.1.2 e 0.1.3.

## Procedimento de fechamento de futuras versões
Antes de concluir uma entrega:
1. Atualizar `CHANGELOG.md` deste add-on e `CHANGELOG.md` da aplicação principal, com a mesma versão e descrição compatível.
2. Atualizar a documentação técnica relevante e registrar limites e pendências reais.
3. Conferir a versão em `config.yaml` e `package.json` e sincronizar os arquivos entre os dois repositórios.
4. Executar e conferir testes e esteira aplicáveis; não declarar homologação no Home Assistant sem evidência da instalação.
5. Preservar o banco e registrar o PR/commit que contém cada entrega.

## Próxima entrega — autenticação em preparação (não instalada)
A branch `feat/pager-auth-staging` reúne a correção do KDS 0.1.4 com:
- Login de Master Admin, gerente e terminal operacional;
- Primeiro acesso do proprietário mediante código temporário dos logs privados;
- Isolamento de pedidos e SSE por restaurante;
- Cadastro e revogação de terminais pelo gerente;
- Alteração da própria senha e redefinição de senha de terminal com revogação de sessões.

O código foi sincronizado com o repositório principal e os testes automatizados do add-on foram adicionados à esteira.
O teste de primeiro acesso foi ampliado e aprovado no GitHub Actions, incluindo tentativa por hostname público e cadastro inicial único. O teste automatizado não substitui o teste real de acesso pelo proxy HTTPS nem a instalação no Raspberry Pi.
**Não atualizar o Home Assistant com esta branch**, que ainda exige homologação operacional, validação HTTPS/proxy e autorização de publicação. O número 0.1.4 continua sendo o da base técnica, não o número definitivo da próxima entrega.

## Migração da versão 0.1.3 — dados existentes
- Teste automatizado `tests/legacy-upgrade.test.js` reproduz o esquema SQLite 0.1.3 e confirma que o upgrade não altera registros de restaurante nem pedidos.
- Após criar um acesso de gerente para o restaurante já cadastrado, os pedidos antigos nos estados `preparo` e `pronto` reaparecem no KDS autenticado. Pedidos `entregue` seguem no banco, fora da lista ativa.
- O novo banco **não cria contas automaticamente**. Após a primeira entrada como Master Admin, é necessário cadastrar o gerente do restaurante existente, sem cadastrar outro restaurante para substituir o anterior.
- **Antes de atualizar uma instalação real**, exigir backup íntegro dos arquivos SQLite e teste de restauração em ambiente separado; o teste com banco sintético não valida backup/restore real do Home Assistant.
- Nenhuma atualização no Home Assistant foi realizada nesta etapa.

## Segurança dos dados antes do upgrade (procedimento de homologação)
O banco de pedidos é `pager_virtual.db`, no diretório persistente `/data` do complemento. O SQLite usa modo WAL, por isso **não basta copiar só o arquivo `.db` enquanto o processo escreve**. Para obter um snapshot consistente, usar o mecanismo de backup do SQLite com o banco aberto ou interromper o serviço e fazer cópia consistente dos arquivos relacionados, conforme o procedimento de backup do Home Assistant verificado na instalação.

**Critérios de aceite para o ensaio fora da instalação ativa:**
1. Obter backup do complemento com o banco preservado, sem modificar a instalação de origem.
2. Restaurar em ambiente isolado, verificar `PRAGMA integrity_check` e `PRAGMA foreign_key_check`, e comparar quantidade, IDs, tokens, estados e datas dos pedidos.
3. Iniciar a versão nova apenas na cópia restaurada; comparar dados antes e depois da migração.
4. Criar Master Admin e gerente vinculados ao **mesmo restaurante existente**; confirmar que o KDS mostra os pedidos em preparo e prontos, sem ressuscitar entregues.
5. Ensaiar o retorno ao snapshot anterior em outra cópia, sem substituir os dados da instalação ativa.
6. Só então preparar liberação da versão, com atualização dos dois changelogs, revisão do número de versão, build ARM64 e autorização de publicação.

**Evidência atual:** `tests/sqlite-backup-restore.test.js` foi aprovado com banco sintético em WAL e 120 pedidos. Isso não comprova a integridade do backup real nem a capacidade de restauração do Raspberry Pi. A homologação real permanece pendente.

## Verificação da imagem ARM64 (CI)
O job `build-pager-arm64` agora carrega a imagem Docker compilada e executa `.github/scripts/smoke-pager.sh` em ambiente descartável. O ensaio deve:
- Iniciar o contêiner ARM64 e verificar `/api/health`.
- Criar um restaurante e um pedido sintéticos no SQLite do volume montado em `/data`.
- Destruir o contêiner, mas **preservar somente o volume de teste**.
- Iniciar um novo contêiner com o mesmo volume, confirmar integridade do SQLite e verificar que o ID, número, token e status do pedido permanecem iguais.
- Remover contêiner e volume sintéticos no encerramento do job.

**Limitação:** o ensaio de CI não acessa o Raspberry Pi, o backup real nem o supervisor Home Assistant. A validação final da instalação e do proxy continua pendente.
