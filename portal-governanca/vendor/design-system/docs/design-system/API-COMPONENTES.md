# Referência de API dos componentes

**Versão:** 0.1.0 — desenvolvimento, não publicada.  
**Fonte:** packages/components/src/components/.  
**Escopo:** contrato observado no código desta versão.

## Inventário

| Elemento | Finalidade | Atributos principais | Eventos / API |
|---|---|---|---|
| ds-button | Executar uma ação | variant, size, type, disabled, loading, aria-label, full-width | click nativo |
| ds-input | Receber um valor | label, name, type, value, placeholder, helper-text, error-message, required, disabled | value, ds-input, ds-change |
| ds-badge | Mostrar estado curto | variant | nenhum evento próprio |
| ds-alert | Mostrar mensagem | variant, title, dismissible | ds-dismiss |
| ds-card | Agrupar conteúdo | title, elevated | nenhum evento próprio |
| ds-dialog | Tarefa modal curta | title, open | showModal(), close(), ds-close |
| ds-app-shell | Estrutura global da aplicação | regiões diretas `data-ds-region` | layout estrutural CSS; sem API JS própria |

## Contrato comum

- Os sete elementos são Custom Elements nativos.
- Todos usam Light DOM. Nenhum usa Shadow DOM.
- `ds-app-shell` é um primitivo estrutural: mantém os elementos semânticos do consumidor como filhos diretos, sem mover conteúdo.
- Nos componentes de conteúdo, filhos são roteados para regiões internas quando indicado pela API. `ds-app-shell` é exceção estrutural: mantém suas regiões semânticas como filhos diretos.
- Filhos adicionados depois também são roteados. O comportamento é mantido após remover e reinserir o host no DOM.
- O pacote registra os elementos ao importar @mmcromero/ds-components.
- A função registerAllComponents() também é exportada. Ela não redefine elementos já registrados.
- O CSS não é injetado pelo JavaScript. Importe os tokens e os estilos dos componentes.
- WCAG 2.2 AA é uma meta do projeto. Os testes axe e de teclado cobrem cenários selecionados. Eles não certificam conformidade completa.
- A importação em Node sem DOM é segura. Renderização SSR em string não está implementada nesta versão.

## ds-button

**Finalidade:** executar uma ação local. Use para salvar, confirmar, cancelar ou abrir um diálogo. Não use para navegação; use um link.

### Atributos

| Atributo | Tipo | Padrão | Valores ou efeito |
|---|---|---|---|
| variant | texto | primary | primary, secondary, destructive, ghost |
| size | texto | md | sm, md, lg |
| type | texto | button | button, submit, reset |
| disabled | booleano | ausente | Desabilita o botão nativo |
| loading | booleano | ausente | Mostra spinner, define aria-busy=true e desabilita |
| aria-label | texto | ausente | Define o nome acessível do botão interno |
| full-width | booleano | ausente | Ocupa 100% da largura disponível |

Os atributos variant, size, type, disabled, loading e aria-label são observados pelo componente. full-width é aplicado pelo CSS do host.

### API pública e eventos

Não há métodos ou propriedades adicionais. O clique usa o evento nativo click, que borbulha a partir do botão interno. Não há evento customizado.

### Estados, teclado e acessibilidade

- O texto filho fornece o nome acessível.
- aria-label substitui o nome calculado a partir do texto.
- loading define aria-busy=true e bloqueia nova ativação.
- O botão nativo aceita Enter e Espaço.
- O foco visível usa focus-visible.
- O spinner respeita prefers-reduced-motion.
- As variantes sm e md usam altura mínima de 44px. A variante lg usa 52px. O CSS também define largura mínima de 44px.

### Exemplo

    <ds-button variant="primary">Salvar</ds-button>
    <ds-button variant="destructive" loading>Excluindo</ds-button>

## ds-input

**Finalidade:** receber um valor de texto com rótulo persistente, ajuda e erro inline.

### Atributos

| Atributo | Tipo | Padrão | Valores ou efeito |
|---|---|---|---|
| label | texto | vazio | Rótulo; deve ser fornecido |
| name | texto | vazio | Nome do input interno |
| type | texto | text | text, email, password, search, number, url |
| value | texto | vazio | Valor atual |
| placeholder | texto | vazio | Texto auxiliar; não substitui label |
| helper-text | texto | vazio | Instrução associada ao campo |
| error-message | texto | vazio | Mensagem; ativa aria-invalid=true |
| required | booleano | ausente | Define required no input interno |
| disabled | booleano | ausente | Desabilita o input interno |

