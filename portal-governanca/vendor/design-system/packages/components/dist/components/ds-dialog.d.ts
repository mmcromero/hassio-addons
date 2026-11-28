import { BaseElement } from '../utils/base-element.js';
export declare class DsDialog extends BaseElement {
    static get observedAttributes(): string[];
    private dialogId;
    private dialogEl;
    private titleEl;
    private bodyEl;
    private footerEl;
    private lightSlot;
    private previousFocus;
    private initialized;
    private closePending;
    connectedCallback(): void;
    disconnectedCallback(): void;
    attributeChangedCallback(name: string): void;
    showModal(): void;
    close(): void;
    private render;
    private sync;
    private finishClose;
}
