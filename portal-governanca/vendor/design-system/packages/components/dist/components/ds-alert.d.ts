import { BaseElement } from '../utils/base-element.js';
export declare class DsAlert extends BaseElement {
    static get observedAttributes(): string[];
    private containerEl;
    private titleEl;
    private closeBtn;
    private lightSlot;
    private initialized;
    connectedCallback(): void;
    disconnectedCallback(): void;
    attributeChangedCallback(): void;
    private render;
    private sync;
}
