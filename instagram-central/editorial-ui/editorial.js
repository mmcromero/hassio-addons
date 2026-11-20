/* Central Instagram: Editorial persistente, mesma sessão administrativa. */
(() => {
  'use strict';
  const MAX_UPLOAD = 25 * 1024 * 1024;
  const FORMATS = {feed:'Publicação',carousel:'Carrossel',story:'Story',reel:'Reel'};
  const STATUS = {draft:'Aguardando aprovação',approved:'Aprovada',scheduled:'Agendada',leased:'Em processamento',needs_review:'Revisão necessária'};
  const state = {
    view:'overview', posts:[], media:[], currentPostId:null, currentPostVersion:null, currentMediaIds:[],
    pickerIds:[], month:new Date(), pendingSchedule:null, toastTimer:null,
    currentSlideCaptions:{}, currentPreviewIndex:0, modalPostId:null, modalPreviewIndex:0
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
  const clear = node => node.replaceChildren();

  async function api(path, {action, data, file}={}) {
    const headers = {};
    if(action){
      const tokens = await api('csrf');
      headers['X-CSRF-Token'] = tokens[action];
      headers['Content-Type'] = file ? file.type : 'application/json';
    }
    const response = await fetch('api/'+path, {
      method:action ? 'POST' : 'GET', credentials:'same-origin', cache:'no-store',
      headers, body:action ? (file || JSON.stringify(data)) : undefined
    });
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
  }
  async function refresh() {
    const result = await api('state');
    state.posts=result.posts;state.media=result.media;
    render();
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
      +'Copie o texto se precisar e abra a publicação novamente em Aprovações → Editar para usar a versão atual.';
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
    all('[data-panel]').forEach(node=>node.classList.toggle('hidden',node.dataset.panel!==view));
    all('[data-view]').forEach(node=>{
      const active=node.dataset.view===view;
      node.classList.toggle('active',active);
      if (active) node.setAttribute('aria-current','page');else node.removeAttribute('aria-current');
    });
    $('current-section').textContent = ({overview:'Visão geral',library:'Biblioteca',editor:'Criar publicação',approval:'Aprovações',calendar:'Calendário'})[view];
    render();
  }
  function formatHint() {
    const fmt = $('post-format').value;
    $('selection-hint').textContent=({
      feed:'De 1 a 20 imagens JPG ou PNG; 2 ou mais formam um carrossel automaticamente.',
      story:'Uma imagem ou um vídeo.',reel:'Um vídeo MP4.'
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
    state.currentPostId=null;
    state.currentPostVersion=null;
    state.currentMediaIds=[];
    state.currentSlideCaptions={};
    state.currentPreviewIndex=0;
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
    renderUpcoming();
    renderLibrary();
    renderApprovals();
    renderCalendar();
    renderSelection();
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
      media.src=previewUrl(first);
      if(media.tagName==='IMG')media.alt='Miniatura da publicação';
      else{media.muted=true;media.playsInline=true;media.preload='metadata';}
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
      content.append(badge(post.status));
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
    }
    if(options.approval && post.status==='scheduled'){
      const cancel=el('button','btn quiet','Cancelar agenda');cancel.type='button';
      cancel.addEventListener('click',()=>guard(()=>cancelSchedule(post.id)));actions.append(cancel);
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
    const items=state.posts.filter(p=>['draft','approved','scheduled','leased','needs_review'].includes(p.status));
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
    media.src=url;
    if(media.tagName==='IMG')media.alt=item.name;
    else{media.muted=true;media.playsInline=true;media.preload='metadata';}
    monitorMediaLoad(media,visual);
    visual.append(media);node.append(visual);
    const info=el('div','media-card-info');info.append(el('strong','',item.name),el('small','',Math.max(1,Math.round(item.size/1024))+' KB'));
    node.append(info);return node;
  }
  function renderLibrary() {
    const grid=$('media-grid');clear(grid);
    if(!state.media.length)return empty(grid,'Sua biblioteca está vazia. Adicione imagens ou vídeos.');
    state.media.forEach(m=>grid.append(mediaCard(m)));
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
    media.src=previewUrl(item);
    if(media.tagName==='IMG') media.alt='Imagem '+(index+1)+' da publicação';
    else{media.controls=true;media.muted=true;media.playsInline=true;media.preload='metadata';}
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
    $('preview-dialog').showModal();
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
    for(const file of files){
      if(!['image/jpeg','image/png','video/mp4'].includes(file.type) || file.size===0 || file.size>MAX_UPLOAD){skipped++;continue;}
      const bytes=new Uint8Array(await file.slice(0,12).arrayBuffer());
      const valid=file.type==='image/jpeg' ? bytes[0]===255 && bytes[1]===216 && bytes[2]===255
        :file.type==='image/png' ? [137,80,78,71,13,10,26,10].every((v,i)=>bytes[i]===v)
        :bytes.length>=12 && String.fromCharCode(...bytes.slice(4,8))==='ftyp';
      if(!valid){skipped++;continue;}
      await api('media',{action:'upload',file});
      added++;
    }
    await refresh();
    clearOperationFeedback('library-feedback');
    toast(added+' arquivo(s) salvo(s) na biblioteca da Central.'+(skipped?' '+skipped+' ignorado(s) por formato ou tamanho.':''));
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
  function renderScheduleSummary(post) {
    const target=$('schedule-post-preview');clear(target);
    const thumb=el('span','schedule-post-thumb');
    const first=state.media.find(media=>media.id===post.mediaIds?.[0]);
    if(first){
      const media=el(first.type.startsWith('image/')?'img':'video');
      media.src=previewUrl(first);
      if(media.tagName==='IMG')media.alt='Miniatura da publicação selecionada';
      else{media.muted=true;media.playsInline=true;media.preload='metadata';}
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
    $('schedule-dialog').showModal();
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
    scheduleFeedback('');
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
    }
    $('schedule-dialog').close();state.pendingSchedule=null;
    await refresh();toast('Agendamento registrado. Publicação automática permanece desativada.');
    show('calendar');
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
    all('[data-view]').forEach(node=>node.addEventListener('click',()=>show(node.dataset.view)));
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
    $('open-library-picker').addEventListener('click',()=>{state.pickerIds=[...state.currentMediaIds];renderPicker();$('media-dialog').showModal();});
    $('close-media-dialog').addEventListener('click',()=>$('media-dialog').close());
    $('apply-media-selection').addEventListener('click',()=>{state.currentMediaIds=[...state.pickerIds];state.currentPreviewIndex=0;$('media-dialog').close();renderSelection();});
    $('close-preview-dialog').addEventListener('click',()=>$('preview-dialog').close());
    $('preview-dialog').addEventListener('click',event=>{if(event.target===$('preview-dialog'))$('preview-dialog').close();});
    $('preview-dialog').addEventListener('close',()=>{state.modalPostId=null;});
    $('close-schedule-dialog').addEventListener('click',()=>$('schedule-dialog').close());
    $('schedule-form').addEventListener('submit',e=>guard(()=>submitSchedule(e)));
    $('prev-month').addEventListener('click',()=>{state.month=new Date(Date.UTC(state.month.getUTCFullYear(),state.month.getUTCMonth()-1,1));renderCalendar();});
    $('next-month').addEventListener('click',()=>{state.month=new Date(Date.UTC(state.month.getUTCFullYear(),state.month.getUTCMonth()+1,1));renderCalendar();});
  }
  async function guard(action) {
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
    }
  }
  async function init() {
    wireEvents();
    try{await refresh();formatHint();}
    catch(err){
      console.error('Armazenamento editorial indisponível:',err?.name || 'Error');
      toast('Editorial indisponível. Entre novamente na Central e recarregue.');
      all('button').forEach(button=>{if(!button.closest('#editorial-logout') && button.id!=='prev-month' && button.id!=='next-month')button.disabled=true;});
    }
  }
  document.addEventListener('DOMContentLoaded',init,{once:true});
})();
