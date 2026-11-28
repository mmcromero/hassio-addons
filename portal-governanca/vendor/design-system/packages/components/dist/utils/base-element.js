/**
 * BaseElement — Classe base server-safe para Custom Elements.
 *
 * Em ambiente Node.js puro sem DOM (SSR), `globalThis.HTMLElement` não existe.
 * Fazer `class DsX extends BaseElement` permite que o módulo seja importado no
 * Node/SSR sem lançar `ReferenceError: HTMLElement is not defined` durante a avaliação
 * estática das classes.
 *
 * No browser ou ambientes com DOM virtual (happy-dom, jsdom, linkedom),
 * `BaseElement` é exatamente o `globalThis.HTMLElement` nativo.
 */
export const BaseElement = typeof globalThis !== 'undefined' && typeof globalThis.HTMLElement !== 'undefined'
    ? globalThis.HTMLElement
    : class {
        // Fallback no-op para propriedades mínimas de elemento caso acessadas estaticamente
        static observedAttributes;
    };
