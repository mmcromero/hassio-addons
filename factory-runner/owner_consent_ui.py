"""HA owner enrollment and per-publication consent UI, independent from API Bearer.

The separate Ingress service supplies a kernel-verified Supervisor peer and user.
Request headers never set verified_ingress; this module never starts a listener.
"""
import html
import secrets
import time
from urllib.parse import urlsplit
from publication_contract import PublicationError
from release_receipt import canonical,digest


class OwnerConsentUI:
    def __init__(self,rpc,origin,*,ingress_verifier):
        # Validate a complete HTTPS origin, not only its textual prefix.
        # urlsplit alone accepts malformed authorities such as "https://";
        # accessing .port also rejects invalid port syntax.
        try:
            parsed=urlsplit(origin)
            _=parsed.port
        except (TypeError,ValueError):
            raise PublicationError('https_owner_origin_required') from None
        if (not isinstance(origin,str) or not origin or any(ch.isspace() for ch in origin)
                or parsed.scheme!='https' or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path or parsed.query or parsed.fragment):
            raise PublicationError('https_owner_origin_required')
        self.rpc=rpc;self.origin=origin;self.ingress_verifier=ingress_verifier;self.sessions={}

    def home_view(self,context):
        owner=self.ingress_verifier(context)
        if not isinstance(owner,str) or not owner:
            raise PublicationError('verified_owner_ingress_required')
        status=self.rpc.enrollment_status()
        if not isinstance(status,dict):
            raise PublicationError('owner_enrollment_status_unavailable')
        if status.get('enrolled') is False:
            body=('<h1>Factory Runner — proprietário</h1>'
                  '<p>O cadastro inicial ainda não foi concluído.</p>'
                  '<p><a href="owner-enroll/">Configurar proprietário</a></p>')
        else:
            body=('<h1>Factory Runner — proprietário</h1>'
                  '<p>Identidade do proprietário confirmada.</p>'
                  '<p>Esta tela não publica pacotes. Abra o link de consentimento gerado pelo Runner para revisar uma operação específica.</p>')
        return {'html':'<!doctype html><meta charset="utf-8"><title>Factory Runner</title>'+body,
                'headers':{'Cache-Control':'no-store',
                    'Content-Security-Policy':"default-src 'none'; form-action 'self'; frame-ancestors 'self'",
                    'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin'}}

    def enroll_view(self,context):
        owner=self.ingress_verifier(context)
        if not isinstance(owner,str) or not owner:
            raise PublicationError('verified_owner_ingress_required')
        status=self.rpc.enrollment_status()
        if not isinstance(status,dict) or status.get('enrolled') is not False:
            raise PublicationError('owner_already_enrolled')
        csrf=secrets.token_hex(32);session=csrf
        self.sessions={key:value for key,value in self.sessions.items() if value['expires']>time.time()}
        if len(self.sessions)>=32:raise PublicationError('owner_session_budget')
        self.sessions[session]={'owner':owner,'csrf':csrf,'expires':time.time()+120,'kind':'enroll',
                                'ingress_path':context.get('ingress_path')}
        page=('<!doctype html><meta charset="utf-8"><title>Configurar proprietário</title>'
              '<h1>Cadastro inicial do proprietário</h1>'
              '<p>Crie uma senha independente. Use pelo menos 16 caracteres. Esta senha será solicitada em cada publicação.</p>'
              '<p>Por segurança, o formulário expira em 2 minutos. Se expirar, abra novamente o cadastro.</p>'
              '<form method="post" action="submit">'
              '<input type="hidden" name="csrf" value="'+csrf+'">'
              '<label>Nova senha <input type="password" name="password" minlength="16" maxlength="256" required></label>'
              '<label>Confirme a senha <input type="password" name="password_confirm" minlength="16" maxlength="256" required></label>'
              '<label>Digite CADASTRAR <input name="confirmation" required></label>'
              '<button type="submit">Cadastrar proprietário</button></form>')
        return {'session':session,'html':page,'headers':{
            'Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; form-action 'self'; frame-ancestors 'self'",
            'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin'}}

    def enroll(self,session,body,context,origin):
        owner=self.ingress_verifier(context)
        state=self.sessions.pop(session,None)
        if (not state or state.get('kind')!='enroll' or state['expires']<=time.time()
                or owner!=state['owner'] or origin!=self.origin
                or not state.get('ingress_path') or state['ingress_path']!=context.get('ingress_path')
                or not isinstance(body,dict)
                or set(body)!={'csrf','password','password_confirm','confirmation'}
                or not secrets.compare_digest(str(body.get('csrf','')),state['csrf'])):
            raise PublicationError('owner_enrollment_session_invalid')
        if (not isinstance(body['password'],str) or not isinstance(body['password_confirm'],str)
                or not 16<=len(body['password'])<=256
                or not secrets.compare_digest(body['password'].encode('utf-8'),body['password_confirm'].encode('utf-8'))
                or body['confirmation']!='CADASTRAR'):
            raise PublicationError('owner_enrollment_input_invalid')
        return self.rpc.enroll(password=body['password'],
                               password_confirm=body['password_confirm'],
                               confirmation=body['confirmation'])

    def view(self,proposal,context):
        owner=self.ingress_verifier(context)
        if not isinstance(owner,str) or not owner:raise PublicationError('verified_owner_ingress_required')
        # The trusted HA adapter maps a verified owner to a short-lived session;
        # the operation Bearer never participates in this channel.
        view=self.rpc.request('view',proposal=proposal)
        session=secrets.token_hex(32);csrf=secrets.token_hex(32)
        self.sessions={key:value for key,value in self.sessions.items() if value['expires']>time.time()}
        if len(self.sessions)>=32:raise PublicationError('owner_session_budget')
        self.sessions[session]={'owner':owner,'csrf':csrf,'proposal':proposal,
                                'digest':view['consent_digest'],'expires':time.time()+120,'kind':'consent'}
        receipt=view['receipt']
        evidence={'binding':view['binding'],'preview':view['preview'],
                  'receipt':{'files':receipt['files'],'state':receipt['state'],
                             'tests':{'status':receipt['tests']['status'],
                                      'source_sha':receipt['tests'].get('source_sha'),
                                      'checks':[{'exit_code':c.get('exit_code'),'passed':c.get('passed')} for c in receipt['tests'].get('checks',[])]}}}
        details=html.escape(canonical(evidence).decode())
        page=('<!doctype html><meta charset="utf-8"><title>Autorizar publicação</title>'
              '<h1>Consentimento por publicação</h1><p>Confira destino, versão, SHAs, escopo e digest.</p>'
              '<pre>'+details+'</pre><form method="post" action="consent">'
              '<input type="hidden" name="csrf" value="'+csrf+'">'
              '<label>Senha independente do proprietário <input type="password" name="password" autocomplete="current-password" required></label>'
              '<label>Digite PUBLICAR <input name="confirmation" required></label>'
              '<button type="submit">Autorizar somente este ato</button></form>')
        return {'session':session,'html':page,'headers':{
            'Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; form-action 'self'; frame-ancestors 'self'",
            'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin'},
            'cookie_attributes':'Secure; HttpOnly; SameSite=Strict; Path=<accepted_ingress_path>'}

    def consent(self,session,body,context,origin):
        owner=self.ingress_verifier(context)
        state=self.sessions.pop(session,None)
        if (not state or state.get('kind')!='consent' or state['expires']<=time.time() or owner!=state['owner'] or origin!=self.origin
                or not isinstance(body,dict) or set(body)!={'csrf','password','confirmation'}
                or not secrets.compare_digest(str(body.get('csrf','')),state['csrf'])):
            raise PublicationError('owner_csrf_or_session_invalid')
        return self.rpc.request('consent',proposal=state['proposal'],password=body['password'],
                                consent_digest=state['digest'],confirmation=body['confirmation'])
