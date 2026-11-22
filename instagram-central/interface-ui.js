/* Central UI: purposeful feedback, native forms, media and accessible motion. */
(() => {
  'use strict';
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const mobile=matchMedia('(max-width: 760px)');
  const pending=new Map(),held=new Map(),dialogs=new WeakMap();
  let feedback,caption,bar,fill,live,hideTimer,sequence=0,paneSequence=0,menuSequence=0;
  const instant=()=>reduced.matches || document.documentElement.dataset.uiInput==='keyboard';
  const make=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;};
  function ensureFeedback(){
    if(feedback)return;
    feedback=make('div','ui-feedback');feedback.id='ui-feedback';feedback.dataset.active='false';
    caption=make('p','ui-feedback-label');caption.setAttribute('aria-hidden','true');
    bar=make('div','ui-progress');bar.setAttribute('role','progressbar');bar.setAttribute('aria-label','Andamento da operação');
    fill=make('span','ui-progress-fill');bar.append(fill);feedback.append(caption,bar);
    live=make('div','ui-sr-only');live.id='ui-announcement';live.setAttribute('role','status');live.setAttribute('aria-live','polite');
    document.body.append(feedback,live);
  }
  function announce(text){ensureFeedback();if(live.textContent!==text)live.textContent=text;}
  function start(label){
    ensureFeedback();clearTimeout(hideTimer);const id=++sequence;pending.set(id,label);
    feedback.dataset.active='true';caption.textContent=label;bar.dataset.indeterminate='true';bar.removeAttribute('aria-valuenow');bar.setAttribute('aria-valuetext',label);announce(label);
    return {
      update(text,value){
        if(!pending.has(id))return;pending.set(id,text);caption.textContent=text;
        if(typeof value==='number' && Number.isFinite(value)){
          const amount=Math.max(0,Math.min(100,value));bar.dataset.indeterminate='false';
          bar.setAttribute('aria-valuemin','0');bar.setAttribute('aria-valuemax','100');bar.setAttribute('aria-valuenow',String(Math.round(amount)));
          bar.setAttribute('aria-valuetext',Math.round(amount)+'%');fill.style.transform='scaleX('+(amount/100)+')';
        }else{bar.dataset.indeterminate='true';bar.removeAttribute('aria-valuenow');bar.setAttribute('aria-valuetext',text);}
      },
      end(){
        pending.delete(id);
        if(pending.size){caption.textContent=[...pending.values()].at(-1);return;}
        feedback.dataset.active='false';hideTimer=setTimeout(()=>{if(!pending.size)caption.textContent='';},instant()?0:120);
      }
    };
  }
  function hold(button,label){
    if(!(button instanceof HTMLButtonElement) || held.has(button))return ()=>{};
    const dialog=button.closest('dialog');
    const saved={nodes:[...button.childNodes],disabled:button.disabled,dialog,dialogBusy:dialog?.getAttribute('aria-busy')};held.set(button,saved);
    dialog?.setAttribute('aria-busy','true');
    button.disabled=true;button.classList.add('ui-button-busy');button.setAttribute('aria-busy','true');
    if(label)button.replaceChildren(document.createTextNode(label));
    return ()=>{
      if(!held.has(button))return;held.delete(button);button.replaceChildren(...saved.nodes);
      button.disabled=saved.disabled;button.classList.remove('ui-button-busy');button.removeAttribute('aria-busy');
      if(saved.dialog){if(saved.dialogBusy===null)saved.dialog.removeAttribute('aria-busy');else saved.dialog.setAttribute('aria-busy',saved.dialogBusy);}
    };
  }
  function restore(){
    for(const [button,saved] of held){button.replaceChildren(...saved.nodes);button.disabled=saved.disabled;button.classList.remove('ui-button-busy');button.removeAttribute('aria-busy');}
    held.clear();pending.clear();document.body.classList.remove('ui-page-leaving');
    document.querySelectorAll('form[data-ui-pending]').forEach(form=>{delete form.dataset.uiPending;form.removeAttribute('aria-busy');});
    if(feedback)feedback.dataset.active='false';
  }
  async function switchPanel(panels,next){
    const generation=++paneSequence;
    const previous=panels.find(panel=>!panel.classList.contains('hidden') && panel!==next);
    if(!previous || instant()){
      panels.forEach(panel=>{panel.classList.toggle('hidden',panel!==next);panel.classList.remove('ui-pane-exit','ui-pane-enter');});
      next.classList.add('ui-pane-current');return;
    }
    previous.classList.remove('ui-pane-current');previous.classList.add('ui-pane-exit');
    await new Promise(resolve=>setTimeout(resolve,90));if(generation!==paneSequence)return;
    panels.forEach(panel=>{panel.classList.toggle('hidden',panel!==next);panel.classList.remove('ui-pane-exit','ui-pane-current');});
    next.classList.add('ui-pane-enter');
    requestAnimationFrame(()=>{if(generation===paneSequence){next.classList.remove('ui-pane-enter');next.classList.add('ui-pane-current');}});
  }
  function openDialog(dialog){
    const previous=dialogs.get(dialog);if(previous?.timer)clearTimeout(previous.timer);
    dialogs.set(dialog,{trigger:document.activeElement});
    if(!dialog.open)dialog.showModal();
    dialog.dataset.uiDialog=instant()?'open':'enter';
    requestAnimationFrame(()=>{if(dialog.open)dialog.dataset.uiDialog='open';});
  }
  function closeDialog(dialog){
    const saved=dialogs.get(dialog)||{};if(saved.timer)clearTimeout(saved.timer);
    const close=()=>{if(dialog.open)dialog.close();dialog.dataset.uiDialog='closed';
      const target=saved.trigger?.isConnected?saved.trigger:document.querySelector('[data-view][aria-current="page"]');
      if(target instanceof HTMLElement && !target.closest('dialog'))target.focus({preventScroll:true});};
    dialog.dataset.uiDialog='exit';if(instant()){close();return;}
    saved.timer=setTimeout(close,100);dialogs.set(dialog,saved);
  }
  let observer;
  function trackMedia(media,url,container){
    media.dataset.uiMediaState='pending';media.dataset.uiMediaUrl=url;
    if(container)container.classList.add('ui-media-pending');
    if(media instanceof HTMLImageElement){media.loading='lazy';media.decoding='async';}
    else if(media instanceof HTMLVideoElement)media.preload='none';
    const settled=state=>{media.dataset.uiMediaState=state;if(container)container.classList.remove('ui-media-pending');};
    media.addEventListener(media instanceof HTMLVideoElement?'loadeddata':'load',()=>settled('ready'),{once:true});
    media.addEventListener('loadedmetadata',()=>settled('ready'),{once:true});
    media.addEventListener('error',()=>settled('error'),{once:true});
    const load=()=>{if(media.dataset.uiMediaUrl){if(media instanceof HTMLVideoElement)media.preload='metadata';media.src=media.dataset.uiMediaUrl;delete media.dataset.uiMediaUrl;}};
    media._uiLoad=load;
    if('IntersectionObserver' in window){
      if(!observer)observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){observer.unobserve(entry.target);entry.target._uiLoad?.();}}),{rootMargin:'160px'});
      observer.observe(media);
    }else load();
    return media;
  }
  function releaseMedia(root){
    root.querySelectorAll('[data-ui-media-state]').forEach(media=>observer?.unobserve(media));
  }
  function ready(){
    delete document.body.dataset.uiLoading;
    const skeleton=document.getElementById('initial-skeleton');if(skeleton)skeleton.hidden=true;
    document.getElementById('principal')?.removeAttribute('aria-busy');
  }
  function initialError(retry){
    document.body.dataset.uiLoading='error';document.getElementById('principal')?.removeAttribute('aria-busy');
    const skeleton=document.getElementById('initial-skeleton');if(!skeleton)return;
    skeleton.hidden=false;skeleton.replaceChildren();
    const panel=make('div','ui-load-error');panel.setAttribute('role','alert');
    panel.append(make('strong','','Não foi possível carregar esta conta.'),make('p','','Seus dados não foram alterados. Tente novamente ou escolha outra conta pelo menu.'));
    const button=make('button','btn primary','Tentar novamente');button.type='button';
    button.addEventListener('click',async()=>{const done=hold(button,'Carregando…');try{await retry();ready();}catch(_){announce('A conta continua indisponível. Tente novamente em instantes.');}finally{done();}});
    panel.append(button);skeleton.append(panel);announce('Não foi possível carregar esta conta.');
  }
  function setMenu(open){
    const nav=document.getElementById('ui-navigation'),button=document.querySelector('.ui-menu-toggle');
    if(!nav || !button)return;
    const generation=++menuSequence,expanded=!mobile.matches || open;
    button.setAttribute('aria-expanded',String(expanded));
    document.body.dataset.uiMenu=expanded?'open':'closed';nav.inert=!expanded;
    if(expanded){
      const wasHidden=nav.hidden;nav.hidden=false;
      nav.dataset.uiNav=wasHidden && !instant()?'enter':'open';
      requestAnimationFrame(()=>{if(generation===menuSequence)nav.dataset.uiNav='open';});
    }else{
      nav.dataset.uiNav='exit';
      if(instant()){nav.hidden=true;return;}
      setTimeout(()=>{if(generation===menuSequence)nav.hidden=true;},100);
    }
  }
  function nativeLabel(form){
    const path=new URL(form.action,location.href).pathname;
    if(path.endsWith('/auth/login'))return 'Entrando…';
    if(path.endsWith('/auth/logout'))return 'Saindo…';
    if(path.endsWith('/accounts'))return 'Adicionando conta…';
    if(path.endsWith('/handoff'))return 'Atualizando conversa…';
    if(path.endsWith('/meta/check'))return 'Verificando acesso Meta…';
    if(path.endsWith('/meta/subscribe'))return 'Solicitando assinatura…';
    return 'Salvando…';
  }
  function init(){
    ensureFeedback();document.documentElement.dataset.uiInput='pointer';
    const visibility=()=>{document.documentElement.dataset.uiBackground=String(document.hidden);};
    document.addEventListener('visibilitychange',visibility);visibility();
    document.addEventListener('keydown',event=>{
      document.documentElement.dataset.uiInput='keyboard';
      if(event.key==='Escape' && mobile.matches)setMenu(false);
    },true);
    document.addEventListener('pointerdown',()=>{document.documentElement.dataset.uiInput='pointer';},true);
    document.querySelector('.ui-menu-toggle')?.addEventListener('click',()=>setMenu(document.body.dataset.uiMenu!=='open'));
    mobile.addEventListener('change',()=>setMenu(!mobile.matches));setMenu(!mobile.matches);
    document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('cancel',event=>{
      event.preventDefault();if(dialog.getAttribute('aria-busy')==='true'){announce('Aguarde a conclusão da operação atual.');return;}closeDialog(dialog);
    }));
    document.addEventListener('click',event=>{
      const link=event.target.closest('a[href]');if(!link || event.defaultPrevented || event.button!==0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || link.target==='_blank' || link.hasAttribute('download'))return;
      const url=new URL(link.href,location.href);if(url.origin!==location.origin)return;
      if(url.pathname===location.pathname && url.search===location.search && url.hash){
        syncNativeNav();return;
      }
      start('Abrindo '+(link.textContent.trim()||'a página')+'…');document.body.classList.add('ui-page-leaving');
    });
    document.addEventListener('submit',event=>{
      if(event.defaultPrevented || !(event.target instanceof HTMLFormElement))return;
      const form=event.target;
      if(form.dataset.uiPending){event.preventDefault();announce('Aguarde a conclusão da operação atual.');return;}
      form.dataset.uiPending='true';form.setAttribute('aria-busy','true');const label=nativeLabel(form);
      if(!form.closest('#meta-actions'))hold(event.submitter || form.querySelector('button[type="submit"],button'),label);
      start(label);document.body.classList.add('ui-page-leaving');
    });
    addEventListener('pageshow',event=>{if(event.persisted)restore();});
    addEventListener('hashchange',syncNativeNav);syncNativeNav();
    if(!instant()){
      document.body.classList.add('ui-page-enter');
      requestAnimationFrame(()=>{document.body.classList.remove('ui-page-enter');document.body.classList.add('ui-page-ready');});
    }
  }
  function syncNativeNav(){
    if(location.pathname.endsWith('/editorial/') || location.pathname.endsWith('/editorial'))return;
    const section=location.hash==='#connection'?'connection':'messages';
    document.querySelectorAll('.ui-sidebar a[href]').forEach(link=>{
      const url=new URL(link.href,location.href);if(url.pathname!==location.pathname || !['#messages','#connection'].includes(url.hash))return;
      const active=url.hash==='#'+section;link.classList.toggle('active',active);
      if(active)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
    });
  }
  window.CentralUI={start,hold,announce,instant,switchPanel,media:trackMedia,releaseMedia,ready,initialError,
    dialog:{open:openDialog,close:closeDialog},closeMenu:()=>setMenu(false)};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
