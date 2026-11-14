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
**Não atualizar o Home Assistant com esta branch**, que ainda exige homologação operacional, validação HTTPS/proxy e autorização de publicação. O número 0.1.4 continua sendo o da base técnica, não o número definitivo da próxima entrega.
