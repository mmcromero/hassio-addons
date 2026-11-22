"""Shared navigation and static, CSP-hashed motion assets. No account data in JS."""
import base64
import hashlib
import html
from html.parser import HTMLParser
from pathlib import Path
import re

ROOT = Path(__file__).parent
SCRIPT = (ROOT / 'interface-ui.js').read_text()
STYLE = (ROOT / 'interface-ui.css').read_text()


def _hash(value):
    return "'sha256-" + base64.b64encode(hashlib.sha256(value.encode()).digest()).decode() + "'"


class _InlineStyles(HTMLParser):
    def __init__(self):
        super().__init__(); self.inside = False; self.styles = []

    def handle_starttag(self, tag, attrs):
        if tag == 'style': self.inside = True

    def handle_endtag(self, tag):
        if tag == 'style': self.inside = False

    def handle_data(self, value):
        if self.inside: self.styles.append(value)


def policy(value, raw=None):
    directives = {}
    for entry in value.split(';'):
        parts = entry.strip().split()
        if parts: directives[parts[0]] = parts[1:]
    for name, digest in (('script-src', _hash(SCRIPT)), ('style-src', _hash(STYLE))):
        values = [part for part in directives.get(name, []) if part != "'none'" and not (name == 'style-src' and part == "'unsafe-inline'")]
        if digest not in values: values.append(digest)
        directives[name] = values
    if raw is not None:
        styles = _InlineStyles(); styles.feed(raw.decode('utf-8'))
        for style in styles.styles:
            digest = _hash(style)
            if digest not in directives['style-src']: directives['style-src'].append(digest)
    return '; '.join(name + ' ' + ' '.join(values) for name, values in directives.items())


def enhance(raw):
    if b'<style data-central-ui-assets>' in raw: return raw
    text = raw.decode('utf-8')
    assets = '<style data-central-ui-assets>' + STYLE + '</style><script>' + SCRIPT + '</script>'
    if '</head>' in text:
        text = text.replace('</head>', assets + '</head>', 1)
    elif re.search(r'<html\b[^>]*>', text, re.I):
        text = re.sub(r'(<html\b[^>]*>)', lambda match: match[1] + '<head>' + assets + '</head>', text, count=1, flags=re.I)
    else:
        text = '<!doctype html><html><head>' + assets + '</head><body>' + text + '</body></html>'
    text = re.sub(r'<body\b', '<body data-ui-page', text, count=1, flags=re.I)
    return text.encode()


def header(cfg, section, *, editorial=False):
    business = cfg.get('business_id', 'umdoislab')
    prefix = '' if business == 'umdoislab' else '/accounts/' + business
    choices = cfg.get('navigation_accounts') or [{'business_id': business,
        'display_name': cfg.get('account_display_name') or 'Umdoislab',
        'username': cfg.get('instagram_expected_username') or 'umdoislab'}]
    options = []
    for account in choices:
        name = account['business_id']
        path = '' if name == 'umdoislab' else '/accounts/' + name
        target = ('/accounts?account=' + name if section == 'Contas' else path +
                  ('/editorial/' if editorial else '/panel?view=settings' if section == 'Configurações Meta' else '/panel'))
        selected = ' selected' if name == business else ''
        options.append('<option value="' + html.escape(target, quote=True) + '"' + selected + '>' +
                       html.escape(account['display_name'] + ' · @' + account['username']) + '</option>')
    return ('<header class="topbar ui-app-header"><div class="crumb">' +
            html.escape(str(cfg.get('account_display_name') or 'Umdoislab')) +
            ' <span>/</span> <strong id="current-section">' + html.escape(section) + '</strong></div>' +
            '<div class="top-actions"><label class="ui-account-picker">Conta<select aria-label="Conta selecionada" data-account-switch>' +
            ''.join(options) + '</select></label><span class="account ui-sr-only" aria-hidden="true">@' +
            html.escape(str(cfg.get('instagram_expected_username') or 'umdoislab')) + '</span>' +
            '<form class="logout-form" method="post" action="' + prefix + '/auth/logout">' +
            '<button type="submit" class="btn quiet">Sair</button></form></div></header>')


def sidebar(cfg=None, *, active='accounts', editorial=False):
    cfg = cfg or {}
    business = cfg.get('business_id', 'umdoislab')
    prefix = html.escape('' if business == 'umdoislab' else '/accounts/' + business, quote=True)
    accounts_url = '/accounts?account=' + html.escape(business, quote=True)
    name = html.escape(str(cfg.get('account_display_name') or 'Umdoislab'))
    username = html.escape(str(cfg.get('instagram_expected_username') or 'umdoislab'))
    def item(label, icon, href, view=None, selected=False):
        current = ' aria-current="page"' if selected else ''
        classes = 'nav-link' + (' active' if selected else '')
        symbol = '<span class="ui-nav-icon" aria-hidden="true">' + icon + '</span>'
        if editorial and view:
            return '<button type="button" class="' + classes + '" data-view="' + view + '"' + current + '>' + symbol + label + '</button>'
        return '<a class="' + classes + '" href="' + href + '"' + current + '>' + symbol + label + '</a>'
    contents = ''.join(item(label, icon, prefix + '/editorial/#' + view, view,
                        editorial and view == 'overview') for view, label, icon in (
                            ('overview', 'Visão geral', '◫'), ('calendar', 'Calendário', '▦'),
                            ('editor', 'Criar publicação', '✎'), ('library', 'Biblioteca', '▧'),
                            ('approval', 'Revisão e envios', '✓'), ('history', 'Histórico', '◷')))
    def group(label, links):
        return '<section class="ui-nav-group"><h2>' + label + '</h2><nav class="nav" aria-label="' + label + '">' + links + '</nav></section>'
    groups = (group('Editorial', contents) +
              group('Mensagens', item('Caixa de entrada', '◉', prefix + '/panel', selected=active == 'messages')) +
              group('Contas', item('Contas conectadas', '◎', accounts_url, selected=active == 'accounts') +
                    item('Adicionar conta', '+', accounts_url + '#add-account')) +
              group('Conexão Meta', item('Configurações Meta', '⚙', prefix + '/panel?view=settings', selected=active == 'settings')))
    return ('<aside class="sidebar ui-sidebar"><div class="ui-sidebar-heading"><a class="brand" href="' + accounts_url + '" aria-label="Central Instagram — Contas">'
            '<span class="brand-icon">U<span class="dot">.</span></span><span><strong>CENTRAL INSTAGRAM</strong><small>Conteúdo e atendimento</small></span></a>'
            '<button class="ui-menu-toggle" type="button" aria-expanded="false" aria-controls="ui-navigation">Menu</button></div>' +
            '<div class="ui-account-context"><small>CONTA SELECIONADA</small><strong>' + name + '</strong><span>@' + username + '</span></div>' +
            '<div id="ui-navigation" class="ui-nav-groups">' + groups + '</div>' +
            '<div class="sidebar-foot ui-sidebar-foot"><strong>Seu fluxo de trabalho</strong><small>Conta → conteúdo → revisão → envio</small></div></aside>')


INITIAL_SKELETON = '''<div id="initial-skeleton" class="ui-initial-skeleton" role="status" aria-live="polite">
<p>Carregando o conteúdo desta conta…</p><div class="ui-skeleton-grid" aria-hidden="true">
<div class="ui-skeleton ui-skeleton-card"></div><div class="ui-skeleton ui-skeleton-card"></div>
<div class="ui-skeleton ui-skeleton-row"></div><div class="ui-skeleton ui-skeleton-row"></div>
</div></div>'''
