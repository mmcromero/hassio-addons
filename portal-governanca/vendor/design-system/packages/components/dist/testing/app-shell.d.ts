export interface AppShellValidation {
    valid: boolean;
    errors: string[];
}
/**
 * Valida o contrato estrutural do ds-app-shell para uso em testes do consumidor.
 * Não mede layout/renderização; combine com testes de navegador para geometria visual.
 */
export declare function validateAppShell(shell: Element): AppShellValidation;
