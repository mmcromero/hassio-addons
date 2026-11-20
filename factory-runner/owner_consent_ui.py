"""Dormant HA owner consent application, independent from operation Bearer.

An accepted HA ingress adapter must authenticate the owner UI session and verify
TLS/peer itself. Request headers never set verified_ingress. No server is started
or route registered by this module, run.sh or server.py in M006.
"""
import html
import secrets
import time
from publication_contract import PublicationError
from release_receipt import canonical,digest


class OwnerConsentUI:
    def __init__(self,rpc,origin,*,ingress_verifier):
        if not origin.startswith('https://') or '/' in origin.removeprefix('https://'):
            raise PublicationError('https_owner_origin_required')
        self.rpc=rpc;self.origin=origin;self.ingress_verifier=ingress_verifier;self.sessions={}

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
                                'digest':view['consent_digest'],'expires':time.time()+120}
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
            'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'},
            'cookie_attributes':'Secure; HttpOnly; SameSite=Strict; Path=<accepted_ingress_path>'}

    def consent(self,session,body,context,origin):
        owner=self.ingress_verifier(context)
        state=self.sessions.pop(session,None)
        if (not state or state['expires']<=time.time() or owner!=state['owner'] or origin!=self.origin
                or not isinstance(body,dict) or set(body)!={'csrf','password','confirmation'}
                or not secrets.compare_digest(str(body.get('csrf','')),state['csrf'])):
            raise PublicationError('owner_csrf_or_session_invalid')
        return self.rpc.request('consent',proposal=state['proposal'],password=body['password'],
                                consent_digest=state['digest'],confirmation=body['confirmation'])
