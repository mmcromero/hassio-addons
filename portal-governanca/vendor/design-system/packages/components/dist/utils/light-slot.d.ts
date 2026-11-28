/**
 * bindLightChildren — roteia filhos do Light DOM do host para destinos internos.
 *
 * Retorna um par [connect, disconnect] em vez de um único observer, para que
 * cada Custom Element possa reconectar a observação em connectedCallback e
 * desconectá-la em disconnectedCallback, garantindo funcionamento correto após
 * mover/remover/reinserir o elemento no DOM (CR-01).
 */
export declare function bindLightChildren(host: HTMLElement, internalRoots: Element[], routeNode: (node: Node) => void): {
    connect: () => void;
    disconnect: () => void;
};