### API pública

A propriedade value é string e tem getter e setter.

    const field = document.querySelector('ds-input');
    field.value = 'marco@example.com';
    console.log(field.value);

### Eventos

| Evento | Quando ocorre | detail | Bubble |
|---|---|---|---|
| ds-input | Em cada evento input | { value: string } | sim |
| ds-change | No evento change | { value: string } | sim |

O componente também atualiza o atributo value quando a pessoa digita.

### Estados, teclado e acessibilidade

- O label é associado ao input interno por label[for] e input[id].
- O ID do input interno é gerado. O atributo id do host identifica o Custom Element, não o input.
- helper-text e error-message são associados por aria-describedby.
- error-message ativa aria-invalid=true e a mensagem usa role=alert.
- required e disabled são aplicados ao input nativo.
- Teclado e entrada seguem o comportamento nativo do tipo escolhido.
- O campo tem largura fluida e altura mínima definida pelo token de alvo de toque.

### Limitações da versão 0.1.0

- Não há atributos min, max, pattern, autocomplete, inputmode ou readonly.
- name e placeholder são observados. A versão atual limpa o valor interno quando esses atributos são removidos.
- O componente não expõe uma API própria de associação a formulários.

### Exemplo

    <ds-input label="E-mail" name="email" type="email"
      placeholder="nome@exemplo.com" helper-text="Use o e-mail da conta"
      required></ds-input>

## ds-badge

**Finalidade:** mostrar um estado curto junto a um item. Exemplo: Ativo, Em revisão ou Bloqueado.

### Atributos

| Atributo | Tipo | Padrão | Valores |
|---|---|---|---|
| variant | texto | neutral | neutral, info, success, warning, error |

### API, semântica e teclado

Não há propriedades, métodos ou eventos próprios. O conteúdo é apresentado em um span. O componente não adiciona role e não é interativo.

Use texto que identifique o estado. Não dependa somente da cor. Não use badge para anunciar mudanças dinâmicas; use ds-alert.

### Exemplo

    <ds-badge variant="success">Concluído</ds-badge>

## ds-alert

**Finalidade:** apresentar uma mensagem contextual de erro, aviso, informação ou sucesso.

### Atributos

| Atributo | Tipo | Padrão | Valores ou efeito |
|---|---|---|---|
| variant | texto | info | info, success, warning, error |
| title | texto | vazio | Título opcional |
| dismissible | booleano | ausente | Exibe botão Fechar aviso |
| aria-live | atributo ARIA | conforme variant | off silencia o anúncio automático interno e mantém o conteúdo navegável como grupo; use somente quando uma região viva persistente externa anunciar o mesmo texto |

### API e eventos

Não há métodos ou propriedades públicos adicionais.

| Evento | Quando ocorre | detail | Bubble |
|---|---|---|---|
| ds-dismiss | Antes de o host ser removido pelo botão de fechar | nenhum | sim |

O componente emite ds-dismiss e remove o próprio host do DOM.

### Semântica, teclado e acessibilidade

- error e warning usam role=alert.
- info e success usam role=status.
- Quando o host recebe aria-live=off, o conteúdo interno usa role=group e aria-live=off; isso permite separar a notificação visual de uma região viva persistente, evitando anúncios duplicados.
- Use aria-live=off apenas quando outra região viva persistente anunciar o mesmo conteúdo. O alerta visual continua navegável, sem anúncio automático duplicado.
- Em notificações dinâmicas, mantenha a região viva no DOM antes da ação e atualize seu texto; não dependa apenas da inserção simultânea de um novo componente.
- Não atualize uma região viva externa enquanto um diálogo modal ainda estiver aberto; aguarde o evento de fechamento.
- O botão de fechar é nativo e tem nome acessível Fechar aviso.
- Tab alcança o botão; Enter ou Espaço ativa.
- Não existe temporizador interno. A aplicação controla o prazo de remoção, se necessário.
- Use role=alert somente quando a mensagem exigir atenção imediata.

### Limitação da versão 0.1.0

O botão de fechar usa largura e altura mínimas de 44px, conforme o token de alvo de toque.

### Exemplo

    <ds-alert variant="success" title="Salvo" dismissible>
      As alterações foram salvas.
    </ds-alert>

## ds-card

**Finalidade:** agrupar conteúdo relacionado em uma superfície visual.

