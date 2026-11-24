/** UX-PRIMEIRO-ACESSO-002: presentation only; Google and invitation endpoints stay unchanged. */
function replaceOnce(source:string,before:string,after:string){const index=source.indexOf(before);return index<0?source:source.slice(0,index)+after+source.slice(index+before.length);}
function enhanceSignupMarkup(markup:string){
 let html=markup;
 const intro='Projeto piloto gratuito, com acesso por convite. Solicite sua participação; a administração avaliará seu interesse. O envio não libera o acesso automaticamente.';
 html=replaceOnce(html,'<p>'+intro+'</p>','<aside class="signup-note signup-note--pilot" aria-labelledby="interest-pilot-title"><div class="signup-note__heading"><span class="signup-note__icon" aria-hidden="true">i</span><h2 id="interest-pilot-title">Como funciona o piloto</h2></div><p class="signup-note__copy">'+intro+'</p></aside>');
 html=replaceOnce(html,'<label for="interest-name">Nome (obrigatório)</label><input id="interest-name" name="name" autocomplete="name" maxlength="100" required>','<label class="entry-sr-only" for="interest-name">Nome</label><input id="interest-name" name="name" autocomplete="name" maxlength="100" placeholder="Seu nome" required>');
 html=replaceOnce(html,'<label for="interest-email">E-mail (obrigatório)</label><input id="interest-email" name="email" type="email" autocomplete="email" maxlength="254" required>','<label class="entry-sr-only" for="interest-email">E-mail</label><input id="interest-email" name="email" type="email" autocomplete="email" maxlength="254" placeholder="Seu e-mail" required>');
 html=replaceOnce(html,'<label for="interest-whatsapp">WhatsApp (opcional)</label><input id="interest-whatsapp" name="whatsapp" type="tel" autocomplete="tel" maxlength="40" placeholder="DDD e número">','<label class="entry-sr-only" for="interest-whatsapp">WhatsApp (opcional)</label><input id="interest-whatsapp" name="whatsapp" type="tel" autocomplete="tel" maxlength="40" placeholder="DDD e número (opcional)">');
 html=replaceOnce(html,'<p id="interest-privacy">','<aside class="signup-note signup-note--privacy" aria-labelledby="interest-privacy-title"><div class="signup-note__heading"><span class="signup-note__icon" aria-hidden="true">✓</span><h2 id="interest-privacy-title">Como usamos seus dados</h2></div><p id="interest-privacy">');
 html=replaceOnce(html,'</p><label class="pilot-consent">','</p></aside><label class="pilot-consent">');
 html=replaceOnce(html,'<input name="consent" type="checkbox" required>','<input name="consent" type="checkbox" aria-describedby="interest-privacy" required>');
 return html;
}
export function entryPage(prefix:string,interest:string){
 const original=interest.includes('data-entry-panel="signup"')?interest:'<section class="entry-card" data-entry-panel="signup" aria-labelledby="interest-title"><h1 id="interest-title" tabindex="-1">Quero participar do piloto</h1>'+interest+'<a class="entry-switch" href="#login" data-entry-view="login">Já sou cadastrado</a></section>';
 const signup=enhanceSignupMarkup(original);
 return '<main class="pilot-auth pilot-entry" data-admin-url="'+prefix+'admin/login" aria-label="Acesso ao Artesão Digital"><header class="entry-brand"><div data-pilot-brand="horizontal">Artesão Digital</div></header>'+signup+'<section class="entry-card" data-entry-panel="auth" aria-labelledby="entry-auth-title" hidden><h1 id="entry-auth-title" tabindex="-1">Bem-vindo de volta!</h1><p id="entry-auth-description">Entre na sua conta para continuar no Artesão Digital.</p><form id="entry-auth-form" method="post" action="'+prefix+'auth/google/start"><div id="entry-invite-field" hidden><label for="invite">Código do convite</label><input id="invite" name="invite" type="password" maxlength="100" autocomplete="off" disabled><p class="entry-help">Depois do código, confirme sua conta Google vinculada ao convite.</p></div><button data-pilot-login class="google-signin" disabled><img src="https://developers.google.com/static/identity/images/g-logo.png" width="20" height="20" alt="" aria-hidden="true" referrerpolicy="no-referrer"><span data-google-label>Entrar com Google</span></button></form><button type="button" class="entry-secondary" data-entry-view="invite" id="entry-have-invite">Tenho um convite</button><a class="entry-switch" href="#signup" data-entry-view="signup" id="entry-signup-link">Quero participar do piloto</a><a class="entry-switch" href="#login" data-entry-view="login" id="entry-back-login" hidden>Voltar para o login</a><p class="entry-help">Seus dados são separados das demais contas. Projeto piloto gratuito, em construção e com acesso por convite.</p></section></main>';
}export function entryScript(){return `(()=>{addEventListener('DOMContentLoaded',()=>{
 const signup=document.querySelector('[data-entry-panel=signup]'),auth=document.querySelector('[data-entry-panel=auth]');if(!signup||!auth)return;
 const footer=document.getElementById('pilot-build-info');
 if(footer){
  footer.setAttribute('aria-label','Informações do Artesão Digital');
  if(!footer.querySelector('.pilot-entry-footer-brand')){
   const brand=document.createElement('div');brand.className='pilot-entry-footer-brand';
   const logo=document.createElement('div');logo.textContent='Artesão Digital';logo.setAttribute('data-pilot-brand','horizontal');logo.setAttribute('aria-label','Artesão Digital');brand.append(logo);
   const slogan=document.createElement('p');slogan.className='pilot-entry-footer-slogan';slogan.textContent='De artesão para artesão.';brand.append(slogan);
   footer.prepend(brand);
  }
  let terms=footer.querySelector('[data-entry-footer-link=terms]');
  if(!terms){
   terms=footer.querySelector('a[href*="/legal"]');
   if(terms){
    const legalPath=terms.getAttribute('href')||terms.href;
    terms.href=legalPath+'#terms';terms.textContent='Termos de Uso';terms.setAttribute('data-entry-footer-link','terms');
    const privacy=terms.cloneNode(false);privacy.href=legalPath+'#privacy';privacy.textContent='Privacidade';privacy.setAttribute('data-entry-footer-link','privacy');
    const cookies=terms.cloneNode(false);cookies.href=legalPath+'#cookies';cookies.textContent='Cookies';cookies.setAttribute('data-entry-footer-link','cookies');
    terms.after(privacy,cookies);
   }
  }
  const entryRoot=document.querySelector('.pilot-entry'),adminPath=entryRoot?.getAttribute('data-admin-url');
  if(adminPath&&!document.querySelector('#pilot-account')&&!document.body.classList.contains('pilot-session-active')&&!footer.querySelector('[data-entry-footer-link=admin]')){
   const admin=document.createElement('a');admin.href=adminPath;admin.textContent='Acesso administrativo';admin.setAttribute('data-entry-footer-link','admin');
   const version=footer.querySelector('.pilot-current-version');if(version)footer.insertBefore(admin,version);else footer.append(admin);
  }
 }
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
:root .pilot-entry-page #pilot-build-info{position:static;font-size:14px;gap:8px 16px;margin-top:auto}
:root .pilot-entry-page #pilot-build-info a{display:inline-flex;align-items:center;min-height:44px}
:root .pilot-entry{--entry-green:var(--mata,#1E4D3B);--entry-line:var(--areia,#CBB493);--entry-paper:var(--linho,#F5F5EF);--entry-text:var(--carvao,#1F2A25);width:100%;max-width:1080px;margin:32px auto;padding:0 32px;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:16px;line-height:1.5;color:var(--entry-text)}
:root .pilot-entry [hidden]{display:none!important}
:root .pilot-entry .entry-brand{display:block;text-align:center;margin-bottom:24px}
:root .pilot-entry [data-pilot-brand]{padding:0;margin:0 auto;max-width:200px}
:root .pilot-entry [data-pilot-brand] img{width:160px;min-width:120px;height:auto}
:root .pilot-entry .entry-card{max-width:560px;margin:0 auto;padding:32px;border:1px solid var(--entry-line);border-radius:16px;background:#fff;box-shadow:0 8px 32px #1e4d3b08}
:root .pilot-entry h1{font:600 32px/1.25 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0 0 16px;color:var(--entry-green);outline-offset:6px}
:root .pilot-entry p{margin:0 0 24px}
:root .pilot-entry input:not([type=checkbox]){min-height:48px;margin:8px 0 16px;border:1px solid #6b8074;border-radius:10px;background:white;font:inherit}
:root .pilot-entry label{font-weight:600;display:block}
:root .pilot-entry button{min-height:48px;padding:12px 20px;margin:16px 0 0;border:1px solid var(--entry-green);border-radius:10px;background:var(--entry-green);color:#fff;font:600 16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;cursor:pointer}
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
:root .pilot-entry :focus-visible{outline:3px solid var(--mata,#1E4D3B);outline-offset:4px}
:root .pilot-entry #interest-status{margin:16px 0 0}
:root .pilot-entry .entry-sr-only{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
:root .pilot-entry .signup-note{min-width:0;display:grid;gap:8px;padding:14px 16px;border:1px solid transparent;border-left-width:4px;border-radius:10px;box-shadow:none;margin-bottom:14px}
:root .pilot-entry .signup-note--pilot{background:#EEF5F0;border-color:#D6E7DB;border-left-color:#1E4D3B;color:#294638}
:root .pilot-entry .signup-note--privacy{background:#FFF5E6;border-color:#EFD7AF;border-left-color:#A66F1E;color:#4B3B24}
:root .pilot-entry .signup-note__heading{display:flex;align-items:center;gap:9px}
:root .pilot-entry .signup-note__heading h2{margin:0;font:700 14px/1.35 system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:0}
:root .pilot-entry .signup-note--pilot .signup-note__heading{color:#1E4D3B}
:root .pilot-entry .signup-note--privacy .signup-note__heading{color:#704B1A}
:root .pilot-entry .signup-note__icon{display:inline-flex;justify-content:center;align-items:center;flex:0 0 21px;width:21px;height:21px;border:1.5px solid currentColor;border-radius:50%;font-size:12px;font-weight:700;line-height:1}
:root .pilot-entry .signup-note .signup-note__copy,:root .pilot-entry .signup-note #interest-privacy{margin:0;color:inherit;font-size:14px;line-height:1.55;overflow-wrap:break-word}
:root .pilot-entry-page #pilot-build-info .pilot-entry-footer-brand{order:-1;flex:0 0 100%;display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:8px 16px;width:100%;margin:0 auto 8px;text-align:center}
:root .pilot-entry-page #pilot-build-info .pilot-entry-footer-brand [data-pilot-brand=horizontal]{display:flex;align-items:center;justify-content:center;max-width:220px;min-width:0;margin:0;padding:0;font-weight:700;color:var(--mata,#1E4D3B)}
:root .pilot-entry-page #pilot-build-info .pilot-entry-footer-brand [data-pilot-brand=horizontal] img{display:block;width:180px;min-width:120px;max-width:100%;max-height:54px;height:auto;object-fit:contain}
:root .pilot-entry-page #pilot-build-info .pilot-entry-footer-brand [data-pilot-brand=horizontal] span{font-weight:700;color:var(--mata,#1E4D3B)}
:root .pilot-entry-page #pilot-build-info .pilot-entry-footer-slogan{margin:0;color:var(--mata,#1E4D3B);font:600 15px/1.4 Georgia,"Times New Roman",serif}
@media(max-width:1024px){:root body.pilot-entry-page{padding-bottom:0}
:root .pilot-entry-page #pilot-build-info{position:static;font-size:14px;gap:8px 16px;margin-top:auto}
:root .pilot-entry-page #pilot-build-info a{display:inline-flex;align-items:center;min-height:44px}
:root .pilot-entry{margin:24px auto;padding:0 24px}}
@media(max-width:768px){:root body.pilot-entry-page{padding-bottom:0}
:root .pilot-entry-page #pilot-build-info{position:static;font-size:14px;gap:8px 16px;margin-top:auto}
:root .pilot-entry-page #pilot-build-info a{display:inline-flex;align-items:center;min-height:44px}
:root .pilot-entry{margin:24px auto;padding:0 16px}:root .pilot-entry .entry-card{padding:24px 20px}:root .pilot-entry h1{font-size:26px}:root .pilot-entry [data-pilot-brand] img{width:140px}:root .pilot-entry .signup-note{padding:12px 13px;gap:7px}:root .pilot-entry-page #pilot-build-info .pilot-entry-footer-brand{gap:6px 12px}:root .pilot-entry-page #pilot-build-info .pilot-entry-footer-brand [data-pilot-brand=horizontal] img{width:140px}:root .pilot-entry-page #pilot-build-info .pilot-entry-footer-slogan{font-size:14px}}
`;
