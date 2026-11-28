import { BaseElement } from '../utils/base-element.js';

/**
 * ds-app-shell — primitivo estrutural para aplicações.
 *
 * Mantém os filhos semânticos no Light DOM. A ordem dos slots define
 * header → navigation (opcional) → main → footer.
 * Não cria rolagens internas nem posiciona header/footer de forma fixa.
 */
export class DsAppShell extends BaseElement {}
