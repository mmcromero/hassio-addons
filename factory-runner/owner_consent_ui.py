"""HA owner status and per-publication consent UI, independent from API Bearer.

The separate Ingress service supplies a kernel-verified Supervisor peer and user.
Request headers never set verified_ingress; this module never starts a listener.
"""
import html
import os
import secrets
import sys
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
                  '<p>O cadastro inicial é feito nas Configurações deste add-on no Home Assistant.</p>'
                  '<p>Preencha a senha e a confirmação, salve as opções e reinicie o add-on. '
                  'A senha temporária será processada pela autoridade local e removida das opções.</p>')
        else:
            body=('<h1>Factory Runner — proprietário</h1>'
                  '<p>Identidade do proprietário confirmada.</p>'
                  '<p>Esta tela não publica pacotes. Abra a proposta pelo Runner para revisar e consentir uma operação específica.</p>')
        return {'html':'<!doctype html><meta charset="utf-8"><title>Factory Runner</title>'+body,
                'headers':{'Cache-Control':'no-store',
                    'Content-Security-Policy':"default-src 'none'; form-action 'self'; frame-ancestors 'self'",
                    'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin'}}

    def view(self,proposal,context):
        owner=self.ingress_verifier(context)
        if not isinstance(owner,str) or not owner:raise PublicationError('verified_owner_ingress_required')
        # The trusted HA adapter maps a verified owner to a short-lived session;
        # the operation Bearer never participates in this channel.
        view=self.rpc.request('view',proposal=proposal)
        session=secrets.token_hex(32);csrf=secrets.token_hex(32)
        self.sessions={key:value for key,value in self.sessions.items() if value['expires']>time.time()}
        if len(self.sessions)>=32:raise PublicationError('owner_session_budget')
        receipt=view['receipt']
        evidence={'binding':view['binding'],'preview':view['preview'],
                  'receipt':{'files':receipt['files'],'state':receipt['state'],
                             'tests':{'status':receipt['tests']['status'],
                                      'source_sha':receipt['tests'].get('source_sha'),
                                      'checks':[{'exit_code':c.get('exit_code'),'passed':c.get('passed')} for c in receipt['tests'].get('checks',[])]}}}
        details=html.escape(canonical(evidence).decode())
        if view.get('state')=='already_consented':
            grant_state=view.get('grant_state')
            if grant_state=='active' and isinstance(view.get('grant_nonce'),str):
                self.sessions[session]={'owner':owner,'csrf':csrf,'proposal':proposal,
                                         'nonce':view['grant_nonce'],'expires':time.time()+120,'kind':'revoke'}
                page=('<!doctype html><meta charset="utf-8"><title>Revogar autorização</title>'
                      '<h1>Publicação autorizada, ainda sujeita ao gate do Publisher</h1>'
                      '<p>Revogue esta autorização antes da reserva final, se não desejar prosseguir.</p>'
                      '<pre>'+details+'</pre><form method="post" action="revoke">'
                      '<input type="hidden" name="csrf" value="'+csrf+'">'
                      '<label>Senha do proprietário <input type="password" name="password" required></label>'
                      '<label>Confirme digitando REVOGAR <input name="confirmation" required></label>'
                      '<button type="submit">Revogar esta autorização</button></form>')
            else:
                state_text={'revoked':'Esta autorização já foi revogada.',
                            'reserved':'A publicação já entrou na etapa reservada; reconciliação é necessária.',
                            'expired':'Esta autorização expirou.',
                            'not_issued':'Nenhuma autorização foi emitida.',
                            'invalid':'A autorização não passou na validação e não pode ser revogada por esta tela.'}.get(grant_state,'Estado da autorização indisponível.')
                page=('<!doctype html><meta charset="utf-8"><title>Estado da autorização</title>'
                      '<h1>Estado da autorização</h1><p>'+html.escape(state_text)+'</p><pre>'+details+'</pre>')
        else:
            self.sessions[session]={'owner':owner,'csrf':csrf,'proposal':proposal,
                                     'digest':view['consent_digest'],'expires':time.time()+120,'kind':'consent'}
            page=('<!doctype html><meta charset="utf-8"><title>Autorizar publicação</title>'
                  '<h1>Consentimento por publicação</h1><p>Confira destino, versão, SHAs, escopo e digest.</p>'
                  '<pre>'+details+'</pre><form method="post" action="consent">'
                  '<input type="hidden" name="csrf" value="'+csrf+'">'
                  '<label>Confirme a publicação digitando PUBLICAR <input name="confirmation" required></label>'
                  '<button type="submit">Autorizar somente este ato</button></form>')
        return {'session':session,'html':page,'headers':{
            'Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; form-action 'self'; frame-ancestors 'self'",
            'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin'},
            'cookie_attributes':'Secure; HttpOnly; SameSite=Strict; Path=<accepted_ingress_path>'}

    def consent(self,session,body,context,origin):
        owner=self.ingress_verifier(context)
        state=self.sessions.pop(session,None)
        if (not state or state.get('kind')!='consent' or state['expires']<=time.time() or owner!=state['owner'] or origin!=self.origin
                or not isinstance(body,dict) or set(body)!={'csrf','confirmation'}
                or not secrets.compare_digest(str(body.get('csrf','')),state['csrf'])):
            raise PublicationError('owner_csrf_or_session_invalid')
        return self.rpc.request('consent',proposal=state['proposal'],
                                consent_digest=state['digest'],confirmation=body['confirmation'])

    def revoke(self,session,body,context,origin):
        owner=self.ingress_verifier(context)
        state=self.sessions.pop(session,None)
        if (not state or state.get('kind')!='revoke' or state['expires']<=time.time()
                or owner!=state['owner'] or origin!=self.origin
                or not isinstance(body,dict) or set(body)!={'csrf','confirmation','password'}
                or not secrets.compare_digest(str(body.get('csrf','')),state['csrf'])
                or body.get('confirmation')!='REVOGAR'
                or not isinstance(body.get('password'),str)):
            raise PublicationError('owner_csrf_or_session_invalid')
        return self.rpc.revoke(state['nonce'],body['password'])
