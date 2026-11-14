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
