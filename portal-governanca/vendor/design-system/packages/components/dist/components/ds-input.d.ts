import { BaseElement } from '../utils/base-element.js';
/**
 * <ds-input> — Campo de entrada acessível com rótulo persistente, ajuda e erro inline.
 *
 * Atributos:
 * - label: texto do rótulo (obrigatório para acessibilidade)
 * - name: nome do campo
 * - type: tipo do input ('text' | 'email' | 'password' | 'search' | 'number' | 'url')
 * - value: valor do campo
 * - placeholder: texto auxiliar (não substitui o label)
 * - helper-text: texto de instrução
 * - error-message: mensagem de erro (ativa aria-invalid="true")
 * - required: boolean
 * - disabled: boolean
 */
export declare class DsInput extends BaseElement {
    static get observedAttributes(): string[];
    private fieldId;
    private labelEl;
    private inputEl;
    private helperEl;
    private errorEl;
    private initialized;
    get value(): string;
    set value(val: string);
    connectedCallback(): void;
    attributeChangedCallback(name: string, _oldVal: string | null, newVal: string | null): void;
    private render;
    private sync;
}
