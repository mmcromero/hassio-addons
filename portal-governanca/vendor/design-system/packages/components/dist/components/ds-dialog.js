import { bindLightChildren } from '../utils/light-slot.js';
import { BaseElement } from '../utils/base-element.js';
let dialogIdCounter = 0;
export class DsDialog extends BaseElement {
    static get observedAttributes() { return ['title', 'open']; }
    dialogId = `ds-dialog-title-${++dialogIdCounter}`;
    dialogEl = null;
    titleEl = null;
    bodyEl = null;
    footerEl = null;
    lightSlot = null;
    previousFocus = null;
    initialized = false;
    closePending = false;
    connectedCallback() {
        if (!this.initialized) {
            this.initialized = true;
            this.render();
        }
        this.lightSlot?.connect();
        this.sync();
    }
    disconnectedCallback() { this.lightSlot?.disconnect(); }
    attributeChangedCallback(name) { if (this.initialized)
        this.sync(name === 'open'); }
    showModal() { this.setAttribute('open', ''); }
    close() { this.removeAttribute('open'); }
    render() {
        const dialogEl = document.createElement('dialog');
        dialogEl.className = 'ds-dialog-native';
        dialogEl.setAttribute('aria-labelledby', this.dialogId);
        this.dialogEl = dialogEl;
        const header = document.createElement('header');
        header.className = 'ds-dialog-header';
        const titleEl = document.createElement('h2');
        titleEl.className = 'ds-dialog-title';
        titleEl.id = this.dialogId;
        this.titleEl = titleEl;
        const closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'ds-dialog-close';
        closeBtn.setAttribute('aria-label', 'Fechar diálogo');
        closeBtn.textContent = '✕';
        closeBtn.addEventListener('click', () => this.close());
        header.appendChild(titleEl);
        header.appendChild(closeBtn);
        const bodyEl = document.createElement('div');
        bodyEl.className = 'ds-dialog-body';
        this.bodyEl = bodyEl;
        const footerEl = document.createElement('footer');
        footerEl.className = 'ds-dialog-footer';
        footerEl.style.display = 'none';
        this.footerEl = footerEl;
        dialogEl.appendChild(header);
        dialogEl.appendChild(bodyEl);
        dialogEl.appendChild(footerEl);
        this.appendChild(dialogEl);
        this.lightSlot = bindLightChildren(this, [dialogEl], (node) => {
            if (node instanceof Element && node.getAttribute('slot') === 'footer') {
                footerEl.appendChild(node);
                footerEl.style.display = 'flex';
            }
            else {
                bodyEl.appendChild(node);
            }
        });
        dialogEl.addEventListener('click', (e) => { if (e.target === dialogEl)
            this.close(); });
        dialogEl.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                this.close();
            }
        });
        this.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.hasAttribute('open')) {
                e.preventDefault();
                this.close();
            }
        });
        dialogEl.addEventListener('close', () => {
            if (this.hasAttribute('open'))
                this.removeAttribute('open');
            this.finishClose();
        });
    }
    sync(openChanged = false) {
        if (!this.dialogEl || !this.titleEl)
            return;
        this.titleEl.textContent = this.getAttribute('title') || 'Diálogo';
        const shouldBeOpen = this.hasAttribute('open');
        if (shouldBeOpen && !this.dialogEl.open) {
            this.previousFocus = document.activeElement;
            this.closePending = true;
            typeof this.dialogEl.showModal === 'function'
                ? this.dialogEl.showModal()
                : this.dialogEl.setAttribute('open', '');
        }
        else if (!shouldBeOpen && this.dialogEl.open) {
            if (typeof this.dialogEl.close === 'function') {
                // The native close event is queued by HTMLDialogElement.close().
                // Restore focus only from that event; doing it synchronously here lets
                // the browser's later native focus restoration steal focus back from
                // the newly rendered logical target.
                this.dialogEl.close();
            }
            else {
                this.dialogEl.removeAttribute('open');
                this.finishClose();
            }
        }
        else if (openChanged && !shouldBeOpen) {
            this.finishClose();
        }
    }
    finishClose() {
        if (!this.closePending)
            return;
        this.closePending = false;
        const returnTarget = this.previousFocus;
        this.previousFocus = null;
        if (returnTarget?.isConnected)
            returnTarget.focus();
        this.dispatchEvent(new CustomEvent('ds-close', { bubbles: true }));
    }
}
