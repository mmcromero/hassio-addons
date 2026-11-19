import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const root = new URL('../src/public/games/', import.meta.url);
const read = name => readFileSync(new URL(name, root), 'utf8');

class Elemento {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.style = { setProperty() {} };
    this.dataset = {};
    this.listeners = {};
    this.classes = new Set();
    this.classList = {
      add: value => this.classes.add(value),
      remove: value => this.classes.delete(value),
      toggle: (value, on) => on ? this.classes.add(value) : this.classes.delete(value)
    };
    this.hidden = false;
    this.textContent = '';
    this.className = '';
  }
  append(...items) {
    for (const item of items) {
      if (!item) continue;
      item.parent = this;
      this.children.push(item);
    }
  }
  prepend(...items) {
    for (const item of [...items].reverse()) {
      item.parent = this;
      this.children.unshift(item);
    }
  }
  replaceChildren(...items) { this.children = []; this.append(...items); }
  remove() {
    if (this.parent) this.parent.children = this.parent.children.filter(x => x !== this);
  }
  addEventListener(name, handler) { (this.listeners[name] ??= []).push(handler); }
  removeEventListener(name, handler) {
    this.listeners[name] = (this.listeners[name] || []).filter(h => h !== handler);
  }
  click() { for (const handler of this.listeners.click || []) handler(); }
  setAttribute(name, value) { this[name] = value; }
  getAttribute(name) { return this[name]; }
}
const descendants = node => [node, ...node.children.flatMap(descendants)];
const textMatch = (element, tag, text) => element.tag === tag && element.textContent === text;

function iniciarEnsaio() {
  const documento = {
    body: new Elemento('body'),
    createElement: tag => new Elemento(tag),
    createElementNS: (_, tag) => new Elemento(tag)
  };
  let paisagem = false;
  const events = {};
  const janela = {
    scrollY: 0, innerWidth: 390, innerHeight: 844, visualViewport: null,
    matchMedia(query) { return { matches: query.includes('portrait') ? !paisagem : paisagem }; },
    addEventListener(name, handler) { events[name] = handler; },
    removeEventListener() {}, scrollTo() {}
  };
  class Canal {
    constructor() {
      this.port1 = { close() {}, postMessage() {} };
      this.port2 = { close() {}, postMessage() {} };
    }
  }
  const arte = read('catalogo-visual.js').replace(/^export .+;$/gm, '');
  const visuais = runInNewContext(
    arte + '\n({ ilustracao, etiquetas })', { document: documento }
  );
  // O adaptador do ensaio substitui apenas importações e serviços externos;
  // o fluxo de UI e seus manipuladores são o código real da biblioteca.
  const codigo = read('biblioteca.js')
    .replace(/^import .+;$/gm, '')
    .replace(/^export /gm, '')
    .replace(/import\.meta/g, '({ url: "http://localhost/games/biblioteca.js" })');
  const criar = runInNewContext(codigo + '\ncriarBibliotecaJogos', {
    document: documento, window: janela, HTMLElement: Elemento,
    obterCatalogo: () => Promise.resolve(JSON.parse(read('manifest.json')).games),
    ilustracao: visuais.ilustracao, etiquetas: visuais.etiquetas,
    newInstanceId: () => 'sintetico',
    createEnvelope: () => ({}), validateEnvelope: () => true,
    createRateLimiter: () => () => true, MessageChannel: Canal,
    URL, setTimeout: () => 1, clearTimeout() {}
  });
  return {
    documento,
    janela,
    session: criar({ container: new Elemento('div') }),
    nodes: () => descendants(documento.body),
    landscape(on) {
      paisagem = on;
      janela.innerWidth = on ? 844 : 390;
      janela.innerHeight = on ? 390 : 844;
      events.orientationchange?.();
    }
  };
}

test('catálogo aprovado: 16 capas, 14 bloqueados e etiquetas', async () => {
  const t = iniciarEnsaio();
  await t.session.pronto;
  const nodes = t.nodes();
  const cards = nodes.filter(x => x.className === 'games-option');
  assert.equal(cards.length, 16);
  assert.equal(cards.filter(x => descendants(x).some(y => y.tag === 'button' && y.disabled)).length, 14);
  assert.equal(nodes.filter(x => x.tag === 'svg').length, 16);
  assert.equal(nodes.filter(x => x.className === 'games-tags').length, 16);
  assert.ok(nodes.some(x => x.textContent === 'Solo / CPU'));
  assert.ok(nodes.some(x => x.textContent === 'Multiplayer local'));
  assert.ok(nodes.some(x => x.textContent === 'Cada um no seu celular'));
  assert.ok(t.nodes().find(x => x.id === 'rotate-hint').hidden);
  t.session.encerrar();
});

