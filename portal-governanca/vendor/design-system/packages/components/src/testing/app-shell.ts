export interface AppShellValidation {
  valid: boolean;
  errors: string[];
}

/**
 * Valida o contrato estrutural do ds-app-shell para uso em testes do consumidor.
 * Não mede layout/renderização; combine com testes de navegador para geometria visual.
 */
export function validateAppShell(shell: Element): AppShellValidation {
  const errors: string[] = [];
  if (shell.tagName.toLowerCase() !== 'ds-app-shell') {
    return { valid: false, errors: ['O elemento raiz deve ser <ds-app-shell>.'] };
  }

  const children = Array.from(shell.children);
  const regions = children.map(element => ({
    element,
    region: element.getAttribute('data-ds-region') || '',
    tag: element.tagName.toLowerCase(),
  }));

  if (children.length !== regions.filter(item => item.region).length) {
    errors.push('Todos os filhos diretos devem declarar data-ds-region.');
  }

  const allowed = ['header', 'navigation', 'main', 'footer'];
  for (const item of regions) {
    if (!allowed.includes(item.region)) {
      errors.push(`Região desconhecida: "${item.region || '(ausente)'}".`);
      continue;
    }
    const expectedTag = item.region === 'navigation' ? 'nav' : item.region;
    if (item.tag !== expectedTag) {
      errors.push(`A região "${item.region}" deve usar <${expectedTag}>; encontrado <${item.tag}>.`);
    }
  }

  for (const required of ['header', 'main', 'footer']) {
    if (regions.filter(item => item.region === required).length !== 1) {
      errors.push(`Deve existir exatamente uma região "${required}".`);
    }
  }

  if (regions.filter(item => item.region === 'navigation').length > 1) {
    errors.push('Pode existir no máximo uma região "navigation".');
  }

  const actualOrder = regions.map(item => item.region).filter(Boolean);
  const expectedOrder = actualOrder.includes('navigation')
    ? ['header', 'navigation', 'main', 'footer']
    : ['header', 'main', 'footer'];
  if (actualOrder.join('|') !== expectedOrder.join('|')) {
    errors.push(`Ordem inválida. Esperado: ${expectedOrder.join(' → ')}.`);
  }

  const navigation = regions.find(item => item.region === 'navigation')?.element;
  if (navigation && !navigation.hasAttribute('aria-label') && !navigation.hasAttribute('aria-labelledby')) {
    errors.push('A navegação global deve ter aria-label ou aria-labelledby.');
  }

  return { valid: errors.length === 0, errors };
}
