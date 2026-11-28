import { BaseElement } from '../utils/base-element.js';
let inputIdCounter = 0;
/**
 * <ds-input> — Campo de entrada acessível com rótulo persistente, ajuda e erro inline.
 *
 * Atributos:
 * - label: texto do rótulo (obrigatório para acessibilidade)
 * - name: nome do campo
 * - type: tipo do input ('text' | 'email' | 'password' | 'search' | 'number' | 'url')
 * - value: valor do campo
 * - placeholder: texto auxiliar (não substitui o label)
 * - helper-text: texto de instrução
 * - error-message: mensagem de erro (ativa aria-invalid="true")
 * - required: boolean
 * - disabled: boolean
 */
export class DsInput extends BaseElement {
    static get observedAttributes() {
        return ['label', 'name', 'type', 'value', 'placeholder', 'helper-text', 'error-message', 'required', 'disabled'];
    }
    fieldId = `ds-input-${++inputIdCounter}`;
    labelEl = null;
    inputEl = null;
    helperEl = null;
    errorEl = null;
    initialized = false;
    get value() {
        return this.inputEl ? this.inputEl.value : (this.getAttribute('value') || '');
    }
    set value(val) {
        if (this.inputEl && this.inputEl.value !== val) {
            this.inputEl.value = val;
        }
        this.setAttribute('value', val);
    }
    connectedCallback() {
        if (!this.initialized) {
            this.initialized = true;
            this.render();
        }
        this.sync();
    }
    attributeChangedCallback(name, _oldVal, newVal) {
        if (!this.initialized)
            return;
        if (name === 'value' && this.inputEl && this.inputEl.value !== (newVal || '')) {
            this.inputEl.value = newVal || '';
        }
        this.sync();
    }
    render() {
        this.innerHTML = '';
        const wrapper = document.createElement('div');
        wrapper.className = 'ds-field';
        this.labelEl = document.createElement('label');
        this.labelEl.className = 'ds-label';
        this.labelEl.htmlFor = this.fieldId;
        this.inputEl = document.createElement('input');
        this.inputEl.className = 'ds-input-control';
        this.inputEl.id = this.fieldId;
        this.inputEl.addEventListener('input', () => {
            if (!this.inputEl)
                return;
            this.setAttribute('value', this.inputEl.value);
            this.dispatchEvent(new CustomEvent('ds-input', { detail: { value: this.inputEl.value }, bubbles: true }));
        });
        this.inputEl.addEventListener('change', () => {
            if (!this.inputEl)
                return;
            this.dispatchEvent(new CustomEvent('ds-change', { detail: { value: this.inputEl.value }, bubbles: true }));
        });
        this.helperEl = document.createElement('div');
        this.helperEl.className = 'ds-helper-text';
        this.helperEl.id = `${this.fieldId}-helper`;
        this.errorEl = document.createElement('div');
        this.errorEl.className = 'ds-error-text';
        this.errorEl.id = `${this.fieldId}-error`;
        this.errorEl.setAttribute('role', 'alert');
        wrapper.appendChild(this.labelEl);
        wrapper.appendChild(this.inputEl);
        wrapper.appendChild(this.helperEl);
        wrapper.appendChild(this.errorEl);
        this.appendChild(wrapper);
    }
    sync() {
        if (!this.labelEl || !this.inputEl || !this.helperEl || !this.errorEl)
            return;
        const labelText = this.getAttribute('label') || '';
        const isRequired = this.hasAttribute('required');
        const isDisabled = this.hasAttribute('disabled');
        const name = this.getAttribute('name') || '';
        const type = this.getAttribute('type') || 'text';
        const placeholder = this.getAttribute('placeholder') || '';
        const helperText = this.getAttribute('helper-text') || '';
        const errorMessage = this.getAttribute('error-message') || '';
        this.labelEl.textContent = labelText;
        if (isRequired) {
            const reqSpan = document.createElement('span');
            reqSpan.className = 'ds-label-required';
            reqSpan.setAttribute('aria-hidden', 'true');
            reqSpan.textContent = '*';
            this.labelEl.appendChild(reqSpan);
        }
        this.inputEl.type = type;
        this.inputEl.name = name;
        this.inputEl.placeholder = placeholder;
        this.inputEl.required = isRequired;
        this.inputEl.disabled = isDisabled;
        const attrValue = this.getAttribute('value');
        if (attrValue !== null && this.inputEl.value !== attrValue) {
            this.inputEl.value = attrValue;
        }
        const describedBy = [];
        if (helperText) {
            this.helperEl.textContent = helperText;
            this.helperEl.style.display = 'block';
            describedBy.push(this.helperEl.id);
        }
        else {
            this.helperEl.textContent = '';
            this.helperEl.style.display = 'none';
        }
        if (errorMessage) {
            this.errorEl.textContent = errorMessage;
            this.errorEl.style.display = 'block';
            this.inputEl.setAttribute('aria-invalid', 'true');
            describedBy.push(this.errorEl.id);
        }
        else {
            this.errorEl.textContent = '';
            this.errorEl.style.display = 'none';
            this.inputEl.removeAttribute('aria-invalid');
        }
        if (describedBy.length > 0) {
            this.inputEl.setAttribute('aria-describedby', describedBy.join(' '));
        }
        else {
            this.inputEl.removeAttribute('aria-describedby');
        }
    }
}
