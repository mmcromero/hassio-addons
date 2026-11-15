# AVISAQUI-PONG-014 — Protótipo de jogo opcional

**Estado:** experimental, sem homologação em dois aparelhos. **Referências:** PR de distribuição [#29](https://github.com/mmcromero/hassio-addons/pull/29); protótipo no repositório fonte [#19](https://github.com/mmcromero/pager-virtual/pull/19). Esta documentação descreve o código da branch, não comprova instalação ou publicação.

## Por que existe

Investigar se o tempo de espera de um pedido pode ser mais agradável com uma atividade compartilhada entre dois clientes, sem prejudicar a função principal: informar o andamento do pedido e avisar quando estiver pronto. É um experimento de produto, **não uma funcionalidade comercial homologada**. A decisão de manter, redesenhar ou retirar depende de testes de usabilidade, desempenho e estabilidade.

## Evolução implementada na branch (ainda sem homologação)

A interface oferece **Pong: duas pessoas** e **Pong: contra o computador**. No modo solo, o servidor controla a raquete direita com velocidade limitada; o cliente controla a esquerda. Uma sala por pedido mantém seu modo até ser encerrada. A escolha não muda o banco de pedidos. O modo solo **ainda não foi testado em celular real**.

## Falha relatada em 15/11/2026

Capturas do pedido #204 mostram botão visível, tela do jogo com **Not Found** e carregamento persistente. A resposta indica erro em uma requisição da entrada no jogo; não há log HTTP do servidor/proxy para confirmar sua origem. A branch passou a exibir mensagem explícita para HTTP 404 e inclui teste automatizado de GET disponibilidade e POST entrada com token inexistente (esperado HTTP 409). **Não declarar a causa raiz corrigida sem reproduzir o fluxo HTTPS real.**

## Experiência pretendida

1. Dois aparelhos abrem a página do cliente pelo **mesmo QR Code/token de pedido**.
2. Se a função estiver ativada e o pedido estiver em `preparo`, aparecem as opções de jogar sozinho contra o computador ou com outra pessoa.
3. No modo dupla, cada aparelho ocupa uma posição e controla uma raquete; no modo solo, o servidor controla a raquete adversária. O servidor mantém bola, placar e estado.
4. A partida termina quando o pedido sai de `preparo`; o aviso do pedido continua prioritário.
5. Quem não abre o jogo usa a página do cliente normalmente. O módulo visual é carregado sob demanda.

**Limite:** o código permite no máximo duas posições por sala. Um terceiro participante não entra como jogador.

## Chave de ativação no Home Assistant

No manifesto `pager-virtual/config.yaml`:
```yaml
options:
  pong_experimental: false
schema:
  pong_experimental: bool
```

- **Desligado (padrão):** `pong_experimental: false`. As rotas do Pong não são registradas e o botão não deve aparecer.
- **Ligado (teste autorizado):** `pong_experimental: true` nas opções do add-on. Salvar e **reiniciar o add-on**: a opção é lida na inicialização, não em tempo real.
- **Desligar novamente:** voltar para `false` e reiniciar. Isso não remove pedidos nem exige migração de banco.
- O servidor também aceita `AVISAQUI_PONG_EXPERIMENTAL=1` como habilitação por variável de ambiente. **Atenção:** essa variável tem precedência sobre `pong_experimental: false`; não configurá-la na instalação normal. Para garantir desligamento, remover a variável e reiniciar.

O código lê as opções em `/data/options.json`; falha na leitura mantém o jogo desligado, salvo se a variável de ambiente o habilitar. **Não confundir desativar o jogo com fazer downgrade do add-on.** Um downgrade precisa de verificação de compatibilidade das opções e backup consistente.

## Arquitetura atual (confirmada no código)

- `src/pong.js`: salas em `Map` na memória do processo, indexadas pelo ID do pedido; não cria tabelas SQLite nem grava pontuação.
- `src/public/pong.js`: canvas, controles por ponteiro, `fetch` para comandos e `EventSource` para receber estado.
- `src/public/cliente.html`: entrada opcional e carregamento dinâmico do módulo.
- `src/server.js`: registra as rotas experimentais quando habilitadas.
- `config.yaml`: chave administrativa `pong_experimental`.

**API experimental** (não tratar como contrato estável):
- `GET /api/jogos/pong/disponivel`: indica que a função está habilitada.
- `POST /api/jogos/pong/entrar`: recebe token, atribui lado e identificador de jogador.
- `POST /api/jogos/pong/mover`: recebe token, jogador e posição vertical.
- `POST /api/jogos/pong/sair`: libera a posição.
- `GET /api/jogos/pong/eventos/:token/:player`: fluxo SSE da partida.

**Parâmetros atuais de implementação, sujeitos a revisão:** ciclo do servidor a cada 50 ms; até 64 salas simultâneas; até quatro conexões SSE por sala; consulta ao status do pedido aproximadamente a cada segundo; descarte de sala após 30 minutos sem atividade. A tela envia movimentos com intervalo mínimo de 45 ms. Esses números **não são capacidade homologada do Raspberry Pi**.

## Riscos e pontos abertos

- A partida é volátil: reiniciar o processo elimina salas e placares, mas não os pedidos.
- A saída explícita libera a posição; perda de rede/fechamento abrupto pode manter a posição ocupada até limpeza. Avaliar presença, reconexão e expiração por jogador.
- A verificação periódica do pedido pode atrasar o encerramento do jogo em relação à mudança de status. Confirmar que o alerta de pedido pronto tem prioridade na experiência real.
- Testar comportamento de duas conexões SSE, perda de sinal, alternância entre abas, tela bloqueada e aparelho lento.
- Medir CPU, memória, volume de requisições e tráfego no Raspberry Pi, com jogo ligado e desligado, sem afetar o atendimento.
- Revisar limites, autenticação por token, consumo de recursos, abuso de endpoints e isolamento entre pedidos.
- O recurso não deve exigir aplicativo nativo, cadastro adicional ou compra de infraestrutura pelo restaurante.

## Critérios de homologação

1. Confirmar o funcionamento normal da versão anterior: pedidos, KDS, QR, alertas, login, HTTPS e impressão quando aplicável.
2. Com a chave desligada, confirmar ausência do botão e das rotas do jogo.
3. Com a chave ligada e o add-on reiniciado, abrir o mesmo pedido em dois celulares e verificar controle independente, bola e placar sincronizados.
4. Confirmar bloqueio de terceiro jogador e comportamento ao sair/reentrar.
5. Mudar pedido para `pronto` e depois `entregue`; verificar prioridade do aviso e fim da partida.
6. Repetir com conexão lenta e interrupção de rede; medir recursos do servidor.
7. Desligar a chave, reiniciar e confirmar que pedidos e funções existentes continuam íntegros.

**Até a execução desses testes:** implementação preparada, **não homologada**.

## Ideias futuras — NÃO implementadas nem aprovadas

- Minijogos alternativos e escolha de jogo pelo cliente.
- Ajuste dinâmico de taxa de atualização conforme rede e carga do servidor.
- Reconexão robusta e retomada de vaga após queda de sinal.
- Modo acessível, orientação de tela e controles adaptados.
- Métricas agregadas de adesão e desempenho, sem coletar dados pessoais desnecessários.
- Limites por estabelecimento e controle administrativo de disponibilidade.

Avaliar essas propostas separadamente. Não ampliar o escopo da 0.1.14 sem decisão explícita.

## Continuidade para outro desenvolvedor

**Fonte da verdade para distribuição:** branch/PR #29 em `mmcromero/hassio-addons`. **Protótipo de origem:** PR #19 em `mmcromero/pager-virtual`. Evitar implementação paralela ou merge duplicado.

Antes de fechar o pacote, conferir o diff atual, a esteira GitHub Actions, a versão em `config.yaml` e `package.json`, o changelog e os documentos de HTTPS/impressão. Registrar o commit final, testes e limitações. Não interpretar aprovação de CI como homologação em aparelhos reais.

**Princípio permanente:** a notificação do pedido é a função principal; o jogo é opcional, leve, reversível e secundário.