test('Pong: seleciona em retrato, pede paisagem e avisa retorno', async () => {
  const t = iniciarEnsaio();
  await t.session.pronto;
  const cards = t.nodes().filter(x => x.className === 'games-option');
  const pong = cards.find(x => descendants(x).some(y => textMatch(y, 'h3', 'Pong')));
  descendants(pong).find(x => x.tag === 'button').click();
  assert.ok(t.nodes().some(x => textMatch(x, 'h2', 'Pong · Jogadores')));
  const girar = t.nodes().find(x => x.id === 'rotate-hint');
  assert.equal(girar.hidden, true);
  t.nodes().find(x => textMatch(x, 'button', 'Começar partida')).click();
  assert.equal(girar.hidden, false);
  assert.equal(t.nodes().filter(x => x.tag === 'iframe').length, 0);
  t.landscape(true);
  assert.equal(t.nodes().filter(x => x.tag === 'iframe').length, 1);
  // Regressão P0: o contêiner de partida deve ter altura integral, sem CSS de catálogo.
  assert.ok(t.nodes().some(x => x.className === 'games-playing'));
  const css = t.nodes().find(x => x.tag === 'style')?.textContent || '';
  assert.match(css, /#game-screen #stage > \.games-playing\{display:flex/);
  assert.doesNotMatch(css, /\\\\n#game-screen #stage > \.games-playing/);
  t.nodes().find(x => x.dataset.gamesBack).click();
  assert.equal(t.nodes().find(x => x.id === 'return-portrait').hidden, false);
  t.landscape(false);
  await Promise.resolve();
  assert.equal(t.nodes().filter(x => x.className === 'games-option').length, 16);
  assert.equal(t.nodes().find(x => x.id === 'return-portrait').hidden, true);
  t.session.encerrar();
});

test('Jogo da Velha: abre sem exigir paisagem', async () => {
  const t = iniciarEnsaio();
  await t.session.pronto;
  const cards = t.nodes().filter(x => x.className === 'games-option');
  const velha = cards.find(x => descendants(x).some(y => textMatch(y, 'h3', 'Jogo da Velha')));
  descendants(velha).find(x => x.tag === 'button').click();
  t.nodes().find(x => textMatch(x, 'button', 'Começar partida')).click();
  assert.equal(t.nodes().find(x => x.id === 'rotate-hint').hidden, true);
  assert.equal(t.nodes().filter(x => x.tag === 'iframe').length, 1);
  t.session.encerrar();
  assert.equal(t.nodes().some(x => x.id === 'game-screen'), false);
});

test('modo local de dois jogadores: seleciona na tela principal e abre partida', async () => {
  const t = iniciarEnsaio();
  await t.session.pronto;
  const cards = t.nodes().filter(x => x.className === 'games-option');
  for (const titulo of ['Pong', 'Jogo da Velha']) {
    const card = cards.find(x => descendants(x).some(y => textMatch(y, 'h3', titulo)));
    if (titulo === 'Jogo da Velha') {
      t.nodes().find(x => x.dataset.gamesBack)?.click();
      await Promise.resolve();
      const atual = t.nodes().filter(x => x.className === 'games-option')
        .find(x => descendants(x).some(y => textMatch(y, 'h3', titulo)));
      descendants(atual).find(x => x.tag === 'button').click();
    } else {
      descendants(card).find(x => x.tag === 'button').click();
    }
    const dois = t.nodes().find(x => x.tag === 'button' && /2 jogadores/.test(x.textContent));
    assert.ok(dois, 'Seleção de dois jogadores ausente: ' + titulo);
    dois.click();
    assert.equal(dois['aria-pressed'], 'true');
    t.nodes().find(x => textMatch(x, 'button', 'Começar partida')).click();
    if (titulo === 'Pong') {
      assert.equal(t.nodes().find(x => x.id === 'rotate-hint').hidden, false);
      t.landscape(true);
    } else {
      assert.equal(t.nodes().find(x => x.id === 'rotate-hint').hidden, true);
    }
    assert.equal(t.nodes().filter(x => x.tag === 'iframe').length, 1);
    t.nodes().find(x => x.dataset.gamesBack).click();
    if (titulo === 'Pong') t.landscape(false);
    await Promise.resolve();
  }
  t.session.encerrar();
});

test('iframes iniciam direto após modo escolhido e mantêm sandbox', () => {
  const jsVelha = read('jogo-da-velha-isolado.html');
  const jsPong = read('pong-local-isolado.html');
  for (const html of [jsVelha, jsPong]) {
    assert.match(html, /autoStart: true/);
    assert.match(html, /if\(autoStart\) iniciar\.click\(\)/);
    assert.match(html, /Content-Security-Policy/);
  }
  assert.match(read('biblioteca.js'), /setAttribute\('sandbox', 'allow-scripts'\)/);
});

test('Pong online: falha de ingresso mantém aviso e tentativa na partida, sem retorno forçado', () => {
  const codigo = read('biblioteca.js');
  const bloco = codigo.slice(codigo.indexOf('} catch (erro) {', codigo.indexOf('async function jogar(')));
  assert.match(bloco, /if \(jogo\.id === 'pong' && modo === 'dupla'\)/);
  assert.match(bloco, /palco\.replaceChildren\(\)/);
  assert.match(bloco, /setAttribute\('role', 'alert'\)/);
  assert.match(bloco, /'Tentar novamente'/);
  assert.match(bloco, /etapa = 'rotacao';\s*layout\(\)/);
  assert.match(bloco, /'← Voltar aos jogos'/);
});
