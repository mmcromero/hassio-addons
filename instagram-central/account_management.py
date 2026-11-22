"""Single-owner administration of multiple isolated Instagram account contexts."""
import html
from urllib.parse import parse_qs
import account_registry
import panel_login
import interface_ui


def prefix(business_id):
    return '' if business_id == account_registry.PRIMARY_BUSINESS else '/accounts/' + business_id


def render(accounts, cfg, cookie_header, summary_for, *, error=False, values=None):
    values = values or {}
    cards = []
    for account in accounts:
        summary = summary_for(account['business_id'])
        status = ('Reconexão Meta necessária' if summary.get('reauthRequired') else
                  'Conectada à Meta' if summary['accountVerified'] else 'Autorização Meta pendente')
        path = prefix(account['business_id']) + '/panel?view=settings'
        cards.append('<li><div class="ui-account-row-head">' + interface_ui._avatar(account) + '<div><h2>' + html.escape(account['display_name']) + '</h2><p>@' +
                     html.escape(account['username']) + ' · ' + status + '</p><a href="' + path +
                     '">Configurações Meta de @' + html.escape(account['username']) + '</a></div></div><div class="ui-account-row-actions"><a class="btn quiet" href="' +
                     prefix(account['business_id']) + '/panel">Abrir Mensagens desta conta</a><a class="btn" href="' +
                     prefix(account['business_id']) + '/editorial/">Abrir Editorial desta conta</a></div></li>')
    csrf = panel_login.admin_csrf_token(cookie_header, cfg.get('panel_password'), 'accounts:create')
    notice = '<p role="alert">Não foi possível adicionar. Confira o usuário, o nome e se a conta já existe.</p>' if error else ''
    return ('''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Contas · Central Instagram</title></head>
<body class="ui-accounts-page"><a class="skip" href="#principal">Pular para conteúdo</a><div class="shell ui-shell">''' +
            interface_ui.sidebar(cfg, active='accounts') + '<main id="principal" class="main">' + interface_ui.header(cfg, 'Contas') +
            '<div class="content ui-account-content"><div class="heading"><span class="eyebrow">SEU ESPAÇO DE TRABALHO</span><h1>Contas do Instagram</h1>' +
            '<p>Gerencie as contas conectadas. A conta selecionada acompanha sua navegação pela Central.</p></div>' +
            '<section id="account-list" data-account-view><div class="ui-list-heading"><h2>Suas contas · ' + str(len(accounts)) + '</h2><a class="btn primary" href="#add-account">Adicionar conta</a></div><ul class="ui-account-grid">' + ''.join(cards) + '</ul></section>' +
            '<section class="panel" id="add-account" data-account-view' + (' data-account-error' if error else '') + '><a class="btn quiet" href="#account-list">Voltar às contas</a><h2>Adicionar conta</h2><p>Use o usuário exato do Instagram. A identidade será confirmada ao conectar pela Meta.</p>' + notice +
            '<form id="account-create-form" data-ui-dirty' + (' data-ui-unsaved' if error else '') + ' method="post" action="/accounts"><input type="hidden" name="csrf" value="' + csrf + '">' +
            '<label for="account-name">Nome da conta</label><input id="account-name" name="display_name" maxlength="120" value="' + html.escape(values.get('display_name',''), quote=True) + '" required>' +
            '<label for="account-user">Usuário do Instagram</label><input id="account-user" name="username" maxlength="31" placeholder="@usuario" value="' + html.escape(values.get('username',''), quote=True) + '" required>' +
            '<p>Adicionar não envia mensagens nem ativa webhook. A conexão Meta será feita nas configurações dessa conta.</p>' +
            '<button class="btn primary" type="submit">Adicionar conta</button></form></section></div></main></div></body></html>')



def parse_registration(raw):
    try:
        fields = parse_qs(raw.decode('utf-8'), keep_blank_values=True, max_num_fields=3)
    except (ValueError, UnicodeDecodeError):
        return None
    if set(fields) != {'username', 'display_name', 'csrf'} or any(len(v) != 1 for v in fields.values()):
        return None
    return {key: values[0] for key, values in fields.items()}
