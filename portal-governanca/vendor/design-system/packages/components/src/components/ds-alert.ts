import { bindLightChildren } from '../utils/light-slot.js';
import { BaseElement } from '../utils/base-element.js';

export class DsAlert extends BaseElement {
  static get observedAttributes() { return ['variant', 'title', 'dismissible', 'aria-live']; }
  private containerEl: HTMLDivElement | null = null;
  private titleEl: HTMLDivElement | null = null;
  private closeBtn: HTMLButtonElement | null = null;
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
    const containerEl = document.createElement('div');
    this.containerEl = containerEl;
    const content = document.createElement('div');
    content.className = 'ds-alert-content';
    const titleEl = document.createElement('div');
    titleEl.className = 'ds-alert-title';
    this.titleEl = titleEl;
    const bodyEl = document.createElement('div');
    bodyEl.className = 'ds-alert-body';
    content.appendChild(titleEl);
    content.appendChild(bodyEl);
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'ds-alert-close';
    closeBtn.setAttribute('aria-label', 'Fechar aviso');
    closeBtn.textContent = '✕';
    closeBtn.addEventListener('click', () => {
      this.dispatchEvent(new CustomEvent('ds-dismiss', { bubbles: true }));
      this.remove();
    });
    this.closeBtn = closeBtn;
    containerEl.appendChild(content);
    containerEl.appendChild(closeBtn);
    this.appendChild(containerEl);
    this.lightSlot = bindLightChildren(this, [containerEl], (node) => bodyEl.appendChild(node));
  }

  private sync() {
    if (!this.containerEl || !this.titleEl || !this.closeBtn) return;
    const variant = this.getAttribute('variant') || 'info';
    const title = this.getAttribute('title') || '';
    this.containerEl.className = `ds-alert ds-alert--${variant}`;
    if (this.getAttribute('aria-live') === 'off') {
      this.containerEl.setAttribute('role', 'group');
      this.containerEl.setAttribute('aria-live', 'off');
    } else {
      this.containerEl.setAttribute('role', variant === 'error' || variant === 'warning' ? 'alert' : 'status');
      this.containerEl.removeAttribute('aria-live');
    }
    this.titleEl.textContent = title;
    this.titleEl.style.display = title ? 'block' : 'none';
    this.closeBtn.style.display = this.hasAttribute('dismissible') ? 'inline-flex' : 'none';
  }
}
