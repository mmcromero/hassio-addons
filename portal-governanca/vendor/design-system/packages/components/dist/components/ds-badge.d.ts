import { BaseElement } from '../utils/base-element.js';
export declare class DsBadge extends BaseElement {
    static get observedAttributes(): string[];
    private spanEl;
    private lightSlot;
    private initialized;
    connectedCallback(): void;
    disconnectedCallback(): void;
    attributeChangedCallback(): void;
    private render;
    private sync;
}
