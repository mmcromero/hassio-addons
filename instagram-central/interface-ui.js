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
  function initPublicationSettings(){
    const button=document.querySelector('button[data-publication-base]');if(!button)return;
    const status=document.getElementById('publication-status'),time=document.getElementById('publication-checked-at');
    const feedback=document.getElementById('publication-check-feedback');
    const showTime=value=>{
      const stamp=Number(value);time.dataset.checkedAt=String(stamp || '');
      time.textContent=stamp>0 && Number.isFinite(stamp)?'Última consulta: '+new Intl.DateTimeFormat('pt-BR',{
        dateStyle:'short',timeStyle:'medium',timeZone:'America/Sao_Paulo'
      }).format(new Date(stamp*1000))+' (Brasília).':'';
    };
    showTime(time.dataset.checkedAt);
    button.addEventListener('click',async()=>{
      if(button.disabled)return;
      const done=hold(button,'Verificando…'),operation=start('Verificando publicação…');
      feedback.textContent='Consultando o acesso desta conta…';
      const request=async(path,options={})=>{
        const response=await fetch(button.dataset.publicationBase+'api/'+path,{
          credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(35000),...options
        });
        if(response.status===403)throw new Error('A sessão expirou ou a consulta não foi autorizada. Entre novamente e tente outra vez.');
        const raw=await response.text();let result;
        try{if(raw.length<=65536)result=JSON.parse(raw);}catch(_){}
        if(!response.ok || !result || typeof result!=='object' || Array.isArray(result))
          throw new Error('Não foi possível concluir a consulta. Tente novamente em instantes.');
        return result;
      };
      try{
        const tokens=await request('csrf');
        if(typeof tokens.check!=='string' || !/^[a-f0-9]{64}$/.test(tokens.check))throw new Error('A consulta não foi autorizada. Recarregue a página e tente novamente.');
        const result=await request('drafts',{method:'POST',headers:{'Content-Type':'application/json',
          'X-Editorial-Action':'check','X-CSRF-Token':tokens.check},body:'{}'});
        if(typeof result.message!=='string' || typeof result.ready!=='boolean')throw new Error('Não foi possível confirmar o resultado da consulta. Tente novamente em instantes.');
        status.textContent=result.message;showTime(result.checkedAt);
        feedback.textContent=result.ready?'Verificação concluída: acesso de publicação confirmado.':'Verificação concluída: confira o diagnóstico acima.';
        announce(feedback.textContent);
      }catch(error){
        feedback.textContent=error instanceof TypeError || error.name==='TimeoutError' || error.name==='AbortError'
          ?'A consulta foi interrompida. O último diagnóstico foi preservado. Tente novamente em instantes.':error.message;
        announce(feedback.textContent);
      }finally{done();operation.end();}
    });
  }
  function initInboxRefresh(){
    const button=document.getElementById('refresh-inbox');if(!button)return;
    const area=document.getElementById('inbox-messages'),feedback=document.getElementById('inbox-feedback');
    button.addEventListener('click',async()=>{
      if(button.disabled)return;
      const done=hold(button,'Buscando na Meta…'),progress=start('Buscando mensagens recentes na Meta…');
      area.setAttribute('aria-busy','true');area.classList.add('ui-skeleton');
      feedback.textContent='Consultando a conta selecionada. Aguarde…';
      let saved=false;
      try{
        const response=await fetch(button.dataset.inboxUrl,{method:'POST',credentials:'same-origin',cache:'no-store',
          signal:AbortSignal.timeout(15000),headers:{'Content-Type':'application/x-www-form-urlencoded','X-Meta-Inbox':'refresh'},
          body:new URLSearchParams({csrf:button.dataset.inboxCsrf})});
        const raw=await response.text();let report;
        try{if(raw.length<=16384)report=JSON.parse(raw);}catch(_){}
        if(response.status===403)throw new Error('A sessão expirou ou a busca não foi autorizada. Entre novamente.');
        if(!response.ok || !report || !['confirmed','error'].includes(report.status))
          throw new Error('Não foi possível concluir a busca na Meta. As mensagens já armazenadas foram preservadas.');
        if(report.status==='error'){
          const reasons={busy:'Já há uma busca manual em andamento. Aguarde a conclusão.',
            configuration_incomplete:'Conecte e verifique esta conta em Configurações Meta antes de buscar mensagens.',
            permission_denied:'A Meta recusou o acesso ao conteúdo das mensagens.',token_invalid:'A Meta recusou o token salvo.',
            unsupported_request:'A Meta não disponibilizou esta consulta de mensagens para este acesso.',
            message_access_disabled:'O acesso externo às mensagens está desativado no Instagram.',
            message_identity_unavailable:'A Meta retornou mensagens sem identificar remetente e destinatário suficientes para importá-las com segurança.',
            transport_error:'Não foi possível concluir a comunicação com a Meta.',
            invalid_response:'A Meta retornou mensagens em formato inesperado.',storage_error:'Não foi possível gravar a busca na caixa de entrada.'};
          const codes=[['HTTP',report.http_status],['código Meta',report.provider_code],['subcódigo',report.provider_subcode]]
            .filter(item=>Number.isInteger(item[1])).map(item=>item[0]+' '+item[1]).join(', ');
          throw new Error((reasons[report.reason] || 'A busca não foi concluída.')+(codes?' ('+codes+')':''));
        }
        if(![report.imported,report.existing,report.scanned,report.skipped].every(n=>Number.isInteger(n)&&n>=0&&n<=50)
          || !Number.isInteger(report.conversations) || report.conversations<0 || report.conversations>5
          || typeof report.limited!=='boolean')throw new Error('Não foi possível confirmar o resumo da busca. Recarregue a caixa.');
        saved=true;
        const page=await fetch(location.pathname,{credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(12000)});
        if(!page.ok)throw new Error();
        const refreshed=new DOMParser().parseFromString(await page.text(),'text/html').getElementById('inbox-messages');
        if(!refreshed)throw new Error();
        area.replaceChildren(...refreshed.childNodes);
        if(!instant())area.animate([{opacity:0},{opacity:1}],{duration:160,easing:'ease-out'});
        const time=Number.isInteger(report.checked_at)?' às '+new Intl.DateTimeFormat('pt-BR',{
          timeStyle:'medium',timeZone:'America/Sao_Paulo'}).format(new Date(report.checked_at*1000))+' (Brasília)':'';
        feedback.textContent='Busca concluída'+time+': '+report.imported+' mensagem(ns) adicionada(s), '+report.existing+
          ' já armazenada(s), '+report.skipped+' item(ns) ignorado(s) (saídas, outros destinatários ou sem texto compatível). '+
          'Consultadas '+report.conversations+' conversa(s). '+(report.limited?'Há mais itens fora desta amostra. ':'')+
          'As mensagens da busca manual ficam fora da fila automática. Isso não confirma entrega de webhook.';
      }catch(error){
        feedback.textContent=saved?'Busca concluída, mas a tela não pôde ser recarregada. Recarregue a página para ver as mensagens armazenadas.':
          ['TimeoutError','AbortError'].includes(error.name) || error instanceof TypeError
            ?'A busca foi interrompida. Recarregue a caixa para conferir o resultado antes de repetir.':error.message;
      }finally{area.removeAttribute('aria-busy');area.classList.remove('ui-skeleton');done();progress.end();announce(feedback.textContent);}
    });
  }
  function initRoutingSettings(){
    const button=document.getElementById('check-routing');if(!button)return;
    const result=document.getElementById('routing-result'),feedback=document.getElementById('routing-feedback');
    const date=stamp=>new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeStyle:'medium',timeZone:'America/Sao_Paulo'}).format(new Date(stamp*1000))+' (Brasília)';
    button.addEventListener('click',async()=>{
      if(button.disabled)return;
      const done=hold(button,'Consultando…'),progress=start('Consultando controle e atividade…');
      feedback.textContent='Lendo somente metadados de até cinco conversas…';
      try{
        const response=await fetch(button.dataset.routingUrl,{method:'POST',credentials:'same-origin',cache:'no-store',
          signal:AbortSignal.timeout(12000),headers:{'Content-Type':'application/x-www-form-urlencoded','X-Meta-Diagnostic':'routing'},
          body:new URLSearchParams({csrf:button.dataset.routingCsrf})});
        const raw=await response.text();let report;
        try{if(raw.length<=16384)report=JSON.parse(raw);}catch(_){}
        if(response.status===403)throw new Error('A sessão expirou ou a consulta não foi autorizada. Entre novamente.');
        if(!response.ok || !report || !['confirmed','unknown','error'].includes(report.status))
          throw new Error('Não foi possível concluir a consulta. O resultado anterior foi preservado.');
        if(report.status!=='confirmed'){
          const reasons={configuration_incomplete:'A conexão desta conta está incompleta ou não foi confirmada.',
            unsupported_request:'A Meta não disponibilizou estes metadados para este acesso.',
            permission_denied:'A Meta recusou o acesso aos metadados das conversas.',token_invalid:'A Meta recusou o token salvo.',
            message_access_disabled:'O acesso externo às mensagens está desativado no Instagram.',
            transport_error:'Não foi possível concluir a comunicação com a Meta.',invalid_response:'A Meta retornou metadados em formato inesperado.'};
          const codes=[['HTTP',report.http_status],['código Meta',report.provider_code],['subcódigo',report.provider_subcode]]
            .filter(item=>Number.isInteger(item[1])).map(item=>item[0]+' '+item[1]).join(', ');
          throw new Error((reasons[report.reason] || 'A consulta não foi concluída.')+(codes?' ('+codes+')':'')+' O resultado anterior foi preservado.');
        }
        if(![report.sample_count,report.owned,report.other,report.unspecified].every(v=>Number.isInteger(v)&&v>=0&&v<=5)
          || report.sample_count!==report.owned+report.other+report.unspecified || !Number.isInteger(report.checked_at))
          throw new Error('Não foi possível confirmar o resultado. O resultado anterior foi preservado.');
        const lines=['Consulta confirmada: '+date(report.checked_at)+'.','Conversas na amostra: '+report.sample_count+'.'];
        if(report.sample_count){
          lines.push('Sob controle do nosso aplicativo: '+report.owned+'.','Fora do controle do nosso aplicativo: '+report.other+'.',
            'Controle não informado pela Meta: '+report.unspecified+'.');
          lines.push(Number.isInteger(report.latest_activity)?'Atividade mais recente na amostra: '+date(report.latest_activity)+'.':'Atividade recente não informada pela Meta.');
          if(report.unspecified)lines.push('Campo de controle ausente não comprova erro de encaminhamento.');
        }else lines.push('A Meta não retornou conversas nesta amostra. Isso não comprova ausência de conversas no Instagram.');
        lines.push('Esta consulta não comprova entrega de webhook nem muda o aplicativo padrão.');
        result.replaceChildren(...lines.map(line=>make('p','',line)));
        feedback.textContent='Consulta concluída. Estes metadados não ficam salvos ao recarregar a página.';announce(feedback.textContent);
      }catch(error){
        feedback.textContent=['TimeoutError','AbortError'].includes(error.name) || error instanceof TypeError
          ?'A consulta foi interrompida. O resultado anterior foi preservado.':error.message;announce(feedback.textContent);
      }finally{done();progress.end();}
    });
  }
  function initIntegrationSettings(){
    const section=document.querySelector('[data-integration-base]');if(!section)return;
    const find=id=>section.querySelector('#integration-'+id),feedback=find('feedback');
    let busy=false;
    const say=text=>{feedback.textContent=text;announce(text);};
    const hide=()=>{find('token').value='';find('secret').hidden=true;};
    addEventListener('pagehide',hide);
    const api=async(action,data={})=>{
      const request=async(path,options={})=>{
        const response=await fetch(section.dataset.integrationBase+'api/'+path,{
          credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(35000),...options
        });
        let result;const raw=await response.text();
        try{if(raw.length<=65536)result=JSON.parse(raw);}catch(_){}
        if(response.status===403)throw new Error('A sessão expirou ou a operação não foi autorizada. Entre novamente e tente outra vez.');
        if(!response.ok || !result || typeof result!=='object' || Array.isArray(result))
          throw new Error([409,422].includes(response.status) && typeof result?.error==='string'
            ?result.error:'Não foi possível concluir a operação. Confira as conexões antes de repetir.');
        return result;
      };
      const tokens=await request('csrf');
      if(typeof tokens[action]!=='string' || !/^[a-f0-9]{64}$/.test(tokens[action]))throw new Error('A operação não foi autorizada. Recarregue a página.');
      return request('drafts',{method:'POST',headers:{'Content-Type':'application/json',
        'X-Editorial-Action':action,'X-CSRF-Token':tokens[action]},body:JSON.stringify(data)});
    };
    const run=async(button,label,operation)=>{
      if(busy)return;busy=true;
      const done=hold(button,label),progress=start(label);
      const controls=[...section.querySelectorAll('button,input')].filter(node=>node!==button);
      const saved=controls.map(node=>node.disabled);controls.forEach(node=>node.disabled=true);
      try{await operation();}catch(error){
        say(error instanceof TypeError || ['AbortError','TimeoutError'].includes(error.name)
          ?'A conexão foi interrompida. Confira as conexões antes de repetir.':error.message);
      }finally{controls.forEach((node,index)=>node.disabled=saved[index]);done();progress.end();busy=false;}
    };
    const list=async()=>{
      const result=await api('integration_list');
      if(!Array.isArray(result.connections))throw new Error('Não foi possível carregar as conexões. Tente novamente.');
      const target=find('connections');target.replaceChildren();
      for(const item of result.connections){
        const row=make('div','integration-row');
        const expiry=new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeZone:'America/Sao_Paulo'}).format(new Date(item.expires*1000));
        const status=item.revoked?'Revogada':item.expires*1000<Date.now()?'Expirada':item.canPublish?'Transferência e publicação direta':'Somente transferência';
        row.append(make('span','',item.label+' · '+status+' · validade: '+expiry));
        if(!item.revoked){
          const revoke=make('button','btn quiet','Revogar');revoke.type='button';
          revoke.setAttribute('aria-label','Revogar conexão '+item.label);
          revoke.addEventListener('click',()=>{
            if(busy || !confirm('Revogar a conexão '+item.label+'?'))return;
            run(revoke,'Revogando…',async()=>{await api('integration_revoke',{id:item.id});await list();say('Conexão revogada.');});
          });row.append(revoke);
        }
        target.append(row);
      }
      if(!result.connections.length)target.textContent='Nenhuma conexão criada para esta conta.';
    };
    find('list').addEventListener('click',()=>run(find('list'),'Carregando conexões…',async()=>{await list();say('Lista de conexões atualizada.');}));
    find('create').addEventListener('click',()=>{
      if(busy)return;
      const label=find('label').value.trim(),canPublish=find('publish').checked;
      if(!label){say('Informe o nome da ferramenta.');find('label').focus();return;}
      if(canPublish && !confirm('Permitir que esta ferramenta publique nesta conta quando você autorizar uma publicação direta?'))return;
      run(find('create'),'Criando conexão…',async()=>{
        hide();const result=await api('integration_create',{label,canPublish});
        if(typeof result.token!=='string' || !/^cei1\.[a-z][a-z0-9_-]{1,39}\.[0-9a-f]{32}\.[A-Za-z0-9_-]{43}$/.test(result.token))throw new Error('Não foi possível confirmar a chave. Confira as conexões antes de repetir.');
        find('token').value=result.token;find('secret').hidden=false;
        try{await list();say('Conexão criada. Guarde a chave na configuração privada da ferramenta.');}
        catch(_){say('Conexão criada e chave exibida. Não foi possível atualizar a lista; use Ver conexões.');}
      });
    });
    find('copy').addEventListener('click',()=>run(find('copy'),'Copiando…',async()=>{
      if(!find('token').value)throw new Error('Crie uma conexão para obter a chave.');
      await navigator.clipboard.writeText(find('token').value);say('Chave copiada. Guarde apenas na configuração privada da ferramenta.');
    }));
    find('hide').addEventListener('click',()=>{if(!busy){hide();say('Chave ocultada.');}});
  }
  function init(){
    ensureFeedback();document.documentElement.dataset.uiInput='pointer';
    document.querySelector('[data-account-switch]')?.addEventListener('change',event=>{
      const target=new URL(event.target.value,location.href);if(target.origin!==location.origin)return;
      if(location.pathname.endsWith('/editorial/') && target.pathname.endsWith('/editorial/'))target.hash=location.hash;
      start('Abrindo a conta selecionada…');document.body.classList.add('ui-page-leaving');location.assign(target.href);
    });
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
    addEventListener('hashchange',syncNativeNav);syncNativeNav();initPublicationSettings();initInboxRefresh();initRoutingSettings();initIntegrationSettings();
    if(!instant()){
      document.body.classList.add('ui-page-enter');
      requestAnimationFrame(()=>{document.body.classList.remove('ui-page-enter');document.body.classList.add('ui-page-ready');});
    }
  }
  function syncNativeNav(){
    if(location.pathname.endsWith('/editorial/') || location.pathname.endsWith('/editorial'))return;
    // Old bookmarks lead to the separate settings document, preserving account.
    if(location.hash==='#connection' && !location.search){
      const link=document.querySelector('.ui-sidebar a[href$="/panel?view=settings"]');
      if(link)location.replace(link.href);
    }
  }
  window.CentralUI={start,hold,announce,instant,switchPanel,media:trackMedia,releaseMedia,ready,initialError,
    dialog:{open:openDialog,close:closeDialog},closeMenu:()=>setMenu(false)};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
