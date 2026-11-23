/** UX-PRIMEIRO-ACESSO-002: presentation only; Google and invitation endpoints stay unchanged. */
export function entryPage(prefix:string,interest:string){const signup=interest.includes('data-entry-panel="signup"')?interest:`<section class="entry-card" data-entry-panel="signup" aria-labelledby="interest-title"><h1 id="interest-title" tabindex="-1">Quero participar do piloto</h1>${interest}<a class="entry-switch" href="#login" data-entry-view="login">Já sou cadastrado</a></section>`;return `<main class="pilot-auth pilot-entry" aria-label="Acesso ao Artesão Digital"><header class="entry-brand"><div data-pilot-brand>Artesão Digital</div></header>${signup}<section class="entry-card" data-entry-panel="auth" aria-labelledby="entry-auth-title" hidden><h1 id="entry-auth-title" tabindex="-1">Bem-vindo de volta!</h1><p id="entry-auth-description">Entre na sua conta para continuar no Artesão Digital.</p><form id="entry-auth-form" method="post" action="${prefix}auth/google/start"><div id="entry-invite-field" hidden><label for="invite">Código do convite</label><input id="invite" name="invite" type="password" maxlength="100" autocomplete="off" disabled><p class="entry-help">Depois do código, confirme sua conta Google vinculada ao convite.</p></div><button data-pilot-login class="google-signin" disabled><img src="https://developers.google.com/static/identity/images/g-logo.png" width="20" height="20" alt="" aria-hidden="true" referrerpolicy="no-referrer"><span data-google-label>Entrar com Google</span></button></form><button type="button" class="entry-secondary" data-entry-view="invite" id="entry-have-invite">Tenho um convite</button><a class="entry-switch" href="#signup" data-entry-view="signup" id="entry-signup-link">Quero participar do piloto</a><a class="entry-switch" href="#login" data-entry-view="login" id="entry-back-login" hidden>Voltar para o login</a><p class="entry-help">Seus dados são separados das demais contas. Projeto piloto gratuito, em construção e com acesso por convite.</p></section><nav class="entry-legal" aria-label="Informações de acesso"><a href="${prefix}legal">Termos de Uso</a><a href="${prefix}legal#privacy">Política de Privacidade</a><a href="${prefix}legal#cookies">Política de Cookies</a><a href="${prefix}admin/login">Acesso administrativo</a></nav></main>`;}
export function entryScript(){return `(()=>{addEventListener('DOMContentLoaded',()=>{
 const signup=document.querySelector('[data-entry-panel=signup]'),auth=document.querySelector('[data-entry-panel=auth]');if(!signup||!auth)return;
 const title=document.getElementById('entry-auth-title'),description=document.getElementById('entry-auth-description'),field=document.getElementById('entry-invite-field'),input=document.getElementById('invite'),button=auth.querySelector('[data-pilot-login]');
 const show=(mode,focus=true)=>{
  if(mode==='pilot-login')mode='login';
  if(!['signup','login','invite'].includes(mode))mode='signup';
  signup.hidden=mode!=='signup';auth.hidden=mode==='signup';field.hidden=mode!=='invite';input.disabled=mode!=='invite';input.required=mode==='invite';input.setCustomValidity('');
  title.textContent=mode==='invite'?'Tenho um convite':'Bem-vindo de volta!';description.textContent=mode==='invite'?'Digite o código que você recebeu para acessar sua conta.':'Entre na sua conta para continuar no Artesão Digital.';
  button.querySelector('[data-google-label]').textContent=mode==='invite'?'Continuar com Google':'Entrar com Google';
  document.getElementById('entry-have-invite').hidden=mode==='invite';document.getElementById('entry-signup-link').hidden=mode==='invite';document.getElementById('entry-back-login').hidden=mode!=='invite';
  document.title=(mode==='signup'?'Quero participar do piloto':title.textContent)+' — Artesão Digital';
  if(focus)(mode==='signup'?document.getElementById('interest-title'):title).focus();
 };
 document.querySelectorAll('[data-entry-view]').forEach(control=>control.addEventListener('click',event=>{event.preventDefault();const mode=control.dataset.entryView;history.pushState(null,'','#'+mode);show(mode);}));
 addEventListener('popstate',()=>show(location.hash.slice(1)));addEventListener('hashchange',()=>show(location.hash.slice(1)));
 input.addEventListener('input',()=>input.setCustomValidity(''));
 document.getElementById('entry-auth-form').addEventListener('submit',event=>{if(!input.disabled&&!input.value.trim()){event.preventDefault();input.setCustomValidity('Digite o código do convite que você recebeu.');input.reportValidity();}});
 show(location.hash.slice(1),false);
});})();`;}
export const entryCss=`
:root body.pilot-entry-page{padding-bottom:0}
:root .pilot-entry-page #pilot-build-info{position:static;font-size:14px;gap:8px 16px;margin-top:32px}
:root .pilot-entry-page #pilot-build-info a{display:inline-flex;align-items:center;min-height:44px}
:root .pilot-entry{--entry-green:var(--mata,#1E4D3B);--entry-line:var(--areia,#CBB493);--entry-paper:var(--linho,#F5F5EF);--entry-text:var(--carvao,#1F2A25);width:100%;max-width:1080px;margin:32px auto;padding:0 32px;font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;font-size:16px;line-height:1.5;color:var(--entry-text)}
:root .pilot-entry [hidden]{display:none!important}
:root .pilot-entry .entry-brand{display:block;text-align:center;margin-bottom:24px}
:root .pilot-entry [data-pilot-brand]{padding:0;margin:0 auto;max-width:200px}
:root .pilot-entry [data-pilot-brand] img{width:160px;min-width:120px;height:auto}
:root .pilot-entry .entry-card{max-width:560px;margin:0 auto;padding:32px;border:1px solid var(--entry-line);border-radius:16px;background:#fff;box-shadow:0 8px 32px #1e4d3b08}
:root .pilot-entry h1{font:600 32px/1.25 Inter,system-ui,-apple-system,"Segoe UI",sans-serif;margin:0 0 16px;color:var(--entry-green);outline-offset:6px}
:root .pilot-entry p{margin:0 0 24px}
:root .pilot-entry input:not([type=checkbox]){min-height:48px;margin:8px 0 16px;border:1px solid #6b8074;border-radius:10px;background:white;font:inherit}
:root .pilot-entry label{font-weight:600;display:block}
:root .pilot-entry button{min-height:48px;padding:12px 20px;margin:16px 0 0;border:1px solid var(--entry-green);border-radius:10px;background:var(--entry-green);color:#fff;font:600 16px/1.5 Inter,system-ui,sans-serif;cursor:pointer}
:root .pilot-entry button:disabled{background:#e2e8e2;color:#43564b;border-color:#8c9d91;opacity:1;cursor:wait}
:root .pilot-entry .google-signin{display:flex;align-items:center;justify-content:center;gap:10px;background:#fff;border:1px solid #747775;color:#1f1f1f;font:500 14px/20px "Google Sans",Arial,Helvetica,sans-serif;letter-spacing:0;border-radius:7px;min-height:48px;padding:12px;margin-top:9px}
:root .pilot-entry .google-signin:enabled:hover{background:#f7f8f8;box-shadow:0 2px 6px #1112}
:root .pilot-entry .google-signin:disabled{background:#fff;color:#1f1f1f;border-color:#747775;opacity:.6;cursor:wait}
:root .pilot-entry .google-signin img{width:20px;height:20px;object-fit:contain;flex-shrink:0}
:root .pilot-entry .entry-secondary{background:#fff;color:var(--entry-green)}
:root .pilot-entry .entry-switch{display:flex;align-items:center;justify-content:center;min-height:48px;margin-top:12px;padding:8px 12px;font-weight:600;text-underline-offset:4px}
:root .pilot-entry .entry-help,:root .pilot-entry #interest-privacy,:root .pilot-entry .pilot-consent,:root .pilot-entry [role=status]{font-size:14px;line-height:1.5}
:root .pilot-entry .entry-help{margin-top:16px}
:root .pilot-entry .pilot-consent{display:flex;gap:12px;align-items:center;min-height:44px}
:root .pilot-entry .pilot-consent input{width:22px;height:22px;margin:0;flex:none}
:root .pilot-entry .entry-legal{max-width:560px;margin:24px auto;display:flex;gap:8px 16px;flex-wrap:wrap;justify-content:center;font-size:14px}
:root .pilot-entry .entry-legal a{display:inline-flex;align-items:center;min-height:44px}
:root .pilot-entry :focus-visible{outline:3px solid var(--mata,#1E4D3B);outline-offset:4px}
:root .pilot-entry #interest-status{margin:16px 0 0}
@media(max-width:1024px){:root body.pilot-entry-page{padding-bottom:0}
:root .pilot-entry-page #pilot-build-info{position:static;font-size:14px;gap:8px 16px;margin-top:32px}
:root .pilot-entry-page #pilot-build-info a{display:inline-flex;align-items:center;min-height:44px}
:root .pilot-entry{margin:24px auto;padding:0 24px}}
@media(max-width:768px){:root body.pilot-entry-page{padding-bottom:0}
:root .pilot-entry-page #pilot-build-info{position:static;font-size:14px;gap:8px 16px;margin-top:32px}
:root .pilot-entry-page #pilot-build-info a{display:inline-flex;align-items:center;min-height:44px}
:root .pilot-entry{margin:24px auto;padding:0 16px}:root .pilot-entry .entry-card{padding:24px 20px}:root .pilot-entry h1{font-size:26px}:root .pilot-entry [data-pilot-brand] img{width:140px}}
`;
