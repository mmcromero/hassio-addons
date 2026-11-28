"use strict";
(() => {
  // src/utils/light-slot.ts
  function bindLightChildren(host, internalRoots, routeNode) {
    const isInternal = (node) => internalRoots.includes(node);
    let observer = null;
    const connect = () => {
      for (const node of Array.from(host.childNodes)) {
        if (!isInternal(node)) {
          routeNode(node);
        }
      }
      observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
          for (const added of Array.from(mutation.addedNodes)) {
            if (added.parentNode === host && !isInternal(added)) {
              routeNode(added);
            }
          }
        }
      });
      observer.observe(host, { childList: true });
    };
    const disconnect = () => {
      observer?.disconnect();
      observer = null;
    };
    return { connect, disconnect };
  }

  // src/utils/base-element.ts
  var BaseElement = typeof globalThis !== "undefined" && typeof globalThis.HTMLElement !== "undefined" ? globalThis.HTMLElement : class {
    // Fallback no-op para propriedades mínimas de elemento caso acessadas estaticamente
    static observedAttributes;
  };

  // src/components/ds-button.ts
  var DsButton = class extends BaseElement {
    static get observedAttributes() {
      return ["variant", "size", "type", "disabled", "loading", "aria-label"];
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
      if (this.initialized) this.sync();
    }
    render() {
      const buttonEl = document.createElement("button");
      buttonEl.className = "ds-btn";
      this.buttonEl = buttonEl;
      const spinnerEl = document.createElement("span");
      spinnerEl.className = "ds-spinner";
      spinnerEl.setAttribute("aria-hidden", "true");
      spinnerEl.style.display = "none";
      this.spinnerEl = spinnerEl;
      const labelSpan = document.createElement("span");
      labelSpan.className = "ds-btn-label";
      this.labelSpan = labelSpan;
      buttonEl.appendChild(spinnerEl);
      buttonEl.appendChild(labelSpan);
      this.appendChild(buttonEl);
      this.lightSlot = bindLightChildren(this, [buttonEl], (node) => {
        labelSpan.appendChild(node);
      });
    }
    sync() {
      if (!this.buttonEl || !this.spinnerEl) return;
      const variant = this.getAttribute("variant") || "primary";
      const size = this.getAttribute("size") || "md";
      const type = this.getAttribute("type") || "button";
      const isDisabled = this.hasAttribute("disabled");
      const isLoading = this.hasAttribute("loading");
      const ariaLabel = this.getAttribute("aria-label");
      const sizeClass = size === "sm" ? "ds-btn--sm" : size === "lg" ? "ds-btn--lg" : "";
      const loadingClass = isLoading ? "ds-btn--loading" : "";
      this.buttonEl.className = `ds-btn ds-btn--${variant} ${sizeClass} ${loadingClass}`.trim();
      this.buttonEl.type = type;
      this.buttonEl.disabled = isDisabled || isLoading;
      if (isLoading) {
        this.buttonEl.setAttribute("aria-busy", "true");
        this.spinnerEl.style.display = "inline-block";
      } else {
        this.buttonEl.removeAttribute("aria-busy");
        this.spinnerEl.style.display = "none";
      }
      if (ariaLabel) this.buttonEl.setAttribute("aria-label", ariaLabel);
      else this.buttonEl.removeAttribute("aria-label");
    }
  };

  // src/components/ds-input.ts
  var inputIdCounter = 0;
  var DsInput = class extends BaseElement {
    static get observedAttributes() {
      return ["label", "name", "type", "value", "placeholder", "helper-text", "error-message", "required", "disabled"];
    }
    fieldId = `ds-input-${++inputIdCounter}`;
    labelEl = null;
    inputEl = null;
    helperEl = null;
    errorEl = null;
    initialized = false;
    get value() {
      return this.inputEl ? this.inputEl.value : this.getAttribute("value") || "";
    }
    set value(val) {
      if (this.inputEl && this.inputEl.value !== val) {
        this.inputEl.value = val;
      }
      this.setAttribute("value", val);
    }
    connectedCallback() {
      if (!this.initialized) {
        this.initialized = true;
        this.render();
      }
      this.sync();
    }
    attributeChangedCallback(name, _oldVal, newVal) {
      if (!this.initialized) return;
      if (name === "value" && this.inputEl && this.inputEl.value !== (newVal || "")) {
        this.inputEl.value = newVal || "";
      }
      this.sync();
    }
    render() {
      this.innerHTML = "";
      const wrapper = document.createElement("div");
      wrapper.className = "ds-field";
      this.labelEl = document.createElement("label");
      this.labelEl.className = "ds-label";
      this.labelEl.htmlFor = this.fieldId;
      this.inputEl = document.createElement("input");
      this.inputEl.className = "ds-input-control";
      this.inputEl.id = this.fieldId;
      this.inputEl.addEventListener("input", () => {
        if (!this.inputEl) return;
        this.setAttribute("value", this.inputEl.value);
        this.dispatchEvent(new CustomEvent("ds-input", { detail: { value: this.inputEl.value }, bubbles: true }));
      });
      this.inputEl.addEventListener("change", () => {
        if (!this.inputEl) return;
        this.dispatchEvent(new CustomEvent("ds-change", { detail: { value: this.inputEl.value }, bubbles: true }));
      });
      this.helperEl = document.createElement("div");
      this.helperEl.className = "ds-helper-text";
      this.helperEl.id = `${this.fieldId}-helper`;
      this.errorEl = document.createElement("div");
      this.errorEl.className = "ds-error-text";
      this.errorEl.id = `${this.fieldId}-error`;
      this.errorEl.setAttribute("role", "alert");
      wrapper.appendChild(this.labelEl);
      wrapper.appendChild(this.inputEl);
      wrapper.appendChild(this.helperEl);
      wrapper.appendChild(this.errorEl);
      this.appendChild(wrapper);
    }
    sync() {
      if (!this.labelEl || !this.inputEl || !this.helperEl || !this.errorEl) return;
      const labelText = this.getAttribute("label") || "";
      const isRequired = this.hasAttribute("required");
      const isDisabled = this.hasAttribute("disabled");
      const name = this.getAttribute("name") || "";
      const type = this.getAttribute("type") || "text";
      const placeholder = this.getAttribute("placeholder") || "";
      const helperText = this.getAttribute("helper-text") || "";
      const errorMessage = this.getAttribute("error-message") || "";
      this.labelEl.textContent = labelText;
      if (isRequired) {
        const reqSpan = document.createElement("span");
        reqSpan.className = "ds-label-required";
        reqSpan.setAttribute("aria-hidden", "true");
        reqSpan.textContent = "*";
        this.labelEl.appendChild(reqSpan);
      }
      this.inputEl.type = type;
      this.inputEl.name = name;
      this.inputEl.placeholder = placeholder;
      this.inputEl.required = isRequired;
      this.inputEl.disabled = isDisabled;
      const attrValue = this.getAttribute("value");
      if (attrValue !== null && this.inputEl.value !== attrValue) {
        this.inputEl.value = attrValue;
      }
      const describedBy = [];
      if (helperText) {
        this.helperEl.textContent = helperText;
        this.helperEl.style.display = "block";
        describedBy.push(this.helperEl.id);
      } else {
        this.helperEl.textContent = "";
        this.helperEl.style.display = "none";
      }
      if (errorMessage) {
        this.errorEl.textContent = errorMessage;
        this.errorEl.style.display = "block";
        this.inputEl.setAttribute("aria-invalid", "true");
        describedBy.push(this.errorEl.id);
      } else {
        this.errorEl.textContent = "";
        this.errorEl.style.display = "none";
        this.inputEl.removeAttribute("aria-invalid");
      }
      if (describedBy.length > 0) {
        this.inputEl.setAttribute("aria-describedby", describedBy.join(" "));
      } else {
        this.inputEl.removeAttribute("aria-describedby");
      }
    }
  };

  // src/components/ds-badge.ts
  var DsBadge = class extends BaseElement {
    static get observedAttributes() {
      return ["variant"];
    }
    spanEl = null;
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
      if (this.initialized) this.sync();
    }
    render() {
      const spanEl = document.createElement("span");
      this.spanEl = spanEl;
      this.appendChild(spanEl);
      this.lightSlot = bindLightChildren(this, [spanEl], (node) => spanEl.appendChild(node));
    }
    sync() {
      if (!this.spanEl) return;
      this.spanEl.className = `ds-badge ds-badge--${this.getAttribute("variant") || "neutral"}`;
    }
  };

  // src/components/ds-alert.ts
  var DsAlert = class extends BaseElement {
    static get observedAttributes() {
      return ["variant", "title", "dismissible", "aria-live"];
    }
    containerEl = null;
    titleEl = null;
    closeBtn = null;
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
      if (this.initialized) this.sync();
    }
    render() {
      const containerEl = document.createElement("div");
      this.containerEl = containerEl;
      const content = document.createElement("div");
      content.className = "ds-alert-content";
      const titleEl = document.createElement("div");
      titleEl.className = "ds-alert-title";
      this.titleEl = titleEl;
      const bodyEl = document.createElement("div");
      bodyEl.className = "ds-alert-body";
      content.appendChild(titleEl);
      content.appendChild(bodyEl);
      const closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.className = "ds-alert-close";
      closeBtn.setAttribute("aria-label", "Fechar aviso");
      closeBtn.textContent = "\u2715";
      closeBtn.addEventListener("click", () => {
        this.dispatchEvent(new CustomEvent("ds-dismiss", { bubbles: true }));
        this.remove();
      });
      this.closeBtn = closeBtn;
      containerEl.appendChild(content);
      containerEl.appendChild(closeBtn);
      this.appendChild(containerEl);
      this.lightSlot = bindLightChildren(this, [containerEl], (node) => bodyEl.appendChild(node));
    }
    sync() {
      if (!this.containerEl || !this.titleEl || !this.closeBtn) return;
      const variant = this.getAttribute("variant") || "info";
      const title = this.getAttribute("title") || "";
      this.containerEl.className = `ds-alert ds-alert--${variant}`;
      if (this.getAttribute("aria-live") === "off") {
        this.containerEl.setAttribute("role", "group");
        this.containerEl.setAttribute("aria-live", "off");
      } else {
        this.containerEl.setAttribute("role", variant === "error" || variant === "warning" ? "alert" : "status");
        this.containerEl.removeAttribute("aria-live");
      }
      this.titleEl.textContent = title;
      this.titleEl.style.display = title ? "block" : "none";
      this.closeBtn.style.display = this.hasAttribute("dismissible") ? "inline-flex" : "none";
    }
  };

  // src/components/ds-card.ts
  var DsCard = class extends BaseElement {
    static get observedAttributes() {
      return ["title", "elevated"];
    }
    containerEl = null;
    headerEl = null;
    titleEl = null;
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
      if (this.initialized) this.sync();
    }
    render() {
      const containerEl = document.createElement("section");
      this.containerEl = containerEl;
      const headerEl = document.createElement("header");
      headerEl.className = "ds-card-header";
      this.headerEl = headerEl;
      const titleEl = document.createElement("h3");
      titleEl.className = "ds-card-title";
      headerEl.appendChild(titleEl);
      this.titleEl = titleEl;
      const bodyEl = document.createElement("div");
      bodyEl.className = "ds-card-body";
      containerEl.appendChild(headerEl);
      containerEl.appendChild(bodyEl);
      this.appendChild(containerEl);
      this.lightSlot = bindLightChildren(this, [containerEl], (node) => bodyEl.appendChild(node));
    }
    sync() {
      if (!this.containerEl || !this.headerEl || !this.titleEl) return;
      const title = this.getAttribute("title") || "";
      this.containerEl.className = `ds-card${this.hasAttribute("elevated") ? " ds-card--elevated" : ""}`;
      this.titleEl.textContent = title;
      this.headerEl.style.display = title ? "flex" : "none";
    }
  };

  // src/components/ds-dialog.ts
  var dialogIdCounter = 0;
  var DsDialog = class extends BaseElement {
    static get observedAttributes() {
      return ["title", "open"];
    }
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
    disconnectedCallback() {
      this.lightSlot?.disconnect();
    }
    attributeChangedCallback(name) {
      if (this.initialized) this.sync(name === "open");
    }
    showModal() {
      this.setAttribute("open", "");
    }
    close() {
      this.removeAttribute("open");
    }
    render() {
      const dialogEl = document.createElement("dialog");
      dialogEl.className = "ds-dialog-native";
      dialogEl.setAttribute("aria-labelledby", this.dialogId);
      this.dialogEl = dialogEl;
      const header = document.createElement("header");
      header.className = "ds-dialog-header";
      const titleEl = document.createElement("h2");
      titleEl.className = "ds-dialog-title";
      titleEl.id = this.dialogId;
      this.titleEl = titleEl;
      const closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.className = "ds-dialog-close";
      closeBtn.setAttribute("aria-label", "Fechar di\xE1logo");
      closeBtn.textContent = "\u2715";
      closeBtn.addEventListener("click", () => this.close());
      header.appendChild(titleEl);
      header.appendChild(closeBtn);
      const bodyEl = document.createElement("div");
      bodyEl.className = "ds-dialog-body";
      this.bodyEl = bodyEl;
      const footerEl = document.createElement("footer");
      footerEl.className = "ds-dialog-footer";
      footerEl.style.display = "none";
      this.footerEl = footerEl;
      dialogEl.appendChild(header);
      dialogEl.appendChild(bodyEl);
      dialogEl.appendChild(footerEl);
      this.appendChild(dialogEl);
      this.lightSlot = bindLightChildren(this, [dialogEl], (node) => {
        if (node instanceof Element && node.getAttribute("slot") === "footer") {
          footerEl.appendChild(node);
          footerEl.style.display = "flex";
        } else {
          bodyEl.appendChild(node);
        }
      });
      dialogEl.addEventListener("click", (e) => {
        if (e.target === dialogEl) this.close();
      });
      dialogEl.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          this.close();
        }
      });
      this.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && this.hasAttribute("open")) {
          e.preventDefault();
          this.close();
        }
      });
      dialogEl.addEventListener("close", () => {
        if (this.hasAttribute("open")) this.removeAttribute("open");
        this.finishClose();
      });
    }
    sync(openChanged = false) {
      if (!this.dialogEl || !this.titleEl) return;
      this.titleEl.textContent = this.getAttribute("title") || "Di\xE1logo";
      const shouldBeOpen = this.hasAttribute("open");
      if (shouldBeOpen && !this.dialogEl.open) {
        this.previousFocus = document.activeElement;
        this.closePending = true;
        typeof this.dialogEl.showModal === "function" ? this.dialogEl.showModal() : this.dialogEl.setAttribute("open", "");
      } else if (!shouldBeOpen && this.dialogEl.open) {
        if (typeof this.dialogEl.close === "function") {
          this.dialogEl.close();
        } else {
          this.dialogEl.removeAttribute("open");
          this.finishClose();
        }
      } else if (openChanged && !shouldBeOpen) {
        this.finishClose();
      }
    }
    finishClose() {
      if (!this.closePending) return;
      this.closePending = false;
      const returnTarget = this.previousFocus;
      this.previousFocus = null;
      if (returnTarget?.isConnected) returnTarget.focus();
      this.dispatchEvent(new CustomEvent("ds-close", { bubbles: true }));
    }
  };

  // src/components/ds-app-shell.ts
  var DsAppShell = class extends BaseElement {
  };

  // src/index.ts
  function registerAllComponents() {
    if (typeof customElements === "undefined") return;
    const registry = [
      ["ds-button", DsButton],
      ["ds-input", DsInput],
      ["ds-badge", DsBadge],
      ["ds-alert", DsAlert],
      ["ds-card", DsCard],
      ["ds-dialog", DsDialog],
      ["ds-app-shell", DsAppShell]
    ];
    for (const [tag, ctor] of registry) {
      if (!customElements.get(tag)) {
        customElements.define(tag, ctor);
      }
    }
  }
  registerAllComponents();
})();
