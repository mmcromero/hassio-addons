# Guia do primeiro consumidor

**Versão do Design System:** 0.1.0 — desenvolvimento, não publicada.  
**Escopo:** consumo local por workspace ou dependência file:.  
**Fora do escopo:** publicação npm, distribuição automática, migração de aplicações e construção do Portal de Governança.

## 1. Estrutura e ambiente

O monorepo contém:
- packages/tokens: tokens DTCG e CSS;
- packages/components: Custom Elements e estilos;
- apps/docs: catálogo;
- apps/demo: aplicação de exemplo.
- apps/app-shell-demo: exemplo oficial do App Shell com três rotas e extensões de conteúdo.

A execução validada anteriormente usou Node.js 24.22.2 e npm 11.19.1. Esses números identificam o ambiente observado; ainda não existe uma versão mínima oficial declarada.

Antes de implementar a estrutura global, leia [DS-STD-APP-SHELL](DS-STD-APP-SHELL.md) e adote `ds-app-shell`; o padrão é obrigatório para novos produtos com cabeçalho/navegação/rodapé globais.

## 2. Consumo no mesmo monorepo

1. Inclua a pasta do consumidor no campo workspaces da raiz.
2. Adicione @mmcromero/ds-tokens e @mmcromero/ds-components às dependências do consumidor, com a versão local 0.1.0.
3. Execute npm install na raiz.
4. Gere os pacotes:

    npm run build

5. Importe na entrada da aplicação:

    import '@mmcromero/ds-tokens/css';
    import '@mmcromero/ds-components/styles.css';
    import '@mmcromero/ds-components';

## 3. Consumo em repositório separado

Mantenha um checkout autorizado do Design System ao lado do repositório consumidor.

    workspace/
      design-system/
      produto-consumidor/

No package.json do consumidor:

    {
      "dependencies": {
        "@mmcromero/ds-tokens": "file:../design-system/packages/tokens",
        "@mmcromero/ds-components": "file:../design-system/packages/components"
      }
    }

Antes de instalar ou atualizar:

1. Entre no checkout design-system.
2. Confira e registre o SHA que o consumidor usará.
3. Execute npm ci e npm run build.
4. Entre no consumidor e execute npm install.
5. Confira os pacotes resolvidos em node_modules/@mmcromero/.

Quando o Design System mudar, repita o build e a instalação local. A dependência file: aponta para um caminho local; ela não fixa sozinha o commit Git. Registre o SHA no repositório consumidor.

## 4. CSS e registro

Importe nesta ordem:

    import '@mmcromero/ds-tokens/css';
    import '@mmcromero/ds-components/styles.css';
    import '@mmcromero/ds-components';

O primeiro import define as variáveis. O segundo importa os estilos dos componentes. O CSS do consumidor deve vir depois.

O pacote registra os sete Custom Elements automaticamente no navegador. Se precisar controlar o registro:

    import { registerAllComponents } from '@mmcromero/ds-components';
    registerAllComponents();

A função não redefine elementos já registrados.

## 5. App Shell obrigatório para aplicações

Todo consumidor com estrutura global deve adotar o App Shell oficial. Importe os pacotes normalmente e use o contrato semântico abaixo:

```html
<ds-app-shell>
  <header data-ds-region="header">
    <a class="skip-link" href="#main-content">Pular para o conteúdo</a>
    <!-- identidade e controles do produto -->
  </header>
  <nav data-ds-region="navigation" aria-label="Navegação principal">
    <!-- navegação global; opcional -->
  </nav>
  <main data-ds-region="main" id="main-content" tabindex="-1">
    <!-- conteúdo da rota -->
  </main>
  <footer data-ds-region="footer">
    <!-- rodapé do produto -->
  </footer>
</ds-app-shell>
```

- As regiões devem ser filhos diretos do `ds-app-shell`, na ordem indicada.
- Cabeçalho, navegação e rodapé permanecem estáveis ao trocar rotas; atualize apenas o conteúdo de main.
- Não use `position: fixed/absolute`, altura fixa ou rolagem vertical interna como solução global.
- O CSS do pacote já fornece a estrutura flexível; o consumidor personaliza o interior com seus tokens e estilos. Defina `body { margin: 0; }` para remover a margem padrão do navegador.
- Teste páginas curtas, médias e longas; rotas; larguras móveis/intermediárias/desktop; teclado e foco.
- Inclua `validateAppShell` nos testes do consumidor para validar a estrutura DOM:

  ```ts
  import { validateAppShell } from '@mmcromero/ds-components/testing/app-shell';
  const result = validateAppShell(document.querySelector('ds-app-shell')!);
  expect(result.valid, result.errors.join('\\n')).toBe(true);
  ```
- Leia [DS-STD-APP-SHELL](DS-STD-APP-SHELL.md) antes de implementar. Não crie estrutura alternativa sem justificativa registrada e revisão explícita.

### Demo funcional

A aplicação `@mmcromero/ds-app-shell-demo` demonstra as três situações e navegação entre elas:

```bash
npm run dev --workspace @mmcromero/ds-app-shell-demo
```

Build específico:

```bash
npm run build --workspace @mmcromero/ds-app-shell-demo
```

## 6. Temas

O tema padrão não exige atributo. Para os outros temas:

    <html data-theme="dark">
    <html data-theme="governance">

Cada consumidor pode definir a própria identidade por tokens de tema. Preserve os nomes semânticos.

## 7. Exemplo

    <ds-card title="Dados da conta">
      <ds-input label="Nome" name="name" required
        helper-text="Informe o nome de exibição"></ds-input>
      <ds-button variant="primary" type="submit">Salvar</ds-button>
    </ds-card>

Consulte a referência de API para atributos, eventos e limites de cada componente.

## 8. Build e testes

No repositório Design System:

    npm ci
    npm run build
    npm test

Os testes de contrato do App Shell estão em `packages/components/test/app-shell*.test.ts` e entram na suíte do pacote de componentes. O consumidor deve manter teste próprio de conformidade e validar o layout em navegador real; os testes DOM/CSS não substituem a verificação geométrica visual.

No consumidor, execute também o build e os testes próprios. O build do Design System não substitui os testes do consumidor.

## 9. Limites conhecidos

- Não há publicação npm nesta fase.
- Registre o SHA do Design System usado pelo consumidor.
- A importação em Node sem DOM é segura. Renderização SSR em string não está implementada.
- Chromium 143 é o único navegador real registrado nesta Fase 1. Firefox, Safari e Edge não foram validados.
- A sessão manual com leitor de tela está pendente. Consulte VALIDACAO-LEITOR-DE-TELA.md.
- A política npm allowScripts permanece restritiva. O aviso do postinstall do esbuild está documentado; não habilite scripts automaticamente.
- Não copie os pacotes para dentro do código do consumidor. Use as dependências locais descritas neste guia.

## 10. Versionamento e migração

A versão 0.1.0 nos manifests identifica um pacote em desenvolvimento; não significa que exista uma release publicada.

Antes de adotar:
- registre o SHA;
- execute build e testes do Design System;
- execute testes de integração do consumidor;
- documente exceções visuais ou de comportamento;
- não atualize outros projetos automaticamente.

A política de versão semântica, depreciação e distribuição será definida antes da Fase 3.
