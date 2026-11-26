import { bindLightChildren } from '../utils/light-slot.js';
import { BaseElement } from '../utils/base-element.js';

export class DsCard extends BaseElement {
  static get observedAttributes() { return ['title', 'elevated']; }
  private containerEl: HTMLElement | null = null;
  private headerEl: HTMLElement | null = null;
  private titleEl: HTMLHeadingElement | null = null;
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
    const containerEl = document.createElement('section');
    this.containerEl = containerEl;
    const headerEl = document.createElement('header');
    headerEl.className = 'ds-card-header';
    this.headerEl = headerEl;
    const titleEl = document.createElement('h3');
    titleEl.className = 'ds-card-title';
    headerEl.appendChild(titleEl);
    this.titleEl = titleEl;
    const bodyEl = document.createElement('div');
    bodyEl.className = 'ds-card-body';
    containerEl.appendChild(headerEl);
    containerEl.appendChild(bodyEl);
    this.appendChild(containerEl);
    this.lightSlot = bindLightChildren(this, [containerEl], (node) => bodyEl.appendChild(node));
  }

  private sync() {
    if (!this.containerEl || !this.headerEl || !this.titleEl) return;
    const title = this.getAttribute('title') || '';
    this.containerEl.className = `ds-card${this.hasAttribute('elevated') ? ' ds-card--elevated' : ''}`;
    this.titleEl.textContent = title;
    this.headerEl.style.display = title ? 'flex' : 'none';
  }
}