### Atributos

| Atributo | Tipo | Padrão | Efeito |
|---|---|---|---|
| title | texto | vazio | Exibe cabeçalho com título |
| elevated | booleano | ausente | Aplica elevação visual |

### API, semântica e teclado

Não há propriedades, métodos ou eventos próprios.

O conteúdo é colocado em um elemento section. Quando title existe, o título interno é h3. Sem título, o cabeçalho fica oculto. elevated altera somente a apresentação. O componente não é clicável e não tem teclado próprio.

O título usa nível h3. Verifique se esse nível faz sentido na hierarquia da página. Se precisar de outro nível, omita title e inclua um título semântico adequado no conteúdo.

### Exemplo

    <ds-card title="Projeto" elevated>
      <p>Descrição do projeto.</p>
      <ds-badge variant="info">Ativo</ds-badge>
    </ds-card>

## ds-dialog

**Finalidade:** executar uma tarefa curta em contexto modal.

### Atributos

| Atributo | Tipo | Padrão | Efeito |
|---|---|---|---|
| title | texto | Diálogo | Título associado por aria-labelledby |
| open | booleano | ausente | Abre o diálogo quando o host está conectado |

Filhos sem atributo slot são enviados ao corpo. Filhos com slot="footer" são enviados ao rodapé.

### API pública

| Método | Efeito |
|---|---|
| showModal() | Define open e abre o diálogo |
| close() | Remove open e fecha o diálogo |

### Eventos

| Evento | Quando ocorre | detail | Bubble |
|---|---|---|---|
| ds-close | Depois de o diálogo ser fechado e de o foco anterior conectado ter sido restaurado (ou a tentativa ter sido concluída) | nenhum | sim |

### Teclado, foco e semântica

- Usa o elemento nativo dialog.
- O título é associado por aria-labelledby.
- Ao abrir, guarda o elemento que tinha foco.
- Ao fechar, restaura o foco ao elemento anterior somente se ele ainda estiver conectado ao DOM.
- Emite ds-close depois de fechar e concluir a restauração/tentativa de foco. O consumidor pode atualizar feedback externo com segurança nesse evento.
- Escape fecha o diálogo.
- Clique no backdrop fecha o diálogo.
- O botão interno Fechar diálogo também fecha.
- Os controles do rodapé mantêm a ordem do DOM.

### Limitações

- Quando showModal() existe, o navegador fornece o comportamento modal nativo.
- Se showModal() não existir, o componente usa o atributo open como fallback. Esse fallback não oferece todas as garantias de um diálogo modal nativo, mas também emite ds-close após fechar.
- A altura máxima é 85vh e o corpo pode rolar.
- A compatibilidade cross-browser não foi validada nesta Fase 1.

### Exemplo

    <ds-dialog title="Confirmar exclusão">
      <p>Deseja excluir este registro?</p>
      <ds-button slot="footer" variant="secondary">Cancelar</ds-button>
      <ds-button slot="footer" variant="destructive">Excluir</ds-button>
    </ds-dialog>

    const dialog = document.querySelector('ds-dialog');
    dialog.showModal();
    dialog.close();


## ds-app-shell

**Finalidade:** fornecer o contrato estrutural obrigatório de aplicações com cabeçalho, navegação global opcional, conteúdo principal e rodapé.

**Regiões diretas:**
- `<header data-ds-region="header">` — obrigatório.
- `<nav data-ds-region="navigation" aria-label="…">` — opcional.
- `<main data-ds-region="main" id="main-content">` — obrigatório, exatamente um.
- `<footer data-ds-region="footer">` — obrigatório.

**Ordem:** header → navigation? → main → footer. As regiões permanecem no Light DOM; `data-ds-region` identifica o contrato e não é um slot Shadow DOM.

**Comportamento CSS:** coluna com `min-height: 100vh / 100dvh`; main flexível; footer com margem automática. O documento mantém a rolagem natural. O componente não impõe marca, dimensões internas, sticky, posicionamento fixo ou scroll container.

**Contrato normativo:** [DS-STD-APP-SHELL](DS-STD-APP-SHELL.md). Exemplo funcional: `apps/app-shell-demo`.

**Validador para testes de consumidores:** `import { validateAppShell } from '@mmcromero/ds-components/testing/app-shell';`. A função retorna `{ valid, errors }` e verifica nomes, quantidade, semântica e ordem das regiões diretas. Não mede posição/renderização no navegador.
