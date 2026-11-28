import { DsButton } from './components/ds-button.js';
import { DsInput } from './components/ds-input.js';
import { DsBadge } from './components/ds-badge.js';
import { DsAlert } from './components/ds-alert.js';
import { DsCard } from './components/ds-card.js';
import { DsDialog } from './components/ds-dialog.js';
import { DsAppShell } from './components/ds-app-shell.js';

export { DsButton, DsInput, DsBadge, DsAlert, DsCard, DsDialog, DsAppShell };

/**
 * Registra todos os Custom Elements no customElements registry.
 *
 * Compatibilidade SSR / Node.js (CR-02):
 * - Seguro para importação em processos Node sem DOM (server-safe / no-throw on import):
 *   as classes estendem `BaseElement`, que faz fallback no-op quando `HTMLElement`
 *   não existe globalmente.
 * - O registro só é executado no cliente ou em ambiente com DOM virtual,
 *   garantido pela guarda `typeof customElements !== 'undefined'`.
 * - Importar este pacote no servidor não lança ReferenceError.
 * - Limite de escopo (Fase 1): renderização declarativa estática em string no servidor
 *   sem DOM virtual não está implementada nesta fase. Para instanciar componentes
 *   no servidor, utilize um DOM virtual (ex.: happy-dom, linkedom).
 */
export function registerAllComponents() {
  if (typeof customElements === 'undefined') return;

  const registry: Array<[string, CustomElementConstructor]> = [
    ['ds-button', DsButton],
    ['ds-input', DsInput],
    ['ds-badge', DsBadge],
    ['ds-alert', DsAlert],
    ['ds-card', DsCard],
    ['ds-dialog', DsDialog],
    ['ds-app-shell', DsAppShell]
  ];

  for (const [tag, ctor] of registry) {
    if (!customElements.get(tag)) {
      customElements.define(tag, ctor);
    }
  }
}

registerAllComponents();
