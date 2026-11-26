/**
 * bindLightChildren — roteia filhos do Light DOM do host para destinos internos.
 *
 * Retorna um par [connect, disconnect] em vez de um único observer, para que
 * cada Custom Element possa reconectar a observação em connectedCallback e
 * desconectá-la em disconnectedCallback, garantindo funcionamento correto após
 * mover/remover/reinserir o elemento no DOM (CR-01).
 */
export function bindLightChildren(
  host: HTMLElement,
  internalRoots: Element[],
  routeNode: (node: Node) => void
): { connect: () => void; disconnect: () => void } {
  const isInternal = (node: Node) => internalRoots.includes(node as Element);
  let observer: MutationObserver | null = null;

  const connect = () => {
    // Mover nós presentes no host (exceto os internos já inseridos)
    for (const node of Array.from(host.childNodes)) {
      if (!isInternal(node)) {
        routeNode(node);
      }
    }
    // Observar inserções futuras
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
