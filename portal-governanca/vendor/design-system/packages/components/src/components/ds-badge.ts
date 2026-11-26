import { bindLightChildren } from '../utils/light-slot.js';
import { BaseElement } from '../utils/base-element.js';

export class DsBadge extends BaseElement {
  static get observedAttributes() { return ['variant']; }
  private spanEl: HTMLSpanElement | null = null;
  private lightSlot: { connect: () => void; disconnect: () => void } | null = null;
  private initialized = false;

  connectedCallback() {
    if (!this.initialized) { this.initialized = true; this.render(); }
    this.lightSlot?.connect();
    this.sync();
  }
  disconnectedCallback() { this.lightSlot?.disconnect(); }
  attributeChangedCallback() { if (this.initialized) this.sync(); }

  private render() {
    const spanEl = document.createElement('span');
    this.spanEl = spanEl;
    this.appendChild(spanEl);
    this.lightSlot = bindLightChildren(this, [spanEl], (node) => spanEl.appendChild(node));
  }

  private sync() {
    if (!this.spanEl) return;
    this.spanEl.className = `ds-badge ds-badge--${this.getAttribute('variant') || 'neutral'}`;
  }
}
