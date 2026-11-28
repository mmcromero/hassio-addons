import { BaseElement } from '../utils/base-element.js';
export declare class DsCard extends BaseElement {
    static get observedAttributes(): string[];
    private containerEl;
    private headerEl;
    private titleEl;
    private lightSlot;
    private initialized;
    connectedCallback(): void;
    disconnectedCallback(): void;
    attributeChangedCallback(): void;
    private render;
    private sync;
}
