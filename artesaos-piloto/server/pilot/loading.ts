/** UX-Loading-01: page-local feedback. Never changes requests, sessions or data. */
export const loadingCss=`button[aria-busy=true]{cursor:progress}button[aria-busy=true]:not([data-action-pending])::before{content:'';display:inline-block;width:.75em;height:.75em;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;margin-right:.45em} #pilot-loading-status{position:fixed;right:16px;bottom:16px;z-index:1200;max-width:calc(100vw - 32px);box-sizing:border-box;padding:9px 13px;border:1px solid #c6d2c9;border-radius:8px;background:#f5f2e9;color:#205e47;font:500 14px/1.4 system-ui,sans-serif;box-shadow:0 2px 8px #0001;pointer-events:none}#pilot-loading-status[hidden]{display:none}#pilot-loading-status::before{content:'◌';display:inline-block;margin-right:8px;font-size:18px;vertical-align:middle}`;
export function loadingScript(prefix:string){return `(()=>{
 const prefix=${JSON.stringify(prefix)},original=window.fetch.bind(window),jobs=new Set(),forms=new Map();let navigation=null;
 const render=()=>{if(!document.body)return;let status=document.getElementById('pilot-loading-status');if(!status){status=document.createElement('p');status.id='pilot-loading-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');document.body.append(status);}status.style.bottom=((document.getElementById('pilot-build-info')?.offsetHeight??0)+12)+'px';status.hidden=jobs.size===0;status.textContent=jobs.size?[...jobs].at(-1).label:'';};
 const begin=label=>{const job={label};jobs.add(job);render();let active=true;return()=>{if(!active)return;active=false;jobs.delete(job);render();};};
 const actions=new WeakMap(),actionNotes=new WeakMap();
 const action=(button,work)=>{
  if(actions.has(button))return actions.get(button);
  const previous=actionNotes.get(button);if(previous)previous.remove();
  let result;try{result=work();}catch{showActionError(button);return Promise.resolve();}
  if(!result||typeof result.then!=='function')return result;
  const busy=button.getAttribute('aria-busy');button.setAttribute('aria-busy','true');
  const promise=Promise.resolve(result).catch(()=>showActionError(button)).finally(()=>{if(actions.get(button)!==promise)return;actions.delete(button);if(busy===null)button.removeAttribute('aria-busy');else button.setAttribute('aria-busy',busy);});actions.set(button,promise);return promise;
 };
 const showActionError=button=>{let note=actionNotes.get(button);if(note&&!note.isConnected)note=null;if(!note){note=document.createElement('p');note.dataset.actionError='true';note.setAttribute('role','alert');button.insertAdjacentElement('afterend',note);actionNotes.set(button,note);}note.textContent='Não foi possível confirmar a operação. Verifique sua conexão e tente novamente.';};
 window.pilotLoading={begin,action};
 const wired=new WeakSet();
 const wire=()=>{if(!document.querySelectorAll)return;for(const button of document.querySelectorAll('button')){if(wired.has(button)||button.closest('#root')||typeof button.onclick!=='function')continue;const handler=button.onclick;button.onclick=function(event){if(actions.has(button)){event.preventDefault();return;}return action(button,()=>handler.call(this,event));};wired.add(button);}};
 const prepareActions=()=>{wire();if(typeof MutationObserver==='function')new MutationObserver(wire).observe(document.body,{childList:true,subtree:true});};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',prepareActions,{once:true});else prepareActions();
 window.fetch=(input,init)=>{let url;try{url=new URL(typeof input==='string'||input instanceof URL?input:input.url,document.baseURI);}catch{return original(input,init);}
  const tracked=url.origin===location.origin&&(url.pathname.startsWith(prefix+'admin/api/')||[prefix+'api/pilot/session',prefix+'api/legal/status',prefix+'api/onboarding',prefix+'api/operational-preferences'].includes(url.pathname));
  if(!tracked)return original(input,init);const end=begin('Carregando…');try{return original(input,init).finally(end);}catch(error){end();throw error;}
 };
 const reset=()=>{jobs.clear();navigation=null;for(const [form,state] of forms){if(state.busy===null)form.removeAttribute('aria-busy');else form.setAttribute('aria-busy',state.busy);for(const [button,disabled] of state.buttons){button.disabled=disabled;button.removeAttribute?.('aria-busy');}}forms.clear();render();};
 addEventListener('resize',render);
 addEventListener('pageshow',event=>{if(event.persisted)reset();});
 addEventListener('keydown',event=>{if(event.key==='Escape'){if(!forms.size&&navigation){navigation();navigation=null;}}});
 document.addEventListener('submit',event=>{if(event.defaultPrevented)return;const form=event.target;if(!(form instanceof HTMLFormElement)||form.method.toLowerCase()!=='post')return;const url=new URL(form.action,document.baseURI);
  if(url.origin!==location.origin||![prefix+'admin/auth/login',prefix+'admin/auth/setup',prefix+'admin/auth/recovery',prefix+'auth/google/start',prefix+'admin/auth/google/start'].includes(url.pathname))return;
  if(forms.has(form)){event.preventDefault();return;}
  const buttons=[...form.querySelectorAll('button[type=submit],button:not([type]),input[type=submit]')].map(button=>[button,button.disabled]);forms.set(form,{buttons,busy:form.getAttribute('aria-busy')});form.setAttribute('aria-busy','true');for(const [button] of buttons){button.disabled=true;button.setAttribute?.('aria-busy','true');}
  begin(url.pathname.includes('google')?'Abrindo acesso Google…':'Processando acesso…');
 });
 document.addEventListener('click',event=>{if(event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;const link=event.target.closest?.('.pilot-admin-nav a');if(!link||link.hasAttribute('download')||link.target&&link.target!=='_self')return;const url=new URL(link.href,document.baseURI);if(url.origin!==location.origin||url.href===location.href||url.pathname===location.pathname&&url.search===location.search)return;if(navigation)navigation();navigation=begin('Carregando página…');});
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',render,{once:true});else render();
})();`;}
