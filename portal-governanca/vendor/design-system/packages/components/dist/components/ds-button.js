import { bindLightChildren } from '../utils/light-slot.js';
import { BaseElement } from '../utils/base-element.js';
export class DsButton extends BaseElement {
    static get observedAttributes() {
        return ['variant', 'size', 'type', 'disabled', 'loading', 'aria-label'];
    }
    buttonEl = null;
    labelSpan = null;
    spinnerEl = null;
    lightSlot = null;
    initialized = false;
    connectedCallback() {
        if (!this.initialized) {
            this.initialized = true;
            this.render();
        }
        this.lightSlot?.connect();
        this.sync();
    }
    disconnectedCallback() {
        this.lightSlot?.disconnect();
    }
    attributeChangedCallback() {
        if (this.initialized)
            this.sync();
    }
    render() {
        const buttonEl = document.createElement('button');
        buttonEl.className = 'ds-btn';
        this.buttonEl = buttonEl;
        const spinnerEl = document.createElement('span');
        spinnerEl.className = 'ds-spinner';
        spinnerEl.setAttribute('aria-hidden', 'true');
        spinnerEl.style.display = 'none';
        this.spinnerEl = spinnerEl;
        const labelSpan = document.createElement('span');
        labelSpan.className = 'ds-btn-label';
        this.labelSpan = labelSpan;
        buttonEl.appendChild(spinnerEl);
        buttonEl.appendChild(labelSpan);
        this.appendChild(buttonEl);
        this.lightSlot = bindLightChildren(this, [buttonEl], (node) => {
            labelSpan.appendChild(node);
        });
    }
    sync() {
        if (!this.buttonEl || !this.spinnerEl)
            return;
        const variant = this.getAttribute('variant') || 'primary';
        const size = this.getAttribute('size') || 'md';
        const type = this.getAttribute('type') || 'button';
        const isDisabled = this.hasAttribute('disabled');
        const isLoading = this.hasAttribute('loading');
        const ariaLabel = this.getAttribute('aria-label');
        const sizeClass = size === 'sm' ? 'ds-btn--sm' : size === 'lg' ? 'ds-btn--lg' : '';
        const loadingClass = isLoading ? 'ds-btn--loading' : '';
        this.buttonEl.className = `ds-btn ds-btn--${variant} ${sizeClass} ${loadingClass}`.trim();
        this.buttonEl.type = type;
        this.buttonEl.disabled = isDisabled || isLoading;
        if (isLoading) {
            this.buttonEl.setAttribute('aria-busy', 'true');
            this.spinnerEl.style.display = 'inline-block';
        }
        else {
            this.buttonEl.removeAttribute('aria-busy');
            this.spinnerEl.style.display = 'none';
        }
        if (ariaLabel)
            this.buttonEl.setAttribute('aria-label', ariaLabel);
        else
            this.buttonEl.removeAttribute('aria-label');
    }
}
