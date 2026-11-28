import { BaseElement } from '../utils/base-element.js';
export declare class DsButton extends BaseElement {
    static get observedAttributes(): string[];
    private buttonEl;
    private labelSpan;
    private spinnerEl;
    private lightSlot;
    private initialized;
    connectedCallback(): void;
    disconnectedCallback(): void;
    attributeChangedCallback(): void;
    private render;
    private sync;
}
