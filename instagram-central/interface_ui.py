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
    directives.setdefault('img-src', ["'self'"])
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


def _avatar(account):
    business = account['business_id']
    path = '' if business == 'umdoislab' else '/accounts/' + business
    label = str(account.get('display_name') or account.get('username') or '?')
    initials = ''.join(word[0] for word in label.split()[:2]).upper()
    return ('<span class="ui-account-avatar" aria-hidden="true"><span>' + html.escape(initials) +
            '</span><img src="' + html.escape(path + '/panel?view=profile-image', quote=True) +
            '" alt="" width="32" height="32" loading="lazy" decoding="async" referrerpolicy="no-referrer"></span>')


def _account_label(account):
    return ('<span class="ui-account-label"><strong>' + html.escape(account['display_name']) +
            '</strong><small>@' + html.escape(account['username']) + '</small></span>')


def settings_tabs(connection, diagnostics, tools, *, automation=None, default='connection'):
    sections = [('connection', 'Conexão', connection), ('diagnostics', 'Diagnósticos', diagnostics),
                ('tools', 'Ferramentas', tools)]
    if automation is not None:
        sections.append(('automation', 'Atendimento', automation))
    return ('<div data-ui-tabs="settings" data-tabs-hash data-tabs-default="' + default + '">' +
            '<div class="ui-local-tabs" aria-label="Configurações desta conta">' + ''.join(
                '<button type="button" id="settings-tab-' + key + '" data-ui-tab="' + key + '">' + label + '</button>'
                for key, label, _ in sections) + '</div>' + ''.join(
                '<div id="settings-pane-' + key + '" data-ui-pane="' + key + '">' + content + '</div>'
                for key, _, content in sections) + '</div>')


def header(cfg, section, *, editorial=False):
    business = cfg.get('business_id', 'umdoislab')
    prefix = '' if business == 'umdoislab' else '/accounts/' + business
    choices = cfg.get('navigation_accounts') or [{'business_id': business,
        'display_name': cfg.get('account_display_name') or 'Umdoislab',
        'username': cfg.get('instagram_expected_username') or 'umdoislab'}]
    options, links = [], []
    current = next((account for account in choices if account['business_id'] == business), choices[0])
    for account in choices:
        name = account['business_id']
        path = '' if name == 'umdoislab' else '/accounts/' + name
        target = ('/accounts?account=' + name if section == 'Contas' else path +
                  ('/editorial/' if editorial else '/panel?view=settings' if section == 'Configurações Meta' else '/panel'))
        selected = ' selected' if name == business else ''
        options.append('<option value="' + html.escape(target, quote=True) + '"' + selected + '>' +
                       html.escape(account['display_name'] + ' · @' + account['username']) + '</option>')
        links.append('<li><a href="' + html.escape(target, quote=True) + '" data-account-link' +
                     (' aria-current="true"' if name == business else '') + '>' + _avatar(account) +
                     _account_label(account) + ('<span aria-hidden="true">✓</span>' if name == business else '') + '</a></li>')
    return ('<header class="topbar ui-app-header"><nav class="ui-breadcrumb" aria-label="Localização">' +
            '<a href="' + html.escape(prefix + '/panel', quote=True) + '">Central</a>' +
            '<span aria-hidden="true">/</span><span id="current-section" aria-current="page">' +
            html.escape(section) + '</span></nav>' +
            '<div class="top-actions"><div class="ui-account-picker"><label data-native-account-picker hidden>Conta<select aria-label="Conta selecionada" data-account-switch>' +
            ''.join(options) + '</select></label><details class="ui-visual-account-picker">' +
            '<summary aria-label="Trocar conta. Conta selecionada: ' + html.escape(current['display_name'] + ' @' + current['username'], quote=True) + '">' +
            _avatar(current) + _account_label(current) + '<span aria-hidden="true">▾</span></summary>' +
            '<nav aria-label="Selecionar conta"><ul>' + ''.join(links) + '</ul></nav></details></div>' +
            '<span class="account ui-sr-only" aria-hidden="true">@' +
            html.escape(str(cfg.get('instagram_expected_username') or 'umdoislab')) + '</span>' +
            '<form class="logout-form" method="post" action="' + prefix + '/auth/logout">' +
            '<button type="submit" class="btn quiet">Sair</button></form></div></header>')


def sidebar(cfg=None, *, active='accounts', editorial=False):
    cfg = cfg or {}
    business = cfg.get('business_id', 'umdoislab')
    prefix = html.escape('' if business == 'umdoislab' else '/accounts/' + business, quote=True)
    accounts_url = '/accounts?account=' + html.escape(business, quote=True)

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
    messages = item('Caixa de entrada', '◉', prefix + '/panel', selected=active == 'messages')
    accounts = (item('Contas conectadas', '◎', accounts_url, selected=active == 'accounts') +
                item('Adicionar conta', '+', accounts_url + '#add-account'))
    meta = item('Configurações Meta', '⚙', prefix + '/panel?view=settings', selected=active == 'settings')

    def group(label, links):
        return '<section class="ui-nav-group"><h2>' + label + '</h2><nav class="nav" aria-label="' + label + '">' + links + '</nav></section>'

    groups = group('Editorial', contents) + group('Atendimento', messages) + group('Gestão', accounts + meta)
    return ('<aside class="sidebar ui-sidebar"><div class="ui-sidebar-heading"><a class="brand" href="' + accounts_url + '" aria-label="Central Instagram — Contas">' +
            '<span class="brand-icon">U<span class="dot">.</span></span><span><strong>CENTRAL INSTAGRAM</strong><small>Conteúdo e atendimento</small></span></a>' +
            '<button class="ui-menu-toggle" type="button" aria-label="Abrir navegação" aria-expanded="false" aria-controls="ui-navigation">Menu</button></div>' +
            '<div id="ui-navigation" class="ui-nav-groups">' + groups + '</div>' +
            '<div class="sidebar-foot ui-sidebar-foot"><strong>Seu fluxo de trabalho</strong><small>Conta → conteúdo → revisão → envio</small></div></aside>')

INITIAL_SKELETON = '''<div id="initial-skeleton" class="ui-initial-skeleton" role="status" aria-live="polite">
<p>Carregando o conteúdo desta conta…</p><div class="ui-skeleton-grid" aria-hidden="true">
<div class="ui-skeleton ui-skeleton-card"></div><div class="ui-skeleton ui-skeleton-card"></div>
<div class="ui-skeleton ui-skeleton-row"></div><div class="ui-skeleton ui-skeleton-row"></div>
</div></div>'''
