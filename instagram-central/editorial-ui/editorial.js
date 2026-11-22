/* Central Instagram: Editorial persistente, mesma sessão administrativa. */
(() => {
  'use strict';
  const UI=window.CentralUI;
  const MAX_UPLOAD = 25 * 1024 * 1024;
  const FORMATS = {feed:'Publicação',carousel:'Carrossel',story:'Story',reel:'Reel'};
  const STATUS = {draft:'Aguardando aprovação',approved:'Aprovada',scheduled:'Agendada',leased:'Em processamento',publishing:'Publicando',published:'Publicada',failed:'Envio interrompido',needs_review:'Verificar resultado'};
  const state = {
    view:'overview', posts:[], media:[], currentPostId:null, currentPostVersion:null, currentMediaIds:[],
    pickerIds:[], month:new Date(), pendingSchedule:null, toastTimer:null,
    currentSlideCaptions:{}, currentPreviewIndex:0, modalPostId:null, modalPreviewIndex:0,
    publication:{}, accountUsername:'', pendingPublish:null, busy:false,actionPending:false,
    dataFingerprint:null,refreshPending:null,uploadLabel:'',editorPreviewKey:null,pendingDelete:null
  };
  const $ = id => document.getElementById(id);
  const all = selector => [...document.querySelectorAll(selector)];
  const escapeName = value => String(value || '').trim();
  const friendlyDate = epoch => new Intl.DateTimeFormat('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(epoch));
  const formatMonth = d => new Intl.DateTimeFormat('pt-BR',{timeZone:'UTC',month:'long',year:'numeric'}).format(d);
  const previewUrl = item => item ? item.url : '';
  const formatLabel = value => FORMATS[value] || 'Publicação';
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  };
  const clear = node => {UI.releaseMedia(node);node.replaceChildren();};
  const actionLabels={upload:'Enviando mídia…',draft:'Salvando rascunho…',approve:'Aprovando conteúdo…',
    schedule:'Confirmando agendamento…',cancel:'Cancelando agendamento…',check:'Verificando publicação…',
    publish:'Preparando publicação…',activate:'Confirmando envio agendado…',reset:'Liberando conteúdo para edição…',
    reconcile:'Verificando o resultado…',retry:'Conferindo nova tentativa…',
    delete_post:'Excluindo publicação local…',delete_media:'Excluindo mídia…'};

  function uploadRequest(endpoint,file,headers,operation){
    return new Promise((resolve,reject)=>{
      const request=new XMLHttpRequest();request.open('POST','api/'+endpoint);request.withCredentials=true;request.timeout=120000;
      Object.entries(headers).forEach(([name,value])=>request.setRequestHeader(name,value));
      request.upload.addEventListener('progress',event=>{
        if(!event.lengthComputable || !event.total)return;
        const percent=100*event.loaded/event.total;
        operation.update((state.uploadLabel || 'Enviando arquivo')+' — '+Math.round(percent)+'%',percent);
        if(event.loaded===event.total)operation.update('Arquivo enviado. Validando e salvando…');
      });
      request.addEventListener('load',()=>resolve({status:request.status,ok:request.status>=200&&request.status<300,text:async()=>request.responseText}));
      ['error','abort','timeout'].forEach(kind=>request.addEventListener(kind,()=>reject(new Error('Não foi possível confirmar o upload. Confira a biblioteca antes de tentar novamente.'))));
      request.send(file);
    });
  }

  async function api(path, {action, data, file}={}) {
    const operation=action?UI.start(state.uploadLabel || actionLabels[action] || 'Processando…'):null;
    try{
    const headers = {};
    let endpoint=path;
    if(['check','delete_media'].includes(action)){
      endpoint='drafts';headers['X-Editorial-Action']=action;
    }else if(['publish','activate','reset','reconcile','retry','delete_post'].includes(action)){
      endpoint=path.replace(/\/[^/]+$/,'/approve');headers['X-Editorial-Action']=action;
    }
    if(action){
      const tokens = await api('csrf');
      headers['X-CSRF-Token'] = tokens[action];
      headers['Content-Type'] = file ? file.type : 'application/json';
    }
    let response;
    try{
      response = file ? await uploadRequest(endpoint,file,headers,operation) : await fetch('api/'+endpoint, {
        method:action ? 'POST' : 'GET', credentials:'same-origin', cache:'no-store',
        headers, body:action ? (file || JSON.stringify(data)) : undefined
      });
    }catch(_){throw new Error('A conexão foi interrompida. Recarregue e confira o resultado antes de repetir o envio.');}
    // A proxy may return plain text/HTML instead of JSON. Never show parser internals.
    const raw=await response.text();
    let result;
    try { result=JSON.parse(raw); } catch (_) { /* handled below */ }
    if(!result || typeof result!=='object' || Array.isArray(result)){
      const error=new Error('O servidor retornou uma resposta inesperada. Nenhuma gravação foi confirmada.');
      error.status=response.status;
      error.unexpectedResponse=true;
      throw error;
    }
    if(!response.ok){
      const error=new Error(typeof result.error==='string' ? result.error : 'Operação recusada');
      error.status=response.status;
      throw error;
    }
    return result;
    }finally{operation?.end();}
  }
  async function refresh() {
    if(state.refreshPending)return state.refreshPending;
    state.refreshPending=(async()=>{
    const result = await api('state');
    state.publication=result.publication || {};state.accountUsername=result.accountUsername || '';
    $('publication-status').textContent=state.publication.message || 'Verifique o acesso de publicação.';
    const fingerprint=JSON.stringify([result.posts,result.media]);
    if(fingerprint!==state.dataFingerprint){
      state.posts=result.posts;state.media=result.media;state.dataFingerprint=fingerprint;render();
    }
    })();
    try{return await state.refreshPending;}finally{state.refreshPending=null;}
  }
  function toast(message, kind='success') {
    $('toast').textContent = message;
    $('toast').classList.toggle('error',kind==='error');
    $('toast').classList.add('visible');
    if (state.toastTimer) clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(()=>$('toast').classList.remove('visible'),3800);
  }
  function clearOperationFeedback(id) {
    const target=$(id);
    if(!target)return;
    target.textContent='';
    target.setAttribute('role','status');
    target.setAttribute('aria-live','polite');
  }
  function actionErrorFeedback(id,error) {
    const target=$(id);
    if(!target)return;
    const sessionEnded=error?.status===403;
    target.textContent=sessionEnded
      ? 'Não foi possível confirmar a operação. Verifique sua sessão e entre novamente se necessário.'
      : 'Não foi possível confirmar a operação. O resultado do salvamento é desconhecido. '
        +'Atualize a página e confira os dados antes de tentar novamente.';
    target.setAttribute('role','alert');
    target.setAttribute('aria-live','assertive');
    target.scrollIntoView({block:'nearest'});
  }
  function clearDraftFeedback() {
    const feedback=$('form-feedback');
    feedback.textContent='';
    feedback.setAttribute('role','status');
    feedback.setAttribute('aria-live','polite');
    feedback.removeAttribute('tabindex');
  }
  function draftConflictFeedback() {
    const feedback=$('form-feedback');
    feedback.textContent='Não foi salvo: esta publicação foi alterada em outra aba. '
      +'Seu texto continua neste formulário, mas não foi gravado. '
      +'Copie o texto se precisar e abra a publicação novamente em Revisão e envios → Editar para usar a versão atual.';
    feedback.setAttribute('role','alert');
    feedback.setAttribute('aria-live','assertive');
    feedback.tabIndex=-1;
    feedback.focus({preventScroll:true});
    feedback.scrollIntoView({block:'nearest'});
    toast('Salvamento recusado: outra aba alterou esta publicação.','error');
  }
  function show(view) {
    if (!['overview','library','editor','approval','calendar'].includes(view)) return;
    state.view = view;
    const panels=all('[data-panel]');
    UI.switchPanel(panels,$('view-'+view));UI.closeMenu();
    all('[data-view]').forEach(node=>{
      const active=node.dataset.view===view;
      node.classList.toggle('active',active);
      if (active) node.setAttribute('aria-current','page');else node.removeAttribute('aria-current');
    });
    $('current-section').textContent = ({overview:'Visão geral',library:'Biblioteca',editor:state.currentPostId?'Editar publicação':'Criar publicação',approval:'Revisão e envios',calendar:'Calendário'})[view];
    history.replaceState(null,'','#'+view);
    render();
  }
  function formatHint() {
    const fmt = $('post-format').value;
    $('selection-hint').textContent=({
      feed:'De 1 a 20 imagens JPG ou PNG, entre 4:5 e 1,91:1; 2 ou mais formam um carrossel. A imagem para envio deve ter até 8 MB.',
      story:'Uma imagem ou MP4 de 3 a 60 segundos. Inclua o texto na própria mídia; deixe a legenda vazia. Requer conta Empresa.',
      reel:'Um MP4 de 3 segundos a 15 minutos. Limite de upload da Central: 25 MiB.'
    })[fmt] || 'Selecione uma mídia.';
  }
  function selectedMedia() {
    return state.currentMediaIds.map(id=>state.media.find(m=>m.id===id)).filter(Boolean);
  }
  function mediaValid(format, items) {
    if (format === 'carousel') return items.length >= 2 && items.length <= 20 && items.every(m=>m.type.startsWith('image/'));
    if (format === 'feed') return items.length === 1 && items[0].type.startsWith('image/');
    if (format === 'reel') return items.length === 1 && items[0].type === 'video/mp4';
    return format === 'story' && items.length === 1;
  }
  function newDraft(format='feed') {
    if(state.actionPending || state.busy)return UI.announce('Aguarde a conclusão da operação atual.');
    state.currentPostId=null;
    state.currentPostVersion=null;
    state.currentMediaIds=[];
    state.currentSlideCaptions={};
    state.currentPreviewIndex=0;
    state.editorPreviewKey=null;
    document.querySelector('input[name="caption-mode"][value="general"]').checked=true;
    $('post-format').value=format === 'carousel' ? 'feed' : (FORMATS[format] ? format : 'feed');
    $('post-caption').value='';
    $('editor-heading').textContent='Nova publicação';
    clearDraftFeedback();
    formatHint();
    renderSelection();
    show('editor');
  }
  function loadDraft(id) {
    const post=state.posts.find(p=>p.id===id);
    if (!post) return toast('Publicação não encontrada.');
    if(!['draft','approved','scheduled'].includes(post.status))return toast('Conteúdo bloqueado para revisão.');
    state.currentPostId=id;
    state.editorPreviewKey=null;
    state.currentPostVersion=post.version;
    state.currentMediaIds=[...post.mediaIds];
    state.currentSlideCaptions={};
    post.mediaIds.forEach((id,i)=>{state.currentSlideCaptions[id]=post.slideCaptions?.[i] || '';});
    state.currentPreviewIndex=0;
    const mode=post.captionMode==='per_slide' ? 'per_slide' : 'general';
    document.querySelector('input[name="caption-mode"][value="'+mode+'"]').checked=true;
    $('post-format').value=post.format==='carousel' ? 'feed' : post.format;
    $('post-caption').value=post.caption;
    $('editor-heading').textContent='Editar publicação';
    clearDraftFeedback();
    formatHint();
    renderSelection();
    show('editor');
  }
  function render() {
    $('count-all').textContent=state.posts.length;
    $('count-draft').textContent=state.posts.filter(p=>p.status==='draft').length;
    $('count-approved').textContent=state.posts.filter(p=>p.status==='approved').length;
    $('count-scheduled').textContent=state.posts.filter(p=>p.status==='scheduled').length;
    if(state.view==='overview')renderUpcoming();
    else if(state.view==='library')renderLibrary();
    else if(state.view==='approval')renderApprovals();
    else if(state.view==='calendar')renderCalendar();
    else if(state.view==='editor')renderSelection();
  }
  function empty(target,message) { clear(target); target.append(el('div','empty',message)); }
  function badge(status) { return el('span','chip '+status,STATUS[status] || 'Revisão necessária'); }
  function calendarTime(post) { return post.scheduledAt || post.pendingScheduledAt || null; }
  function pendingApproval(post) { return post.status==='draft' && !!post.pendingScheduledAt; }
  function expiredReservation(post) {
    return post.status==='approved' && !!post.pendingScheduledAt &&
      post.pendingScheduledAt<=Date.now();
  }
  function postText(post) {
    return post.caption?.trim() || post.slideCaptions?.find(t=>t.trim())?.trim() || '';
  }
  function postRow(post, options={}) {
    const row=el('article','item');
    if(pendingApproval(post))row.classList.add('pending-review');
    else if(expiredReservation(post))row.classList.add('expired-reservation');
    const preview=el('button','post-preview-trigger');
    preview.type='button';
    preview.setAttribute('aria-label','Visualizar publicação: '+(postText(post).slice(0,60)||formatLabel(post.format)));
    preview.addEventListener('click',()=>openPostPreview(post.id));
    const first=state.media.find(m=>m.id===post.mediaIds?.[0]);
    const thumb=el('span','post-preview-thumb');
    if(first) {
      const media=el(first.type.startsWith('image/')?'img':'video');
      UI.media(media,previewUrl(first),thumb);
      if(media.tagName==='IMG')media.alt='Miniatura da publicação';
      else{media.muted=true;media.playsInline=true;}
      thumb.append(media);
    } else thumb.append(el('span','post-thumb-fallback','Sem imagem'));
    const content=el('span','item-content');
    const text=postText(post);
    const title=text.split(/\n/)[0].trim().slice(0,62) || 'Publicação sem legenda';
    const detail=text.slice(title.length).trim() || text;
    content.append(el('strong','post-title',title));
    content.append(el('span','post-excerpt',detail.slice(0,160)));
    const date=calendarTime(post);
    content.append(el('small','post-kind',formatLabel(post.format)+(date ? ' · '+friendlyDate(date) : '')));
    if(pendingApproval(post)){
      content.append(el('span','chip awaiting-review','Aguardando nova aprovação'));
    }else if(expiredReservation(post)){
      content.append(el('span','chip expired-review','Horário expirado · Reagende'));
    }else{
      content.append(post.status==='scheduled' && !post.publishAuthorized
        ? el('span','chip awaiting-review','Confirme o envio deste agendamento') : badge(post.status));
    }
    if(post.publicationMessage)content.append(el('small','publication-error',post.publicationMessage));
    if(post.status==='publishing'){
      const progress=el('span','ui-job-progress');
      const label=({create:'Preparando mídias para o Instagram…',poll:'A Meta está processando a mídia…',ready:'Mídia pronta. Preparando o envio…',confirm:'Conferindo o resultado na Meta…'})[post.publicationPhase] || 'Preparando a publicação…';
      progress.append(el('span','',label));const track=el('span','ui-progress');track.dataset.indeterminate='true';
      track.setAttribute('role','progressbar');track.setAttribute('aria-label',label);track.append(el('span','ui-progress-fill'));progress.append(track);content.append(progress);
    }
    preview.append(thumb,content);
    row.append(preview);
    const actions=el('div','item-actions');
    const edit=el('button','btn quiet','Editar');edit.type='button';edit.disabled=!['draft','approved','scheduled'].includes(post.status);edit.addEventListener('click',()=>loadDraft(post.id));actions.append(edit);
    if(options.approval && post.status==='draft'){
      const approve=el('button','btn primary','Aprovar');approve.type='button';
      approve.addEventListener('click',()=>guard(()=>approvePost(post.id)));actions.append(approve);
    }
    if(options.approval && post.status==='approved'){
      const schedule=el('button','btn primary','Agendar');schedule.type='button';
      schedule.addEventListener('click',()=>schedulePost(post.id));actions.append(schedule);
      const publish=el('button','btn primary','Publicar agora');publish.type='button';
      publish.addEventListener('click',()=>confirmPublication(post,'publish'));actions.append(publish);
    }
    if(options.approval && post.status==='scheduled'){
      const cancel=el('button','btn quiet','Cancelar agenda');cancel.type='button';
      cancel.addEventListener('click',()=>guard(()=>cancelSchedule(post.id)));actions.append(cancel);
    }
    if(post.status==='scheduled' && !post.publishAuthorized){
      const activate=el('button','btn primary','Confirmar envio agendado');activate.type='button';
      activate.addEventListener('click',()=>confirmPublication(post,'activate'));actions.append(activate);
    }
    if(['failed','needs_review'].includes(post.status)){
      const recover=el('button','btn quiet',post.publicationAttempted?'Verificar resultado':'Voltar ao rascunho');recover.type='button';
      recover.addEventListener('click',()=>guard(()=>recoverPost(post,post.publicationAttempted?'reconcile':'reset')));actions.append(recover);
      if(post.publicationAttempted){
        const retry=el('button','btn quiet','Liberar nova tentativa');retry.type='button';
        retry.addEventListener('click',()=>guard(()=>recoverPost(post,'retry')));actions.append(retry);
      }
    }
    if(post.status==='published'){
      const link=el('a','btn quiet','Ver no Instagram');
      const remote=post.permalink;
      link.href=typeof remote==='string' && /^https:\/\/(www\.)?instagram\.com\/(p|reel|stories)\/[A-Za-z0-9_/-]+$/.test(remote)
        ? remote : 'https://www.instagram.com/'+encodeURIComponent(state.accountUsername)+'/';
      link.target='_blank';link.rel='noopener noreferrer';actions.append(link);
    }
    if(options.approval){
      const remove=el('button','btn quiet danger','Excluir');remove.type='button';
      remove.disabled=!['draft','approved','scheduled','failed','published'].includes(post.status) ||
        (post.publicationAttempted && post.status!=='published');
      if(remove.disabled)remove.title='Confira o resultado do envio antes de excluir.';
      remove.addEventListener('click',()=>requestDeletion('post',post));actions.append(remove);
    }
    row.append(actions);
    return row;
  }
  function renderUpcoming() {
    const target=$('upcoming-list');
    const items=state.posts.filter(p=>p.status==='scheduled').sort((a,b)=>a.scheduledAt-b.scheduledAt).slice(0,5);
    if(!items.length)return empty(target,'Nenhuma publicação agendada. Crie uma publicação para começar.');
    clear(target);items.forEach(p=>target.append(postRow(p)));
  }
  function renderApprovals() {
    const target=$('approval-list');
    const items=state.posts;
    if(!items.length)return empty(target,'Nenhuma publicação criada. Use “Nova publicação” para começar.');
    clear(target);items.forEach(p=>target.append(postRow(p,{approval:true})));
  }
  function monitorMediaLoad(media, target) {
    media.addEventListener('error',()=>{
      if(!target.isConnected)return;
      const message=el('span','media-load-failed',
        'Não foi possível carregar esta mídia. Atualize a página para tentar novamente.');
      message.setAttribute('role','status');
      target.append(message);
    },{once:true});
  }
  function mediaCard(item, selected=false, clickable=false) {
    const node=el(clickable?'button':'div','media-card'+(selected?' selected':''));
    if(clickable)node.type='button';
    const visual=el('div','media-card-visual');
    const url=previewUrl(item);
    const media=el(item.type.startsWith('image/')?'img':'video');
    UI.media(media,url,visual);
    if(media.tagName==='IMG')media.alt=item.name;
    else{media.muted=true;media.playsInline=true;}
    monitorMediaLoad(media,visual);
    visual.append(media);node.append(visual);
    const info=el('div','media-card-info');info.append(el('strong','',item.name),el('small','',Math.max(1,Math.round(item.size/1024))+' KB'));
    node.append(info);return node;
  }
  function renderLibrary() {
    const grid=$('media-grid');clear(grid);
    if(!state.media.length)return empty(grid,'Sua biblioteca está vazia. Adicione imagens ou vídeos.');
    state.media.forEach(m=>{
      const card=mediaCard(m);card.dataset.mediaId=m.id;
      const remove=el('button','btn quiet danger','Excluir mídia');remove.type='button';
      remove.disabled=m.usageCount>0;
      if(remove.disabled){
        const usage='Em uso por '+m.usageCount+' publicação(ões).';remove.title=usage;
        card.append(el('small','media-usage',usage));
      }
      remove.addEventListener('click',()=>requestDeletion('media',m));card.append(remove);grid.append(card);
    });
  }
  function renderPicker() {
    const grid=$('picker-grid');clear(grid);
    if(!state.media.length)return empty(grid,'Adicione arquivos pela Biblioteca antes de selecionar.');
    state.media.forEach(m=>{
      const button=mediaCard(m,state.pickerIds.includes(m.id),true);
      button.setAttribute('aria-pressed',String(state.pickerIds.includes(m.id)));
      button.addEventListener('click',()=>{
        if(state.pickerIds.includes(m.id))state.pickerIds=state.pickerIds.filter(id=>id!==m.id);
        else if(state.pickerIds.length<20)state.pickerIds.push(m.id);
        else return toast('Limite de 20 itens por publicação.');
        renderPicker();
      });
      grid.append(button);
    });
  }
  function effectiveFormat() {
    return $('post-format').value==='feed' && selectedMedia().length>=2
      ? 'carousel' : $('post-format').value;
  }
  function captionMode() {
    return document.querySelector('input[name="caption-mode"]:checked')?.value==='per_slide'
      ? 'per_slide' : 'general';
  }
  function renderCaptionControls() {
    const items=selectedMedia();
    const isCarousel=effectiveFormat()==='carousel' && items.every(m=>m.type.startsWith('image/'));
    $('carousel-caption-options').classList.toggle('hidden',!isCarousel);
    const perSlide=isCarousel && captionMode()==='per_slide';
    $('general-caption-field').classList.toggle('hidden',perSlide);
    const target=$('slide-caption-fields');clear(target);
    target.classList.toggle('hidden',!perSlide);
    if(!perSlide)return;
    items.forEach((item,i)=>{
      const row=el('div','slide-caption-row');
      const label=el('label','',('Imagem '+(i+1)+' de '+items.length));
      const input=el('textarea','slide-caption-input');
      input.rows=3;input.maxLength=2200;
      input.value=state.currentSlideCaptions[item.id] || '';
      input.placeholder='Legenda desta imagem (somente editorial local)';
      label.append(input);row.append(label);
      input.addEventListener('input',()=>{
        state.currentSlideCaptions[item.id]=input.value;
        renderEditorPreview();
      });
      target.append(row);
    });
  }
  function drawMediaFrame(target,captionTarget,items,index,caption,mode,slideCaptions,onChange) {
    clear(target);
    const item=items[index];
    if(!item) {
      target.append(el('span','','Selecione uma mídia para visualizar'));
      captionTarget.textContent=caption?.trim() || 'Sua legenda aparece aqui.';
      return;
    }
    const media=el(item.type.startsWith('image/')?'img':'video');
    media.className='phone-frame-media';
    if(media.tagName==='IMG') media.alt='Imagem '+(index+1)+' da publicação';
    else{media.controls=true;media.muted=true;media.playsInline=true;}
    UI.media(media,previewUrl(item),target);
    monitorMediaLoad(media,target);
    target.append(media);
    if(items.length>1) {
      const controls=el('div','phone-carousel-controls');
      const prev=el('button','carousel-arrow','‹');prev.type='button';prev.disabled=index===0;
      prev.setAttribute('aria-label','Imagem anterior');
      prev.addEventListener('click',()=>onChange(index-1));
      const counter=el('span','carousel-counter',(index+1)+' / '+items.length);
      const next=el('button','carousel-arrow','›');next.type='button';next.disabled=index===items.length-1;
      next.setAttribute('aria-label','Próxima imagem');
      next.addEventListener('click',()=>onChange(index+1));
      controls.append(prev,counter,next);target.append(controls);
    }
    captionTarget.textContent=(mode==='per_slide'
      ? (slideCaptions[index] || '')
      : (caption || '')).trim() || 'Sem legenda nesta imagem.';
  }
  function renderEditorPreview() {
    const items=selectedMedia();
    state.currentPreviewIndex=Math.min(state.currentPreviewIndex,Math.max(0,items.length-1));
    const mode=effectiveFormat()==='carousel' && captionMode()==='per_slide'?'per_slide':'general';
    const key=JSON.stringify([items.map(item=>item.id),state.currentPreviewIndex]);
    if(state.editorPreviewKey===key){
      $('preview-caption').textContent=(mode==='per_slide'
        ? state.currentSlideCaptions[items[state.currentPreviewIndex]?.id] || ''
        : $('post-caption').value).trim() || (items.length?'Sem legenda nesta imagem.':'Sua legenda aparece aqui.');
      return;
    }
    state.editorPreviewKey=key;
    drawMediaFrame($('phone-media'),$('preview-caption'),items,state.currentPreviewIndex,
      $('post-caption').value,mode,items.map(item=>state.currentSlideCaptions[item.id] || ''),
      index=>{state.currentPreviewIndex=index;renderEditorPreview();});
  }
  function renderModalPreview() {
    const post=state.posts.find(p=>p.id===state.modalPostId);
    if(!post)return;
    const items=post.mediaIds.map(id=>state.media.find(m=>m.id===id)).filter(Boolean);
    state.modalPreviewIndex=Math.min(state.modalPreviewIndex,Math.max(0,items.length-1));
    drawMediaFrame($('modal-phone-media'),$('modal-preview-caption'),items,state.modalPreviewIndex,
      post.caption,post.captionMode||'general',post.slideCaptions||[],
      index=>{state.modalPreviewIndex=index;renderModalPreview();});
    $('modal-preview-description').textContent=formatLabel(post.format)+' · '+(STATUS[post.status] || 'Revisão necessária');
  }
  function openPostPreview(id) {
    const post=state.posts.find(p=>p.id===id);
    if(!post)return toast('Publicação indisponível.');
    state.modalPostId=id;state.modalPreviewIndex=0;
    renderModalPreview();
    UI.dialog.open($('preview-dialog'));
  }
  function renderSelection(){
    const target=$('selected-media');clear(target);
    const items=selectedMedia();
    if(!items.length)target.append(el('span','','Nenhuma mídia selecionada.'));
    for(const item of items){
      const thumb=el('span','selected-thumb',item.name);
      const remove=el('button','','×');remove.type='button';remove.setAttribute('aria-label','Remover '+item.name);
      remove.addEventListener('click',()=>{
        state.currentMediaIds=state.currentMediaIds.filter(id=>id!==item.id);
        state.currentPreviewIndex=0;
        renderSelection();
      });
      thumb.append(remove);target.append(thumb);
    }
    $('caption-count').textContent=$('post-caption').value.length+'/2200';
    renderCaptionControls();
    renderEditorPreview();
  }
  async function uploadFiles(files) {
    let added=0, skipped=0;
    let index=0;
    try{
    for(const file of files){
      index++;
      if(!['image/jpeg','image/png','video/mp4'].includes(file.type) || file.size===0 || file.size>MAX_UPLOAD){skipped++;continue;}
      const bytes=new Uint8Array(await file.slice(0,12).arrayBuffer());
      const valid=file.type==='image/jpeg' ? bytes[0]===255 && bytes[1]===216 && bytes[2]===255
        :file.type==='image/png' ? [137,80,78,71,13,10,26,10].every((v,i)=>bytes[i]===v)
        :bytes.length>=12 && String.fromCharCode(...bytes.slice(4,8))==='ftyp';
      if(!valid){skipped++;continue;}
      state.uploadLabel='Enviando mídia '+index+' de '+files.length;
      await api('media',{action:'upload',file});
      added++;
    }
    await refresh();
    clearOperationFeedback('library-feedback');
    toast(added+' arquivo(s) salvo(s) na biblioteca da Central.'+(skipped?' '+skipped+' ignorado(s) por formato ou tamanho.':''));
    }finally{state.uploadLabel='';}
  }
  async function savePost(navigate=false) {
    const media=selectedMedia(),format=effectiveFormat();
    const mode=format==='carousel' && captionMode()==='per_slide'?'per_slide':'general';
    const caption=mode==='per_slide'?'':$('post-caption').value.trim();
    const slideCaptions=media.map(item=>mode==='per_slide'
      ? (state.currentSlideCaptions[item.id] || '').trim() : '');
    if(!FORMATS[format] || caption.length>2200 || slideCaptions.some(t=>t.length>2200)){
      $('form-feedback').textContent='Confira o formato e as legendas.';return;
    }
    if(!mediaValid(format,media)){
      $('form-feedback').textContent='Selecione mídias compatíveis com o formato. '+$('selection-hint').textContent;return;
    }
    const current=state.posts.find(p=>p.id===state.currentPostId);
    if(current && !['draft','approved','scheduled'].includes(current.status)){
      $('form-feedback').textContent='Esta publicação não pode ser editada.';return;
    }
    const changed=!current || current.format!==format || current.caption!==caption ||
      JSON.stringify(current.mediaIds)!==JSON.stringify(state.currentMediaIds) ||
      (current.captionMode || 'general')!==mode ||
      JSON.stringify(current.slideCaptions || current.mediaIds.map(()=>''))!==JSON.stringify(slideCaptions);
    if(current && !changed){toast('Conteúdo sem alterações.');if(navigate)show('approval');return;}
    const data={format,caption,mediaIds:[...state.currentMediaIds],captionMode:mode,slideCaptions};
    if(current){data.id=current.id;data.version=state.currentPostVersion;}
    const saved=await api('drafts',{action:'draft',data});
    state.currentPostId=saved.id;
    clearDraftFeedback();
    await refresh();
    state.currentPostVersion=state.posts.find(p=>p.id===saved.id)?.version;
    toast('Rascunho salvo. A revisão anterior, se houver, foi invalidada.');
    if(navigate)show('approval');
  }
  async function approvePost(id) {
    const post=state.posts.find(p=>p.id===id);
    if(!post || post.status!=='draft')return;
    const items=post.mediaIds.map(mid=>state.media.find(m=>m.id===mid)).filter(Boolean);
    if(!mediaValid(post.format,items))return toast('Não é possível aprovar: confira as mídias.');
    await api('posts/'+id+'/approve',{action:'approve',data:{version:post.version}});
    await refresh();
    const updated=state.posts.find(p=>p.id===id);
    if(updated?.status==='scheduled')toast('Aprovada. Agendamento original restaurado. Nenhum envio foi realizado.');
    else if(updated?.pendingScheduledAt)toast('Aprovada. A data anterior já passou; escolha novo horário.');
    else toast('Publicação aprovada. Nenhum envio foi realizado.');
  }
  function renderScheduleSummary(post, targetId='schedule-post-preview') {
    const target=$(targetId);clear(target);
    const thumb=el('span','schedule-post-thumb');
    const first=state.media.find(media=>media.id===post.mediaIds?.[0]);
    if(first){
      const media=el(first.type.startsWith('image/')?'img':'video');
      if(media.tagName==='IMG')media.alt='Miniatura da publicação selecionada';
      else{media.muted=true;media.playsInline=true;}
      UI.media(media,previewUrl(first),thumb);
      thumb.append(media);
    }else thumb.append(el('span','schedule-thumb-fallback','Sem miniatura'));
    const body=el('div','schedule-post-content');
    const caption=postText(post);
    const title=caption.split(/\n/)[0].trim().slice(0,62) || 'Publicação sem legenda';
    const summary=caption.slice(title.length).trim() || caption;
    body.append(el('strong','schedule-post-title',title));
    body.append(el('span','schedule-post-excerpt',summary.slice(0,150) || 'Sem legenda'));
    body.append(el('small','schedule-post-kind',formatLabel(post.format)));
    target.append(thumb,body);
  }
  function scheduleFeedback(message,kind='error') {
    const target=$('schedule-feedback');
    target.textContent=message;
    target.classList.toggle('schedule-error',kind==='error' && !!message);
    target.setAttribute('role',kind==='error' && message?'alert':'status');
    target.setAttribute('aria-live',kind==='error' && message?'assertive':'polite');
  }
  function saoPauloMinute(date=new Date()) {
    const parts=new Intl.DateTimeFormat('en-US',{
      timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit',
      hour:'2-digit',minute:'2-digit',hourCycle:'h23'
    }).formatToParts(date);
    const part=name=>parts.find(item=>item.type===name)?.value;
    return part('year')+'-'+part('month')+'-'+part('day')+'T'+part('hour')+':'+part('minute');
  }
  function schedulePost(id) {
    const post=state.posts.find(p=>p.id===id);
    if(!post || post.status!=='approved' || post.revision!==post.approvedRevision)return toast('Aprove a revisão atual primeiro.');
    state.pendingSchedule=id;
    renderScheduleSummary(post);
    scheduleFeedback(post.pendingScheduledAt
      ? 'O horário anterior ('+friendlyDate(post.pendingScheduledAt)+') já passou. Informe uma nova data.'
      : '', 'info');
    $('schedule-at').value='';
    UI.dialog.open($('schedule-dialog'));
  }
  async function submitSchedule(event) {
    event.preventDefault();
    const post=state.posts.find(p=>p.id===state.pendingSchedule);
    if(!post || post.status!=='approved' || post.revision!==post.approvedRevision){
      scheduleFeedback('Esta publicação mudou. Feche esta janela e abra Agendar novamente.');
      return;
    }
    const val=$('schedule-at').value;
    if(!/^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(val)){
      scheduleFeedback('Informe uma data e um horário válidos.');
      return;
    }
    if(val<=saoPauloMinute()){
      scheduleFeedback('A data e o horário escolhidos já passaram. Selecione um horário futuro para agendar.');
      return;
    }
    if(state.busy)return;
    state.busy=true;
    const submit=$('schedule-form').querySelector('button[type="submit"]');
    const release=UI.hold(submit,'Agendando…');
    scheduleFeedback('Conferindo o acesso e confirmando o agendamento…','info');
    try{
      await api('posts/'+post.id+'/schedule',{action:'schedule',data:{version:post.version,localTime:val}});
    }catch(error){
      if(error.status===422 && /Data deve ser futura/i.test(error.message)){
        scheduleFeedback('A data e o horário escolhidos já passaram. Selecione um horário futuro para agendar.');
      }else if(error.status===409){
        scheduleFeedback('Esta publicação foi alterada em outra aba. Feche esta janela e tente agendar a versão atual.');
      }else if(error.status===403){
        scheduleFeedback('Sua sessão expirou. Entre novamente para continuar.');
      }else if(error.unexpectedResponse){
        scheduleFeedback('Não foi possível confirmar o agendamento. O servidor respondeu de forma inesperada. Tente novamente.');
      }else{
        scheduleFeedback('Não foi possível agendar. '+(error.message || 'Verifique a data e tente novamente.'));
      }
      return; // Keep the modal, selected post and entered date visible on errors.
    }finally{
      state.busy=false;release();
    }
    UI.dialog.close($('schedule-dialog'));state.pendingSchedule=null;
    await refresh();toast('Envio agendado para @'+state.accountUsername+'. Mantenha a Central ligada.');
    show('calendar');
  }
  function confirmPublication(post,action) {
    state.pendingPublish={id:post.id,version:post.version,action};
    renderScheduleSummary(post,'publish-post-preview');
    $('publish-account').textContent='Conta de destino: @'+state.accountUsername;
    $('publish-explanation').textContent=action==='activate'
      ? 'Este conteúdo será enviado no horário agendado após sua confirmação.'
      : 'Este conteúdo será enviado agora ao Instagram após sua confirmação.';
    $('publish-feedback').textContent='';$('confirm-publish').disabled=false;
    UI.dialog.open($('publish-dialog'));
  }
  async function submitPublication() {
    if(state.busy || !state.pendingPublish)return;
    state.busy=true;const release=UI.hold($('confirm-publish'),'Preparando envio…');
    $('publish-feedback').textContent='Conferindo o acesso e preparando o envio…';
    const pending=state.pendingPublish;
    try{
      await api('posts/'+pending.id+'/'+pending.action,{action:pending.action,data:{version:pending.version}});
      UI.dialog.close($('publish-dialog'));state.pendingPublish=null;
      await refresh();toast(pending.action==='activate'?'Envio agendado confirmado.':'Publicação recebida para envio. Acompanhe o resultado nesta tela.');
    }catch(error){$('publish-feedback').textContent=error.message || 'Não foi possível preparar o envio.';}
    finally{state.busy=false;release();}
  }
  async function recoverPost(post,action) {
    const data={version:post.version};
    if(action==='retry'){
      if(!window.confirm('Confira o perfil @'+state.accountUsername+' no Instagram. Você confirma que este conteúdo NÃO foi publicado e quer liberar outra tentativa com o mesmo contêiner?'))return;
      data.confirmNotPublished=true;
    }
    await api('posts/'+post.id+'/'+action,{action,data});await refresh();
    toast(action==='reset'?'Conteúdo liberado para edição.':'Verificação solicitada. Acompanhe o resultado.');
  }
  async function checkPublication() {
    await api('publication/check',{action:'check',data:{}});await refresh();
    toast(state.publication.ready?'Verificação concluída: acesso de publicação confirmado.'
      :'Verificação concluída: '+state.publication.message,state.publication.ready?'success':'error');
  }
  const bytesLabel=value=>new Intl.NumberFormat('pt-BR',{maximumFractionDigits:1}).format(value/1024/1024)+' MB';
  function requestDeletion(kind,item){
    if(state.busy || state.actionPending)return UI.announce('Aguarde a conclusão da operação atual.');
    state.pendingDelete={kind,id:item.id,version:item.version};
    $('delete-title').textContent=kind==='post'?'Excluir publicação local':'Excluir mídia da biblioteca';
    $('delete-description').textContent=kind==='post'
      ? 'Conta @'+state.accountUsername+' · '+(postText(item).slice(0,120) || 'Publicação sem legenda')
      : 'Conta @'+state.accountUsername+' · '+item.name+' · '+bytesLabel(item.size);
    $('delete-consequence').textContent=kind==='media'
      ? 'O arquivo será apagado do armazenamento da Central. Esta ação não pode ser desfeita.'
      : (item.status==='scheduled'?'O agendamento será cancelado. ':'')+
        'O registro será apagado da Central. Conteúdo já publicado no Instagram permanece lá. Esta ação não pode ser desfeita.';
    $('delete-media-option').hidden=kind!=='post';$('delete-unused-media').checked=true;
    $('delete-feedback').textContent='';UI.dialog.open($('delete-dialog'));
  }
  async function submitDeletion(){
    if(state.busy || state.actionPending || !state.pendingDelete)return;
    const pending=state.pendingDelete;state.busy=true;
    const release=UI.hold($('confirm-delete'),'Excluindo…');
    $('delete-feedback').textContent='Excluindo da conta selecionada…';
    try{
      const action=pending.kind==='post'?'delete_post':'delete_media';
      const data=pending.kind==='post'?{version:pending.version,deleteUnusedMedia:$('delete-unused-media').checked}:{mediaId:pending.id};
      const result=await api(pending.kind==='post'?'posts/'+pending.id+'/delete':'drafts',{action,data});
      if(pending.kind==='post' && state.currentPostId===pending.id){state.currentPostId=null;state.currentPostVersion=null;}
      await refresh();state.currentMediaIds=state.currentMediaIds.filter(id=>state.media.some(m=>m.id===id));state.editorPreviewKey=null;
      UI.dialog.close($('delete-dialog'));state.pendingDelete=null;
      toast('Exclusão concluída. '+(result.deletedMedia || 0)+' mídia(s) removida(s); '+bytesLabel(result.freedBytes || 0)+' liberados.'+
        (result.keptMedia?' '+result.keptMedia+' mídia(s) preservada(s) por uso em outra publicação.':'')+
        (result.pendingBytes?' Limpeza de '+bytesLabel(result.pendingBytes)+' pendente; será retomada ao abrir a conta.':''));
    }catch(error){$('delete-feedback').textContent=error.message || 'Não foi possível confirmar a exclusão. Atualize e confira os dados.';}
    finally{state.busy=false;release();}
  }
  async function cancelSchedule(id) {
    const post=state.posts.find(p=>p.id===id);
    if(!post || post.status!=='scheduled')return;
    await api('posts/'+id+'/cancel',{action:'cancel',data:{version:post.version}});
    await refresh();toast('Agendamento cancelado.');
  }
  function renderCalendar() {
    const start=new Date(Date.UTC(state.month.getUTCFullYear(),state.month.getUTCMonth(),1));
    $('month-label').textContent=formatMonth(start);
    const target=$('calendar-grid');clear(target);
    const firstWeekday=start.getUTCDay();
    const monthDays=new Date(Date.UTC(start.getUTCFullYear(),start.getUTCMonth()+1,0)).getUTCDate();
    const cells=Math.ceil((firstWeekday+monthDays)/7)*7;
    const today=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    for(let index=0;index<cells;index++){
      const date=new Date(Date.UTC(start.getUTCFullYear(),start.getUTCMonth(),index-firstWeekday+1));
      const iso=date.toISOString().slice(0,10);
      const outside=date.getUTCMonth()!==start.getUTCMonth();
      const cell=el('div','calendar-day'+(outside?' outside':'')+(iso===today?' today':''));
      cell.append(el('span','day-number',date.getUTCDate()));
      const events=state.posts.filter(p=>calendarTime(p) &&
        (p.status==='scheduled' || pendingApproval(p) || expiredReservation(p)) &&
        new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(calendarTime(p)))===iso);
      events.forEach(post=>{
        const summary=postText(post);
        const needsReview=pendingApproval(post),expired=expiredReservation(post);
        const prefix=needsReview?'Aprovação pendente':expired?'Horário expirado':formatLabel(post.format);
        const text=el('div','calendar-event'+(needsReview?' awaiting-review':expired?' expired-review':''),
          prefix+' · '+(summary.slice(0,15)||'Sem legenda'));
        text.title=prefix+' · '+summary;
        if(needsReview){
          text.setAttribute('role','button');text.tabIndex=0;
          text.setAttribute('aria-label','Ver publicação aguardando aprovação: '+summary.slice(0,60));
          const focusItem=()=>document.getElementById('calendar-post-'+post.id)?.scrollIntoView({block:'nearest'});
          text.addEventListener('click',focusItem);
          text.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();focusItem();}});
        }
        cell.append(text);
      });
      target.append(cell);
    }
    const list=$('calendar-list');clear(list);
    const scheduled=state.posts.filter(p=>
      p.status==='scheduled' || pendingApproval(p) || expiredReservation(p))
      .sort((a,b)=>calendarTime(a)-calendarTime(b));
    if(!scheduled.length)return empty(list,'Nenhuma publicação agendada.');
    scheduled.forEach(p=>{
      const row=postRow(p,{approval:true});
      row.id='calendar-post-'+p.id;
      list.append(row);
    });
  }
  function wireEvents() {
    $('confirm-delete').addEventListener('click',submitDeletion);
    ['close-delete-dialog','cancel-delete'].forEach(id=>$(id).addEventListener('click',()=>{if(!state.busy)UI.dialog.close($('delete-dialog'));}));
    $('check-publication').addEventListener('click',()=>guard(checkPublication));
    $('confirm-publish').addEventListener('click',submitPublication);
    $('close-publish-dialog').addEventListener('click',()=>{if(!state.busy)UI.dialog.close($('publish-dialog'));});
    all('[data-view]').forEach(node=>node.addEventListener('click',()=>{
      if(state.actionPending || state.busy)return UI.announce('Aguarde a conclusão da operação atual.');
      if(node.dataset.view==='editor')newDraft();else show(node.dataset.view);
    }));
    all('[data-goto]').forEach(node=>node.addEventListener('click',()=>show(node.dataset.goto)));
    all('[data-new-format]').forEach(node=>node.addEventListener('click',()=>newDraft(node.dataset.newFormat)));
    $('new-post').addEventListener('click',()=>newDraft());
    $('clear-editor').addEventListener('click',()=>newDraft());
    $('post-format').addEventListener('change',()=>{state.currentPreviewIndex=0;formatHint();renderSelection();});
    $('post-caption').addEventListener('input',renderSelection);
    all('input[name="caption-mode"]').forEach(node=>node.addEventListener('change',()=>{state.currentPreviewIndex=0;renderSelection();}));
    $('save-draft').addEventListener('click',()=>guard(()=>savePost(false)));
    $('post-form').addEventListener('submit',e=>{e.preventDefault();guard(()=>savePost(true));});
    $('upload-trigger').addEventListener('click',()=>$('media-input').click());
    $('media-input').addEventListener('change',e=>guard(async()=>{await uploadFiles(e.target.files);e.target.value='';}));
    $('open-library-picker').addEventListener('click',()=>{state.pickerIds=[...state.currentMediaIds];renderPicker();UI.dialog.open($('media-dialog'));});
    $('close-media-dialog').addEventListener('click',()=>UI.dialog.close($('media-dialog')));
    $('apply-media-selection').addEventListener('click',()=>{state.currentMediaIds=[...state.pickerIds];state.currentPreviewIndex=0;UI.dialog.close($('media-dialog'));renderSelection();});
    $('close-preview-dialog').addEventListener('click',()=>UI.dialog.close($('preview-dialog')));
    $('preview-dialog').addEventListener('click',event=>{if(event.target===$('preview-dialog'))UI.dialog.close($('preview-dialog'));});
    $('preview-dialog').addEventListener('close',()=>{state.modalPostId=null;});
    $('close-schedule-dialog').addEventListener('click',()=>{if(!state.busy)UI.dialog.close($('schedule-dialog'));});
    $('schedule-form').addEventListener('submit',e=>{e.preventDefault();guard(()=>submitSchedule(e));});
    $('refresh-content').addEventListener('click',()=>guard(async()=>{
      const operation=UI.start('Atualizando o conteúdo desta conta…');
      try{await refresh();render();toast('Conteúdo atualizado.');}finally{operation.end();}
    }));
    $('prev-month').addEventListener('click',()=>{state.month=new Date(Date.UTC(state.month.getUTCFullYear(),state.month.getUTCMonth()-1,1));renderCalendar();});
    $('next-month').addEventListener('click',()=>{state.month=new Date(Date.UTC(state.month.getUTCFullYear(),state.month.getUTCMonth()+1,1));renderCalendar();});
  }
  async function guard(action) {
    if(state.actionPending || state.busy)return UI.announce('Aguarde a conclusão da operação atual.');
    state.actionPending=true;
    const button=document.activeElement;
    const label=({'check-publication':'Verificando…','refresh-content':'Atualizando…','save-draft':'Salvando…','upload-trigger':'Enviando…'})[button?.id] || 'Processando…';
    const release=UI.hold(button,label);
    try {await action();} catch(err) {
      console.error('Erro no laboratório editorial:',err?.name || 'Error');
      if(err?.status===409 && state.view==='editor' && state.currentPostId){
        draftConflictFeedback();
        return; // Do not replace unsaved text or imply a successful save.
      }
      if(state.view==='editor')actionErrorFeedback('form-feedback',err);
      else if(state.view==='library')actionErrorFeedback('library-feedback',err);
      toast(err.unexpectedResponse
        ? 'O servidor respondeu de forma inesperada. Operação não confirmada.'
        : (err.message || 'Não foi possível concluir a operação.'),'error');
      try {await refresh();} catch (_) { /* keep the error visible */ }
    }finally{state.actionPending=false;release();}
  }
  async function init() {
    wireEvents();
    const initial=location.hash.slice(1);
    if(['overview','library','editor','approval','calendar'].includes(initial))state.view=initial;
    const load=async()=>{await refresh();formatHint();show(state.view);UI.ready();};
    try{
      await load();
    }catch(err){UI.initialError(load);}
    setInterval(()=>{
        if(document.visibilityState==='visible' && !state.busy &&
           !state.actionPending && !document.body.dataset.uiLoading &&
           state.posts.some(post=>post.status==='publishing' || (post.status==='scheduled' && post.publishAuthorized))){
          refresh().catch(()=>{ $('publication-status').textContent='Não foi possível atualizar o resultado. Recarregue para conferir antes de tentar outro envio.'; });
        }
    },10000);
  }
  document.addEventListener('DOMContentLoaded',init,{once:true});
})();
