# DS-STD-APP-SHELL — Padrão estrutural de aplicação

**Estado:** padrão oficial obrigatório para novos produtos com estrutura global de aplicação.  
**Versão:** 1.0 — 25/11/2026  
**Implementação de referência:** `ds-app-shell` em `@mmcromero/ds-components`.  
**Exemplo funcional:** `apps/app-shell-demo`.

## 1. Objetivo e alcance

O App Shell define a estrutura persistente que envolve as rotas de uma aplicação: cabeçalho, navegação global opcional, conteúdo principal e rodapé. Seu contrato é estrutural e comportamental; não impõe marca, paleta, logotipo, composição visual ou conteúdo idênticos entre produtos.

Todo novo produto da Fábrica de Ideias que possua uma estrutura global de aplicação DEVE adotar `ds-app-shell` e este contrato. Exceções exigem justificativa técnica registrada no projeto consumidor e revisão explícita; não podem surgir apenas por preferência ou desconhecimento do padrão.

## 2. Contrato de marcação

Use os elementos semânticos como filhos diretos do componente:

```html
<ds-app-shell>
  <header data-ds-region="header">
    <!-- identidade e conteúdo do cabeçalho -->
  </header>

  <nav data-ds-region="navigation" aria-label="Navegação principal">
    <!-- navegação global; região opcional -->
  </nav>

  <main data-ds-region="main" id="main-content" tabindex="-1">
    <!-- conteúdo variável da rota -->
  </main>

  <footer data-ds-region="footer">
    <!-- conteúdo do rodapé -->
  </footer>
</ds-app-shell>
```

Regras:
- `header`, `main` e `footer` são obrigatórios; `nav` é opcional.
- Deve existir exatamente um `main` principal.
- Ordem direta obrigatória: header → navigation (se existir) → main → footer.
- As regiões ficam no Light DOM. `data-ds-region` é um contrato de identificação do App Shell, não distribuição por Shadow DOM/slot nativo.
- Cabeçalho, navegação e rodapé são persistentes entre rotas; somente a região principal deve ser substituída durante navegação comum.
- Inclua link para saltar ao conteúdo, visível ao receber foco, antes ou dentro do cabeçalho.
- Nomeie a navegação com `aria-label` ou `aria-labelledby`; indique o destino atual com `aria-current="page"`.
- Mantenha títulos de página e hierarquia de headings dentro do `main`.

## 3. Comportamento estrutural obrigatório

### Cabeçalho e navegação
- Permanecem no início da estrutura e na mesma ordem em todas as rotas.
- Não podem ser centralizados verticalmente pelo layout da página nem deslocados pela quantidade de conteúdo.
- Não usar `position: absolute` ou `fixed` como solução estrutural genérica.
- Sticky é uma decisão opcional do produto, não o padrão. Se adotado, deve ser justificado e testado quanto a foco, âncoras, zoom e viewport móvel.

### Conteúdo principal
- Ocupa o espaço livre quando a página tem pouco conteúdo.
- Cresce naturalmente quando o conteúdo excede a altura disponível.
- Não recebe altura fixa que corte conteúdo; largura, espaçamento e limites internos são responsabilidade do consumidor, usando tokens.
- Deve permitir foco, zoom, reflow e leitura em telas estreitas sem sobreposição.

### Rodapé
- Fica junto ao limite inferior da área disponível em páginas curtas.
- Em páginas longas, vem depois do conteúdo e é alcançado pela rolagem natural.
- Permanece no fluxo normal; não usar posicionamento absoluto/fixo como solução genérica.

### Rolagem
- O documento é a área de rolagem padrão.
- Não criar `overflow-y: auto/scroll` no shell, no main ou em wrappers de página por padrão.
- Rolagem interna só pode ser usada em regiões funcionais delimitadas (por exemplo, painel de dados), com necessidade demonstrada, foco/teclado acessíveis e comportamento móvel validado.
- Navegação horizontal localizada pode existir para menus estreitos, sem provocar rolagem horizontal da página inteira.

## 4. Implementação e personalização

`ds-app-shell` é um Custom Element estrutural em Light DOM. Seus estilos definem apenas o contrato de layout:
- coluna vertical com altura mínima de viewport (`100vh` com fallback para `100dvh`);
- regiões superiores e rodapé sem encolhimento;
- main flexível (`flex: 1 0 auto`);
- rodapé com margem automática no início para ocupar o espaço restante.

O componente não estiliza a identidade interna. O consumidor pode personalizar logotipo, cores/tema, altura, navegação, conteúdo e organização interna das regiões, preservando semântica, ordem e comportamento.

Não confundir altura mínima com altura fixa: o shell pode crescer além do viewport. Não limitar a rolagem do documento.

## 5. Acessibilidade e responsividade

- Usar landmarks HTML nativos e apenas um `main`.
- Link de salto para o conteúdo e foco visível.
- Navegação completa por teclado, ordem de foco lógica e `aria-current` correto.
- Cabeçalho/rodapé não podem cobrir conteúdo ou foco em zoom de 200%/400%.
- Validar ao menos 320, 375, 768, 1024 e 1440 CSS px, além de larguras intermediárias.
- Respeitar orientação, teclado virtual, safe areas e preferências de movimento reduzido quando aplicáveis.
- Automatizar verificações semânticas/axe e executar inspeção visual/funcional em navegador real. Axe isolado não comprova comportamento geométrico nem conformidade completa.

## 6. Testes de conformidade

Cada consumidor deve manter testes que comprovem:
1. existência e ordem header → navigation? → main → footer;
2. exatamente um main e landmarks nomeados;
3. cabeçalho/rodapé preservados durante mudança de rota;
4. página curta: cabeçalho no topo e rodapé no fim do viewport;
5. página longa: main cresce e rodapé fica depois do conteúdo;
6. ausência de sobreposição e de posicionamento fixo/absoluto genérico;
7. rolagem natural do documento, sem scroll container global independente;
8. comportamento em larguras móveis, intermediárias e desktop;
9. teclado, link de salto, foco e tecnologia assistiva nos fluxos aplicáveis.

Os testes DOM/CSS verificam contrato e regressões estáticas; a posição real dos elementos deve ser validada com browser layout tests ou inspeção manual em navegador. Não marcar teste visual como PASS sem execução.

O exemplo de conformidade está em `apps/app-shell-demo`; testes do componente em `packages/components/test/app-shell*.test.ts`. O pacote exporta `validateAppShell` em `@mmcromero/ds-components/testing/app-shell` para validar a estrutura DOM dentro da suíte de cada consumidor. Esse helper não substitui browser tests de geometria.

## 7. Adoção por agentes e desenvolvedores

Antes de construir uma interface:
1. ler `AGENTS.md`, esta norma e `GUIA-PRIMEIRO-CONSUMIDOR.md`;
2. consultar o catálogo e a API de componentes antes de criar equivalentes;
3. fixar o SHA do Design System utilizado no projeto consumidor;
4. adotar `ds-app-shell` quando houver estrutura global;
5. implementar as regiões semânticas e manter as regiões globais estáveis entre rotas;
6. adicionar/ajustar testes de conformidade no próprio consumidor;
7. registrar SHA, exceções justificadas e evidências no repositório consumidor.

O commit desta norma não comprova que projetos existentes ou chats/agentes externos já a receberam. Esta missão não migra nem altera consumidores existentes.
