/* Central Instagram: Editorial persistente, mesma sessão administrativa. */
(() => {
  'use strict';
  const MAX_UPLOAD = 25 * 1024 * 1024;
  const FORMATS = {feed:'Publicação',carousel:'Carrossel',story:'Story',reel:'Reel'};
  const STATUS = {draft:'Aguardando aprovação',approved:'Aprovada',scheduled:'Agendada',leased:'Em processamento',needs_review:'Revisão necessária'};
  const state = {
    view:'overview', posts:[], media:[], currentPostId:null, currentPostVersion:null, currentMediaIds:[],
    pickerIds:[], month:new Date(), pendingSchedule:null, toastTimer:null
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
    const result = await response.json();
    if(!response.ok)throw Error(result.error || 'Operação recusada');
    return result;
  }
  async function refresh() {
    const result = await api('state');
    state.posts=result.posts;state.media=result.media;
    render();
  }
  function toast(message) {
    $('toast').textContent = message;
    $('toast').classList.add('visible');
    if (state.toastTimer) clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(()=>$('toast').classList.remove('visible'),3800);
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
      feed:'Uma imagem JPG ou PNG.',carousel:'De 2 a 20 imagens JPG ou PNG.',
      story:'Uma imagem ou um vídeo.',reel:'Um vídeo MP4.'
    })[fmt];
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
    $('post-format').value=FORMATS[format] ? format : 'feed';
    $('post-caption').value='';
    $('editor-heading').textContent='Nova publicação';
    $('form-feedback').textContent='';
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
    $('post-format').value=post.format;
    $('post-caption').value=post.caption;
    $('editor-heading').textContent='Editar publicação';
    $('form-feedback').textContent='';
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
  function postRow(post, options={}) {
    const row=el('article','item');
    const content=el('div','item-content');
    content.append(el('strong','',post.caption?.trim().slice(0,90) || formatLabel(post.format)));
    content.append(el('small','',formatLabel(post.format)+(post.scheduledAt ? ' · '+friendlyDate(post.scheduledAt) : '')));
    row.append(badge(post.status),content);
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
  function mediaCard(item, selected=false, clickable=false) {
    const node=el(clickable?'button':'div','media-card'+(selected?' selected':''));
    if(clickable)node.type='button';
    const visual=el('div','media-card-visual');
    const url=previewUrl(item);
    const media=el(item.type.startsWith('image/')?'img':'video');
    media.src=url;
    if(media.tagName==='IMG')media.alt=item.name;
    else{media.muted=true;media.playsInline=true;media.preload='metadata';}
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
  function renderSelection(){
    const target=$('selected-media');clear(target);
    const items=selectedMedia();
    if(!items.length)target.append(el('span','','Nenhuma mídia selecionada.'));
    for(const item of items){
      const thumb=el('span','selected-thumb',item.name);
      const remove=el('button','','×');remove.type='button';remove.setAttribute('aria-label','Remover '+item.name);
      remove.addEventListener('click',()=>{
        state.currentMediaIds=state.currentMediaIds.filter(id=>id!==item.id);
        renderSelection();
      });
      thumb.append(remove);target.append(thumb);
    }
    $('caption-count').textContent=$('post-caption').value.length+'/2200';
    const phone=$('phone-media');clear(phone);
    const first=items[0];
    if(first){
      const url=previewUrl(first);
      const preview=el(first.type.startsWith('image/')?'img':'video');
      preview.src=url;
      if(preview.tagName==='IMG')preview.alt=first.name;
      else{preview.controls=true;preview.muted=true;preview.playsInline=true;preview.preload='metadata';}
      phone.append(preview);
    }else phone.append(el('span','','Selecione uma mídia para visualizar'));
    $('preview-caption').textContent=$('post-caption').value.trim() || 'Sua legenda aparece aqui.';
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
    toast(added+' arquivo(s) salvo(s) na biblioteca da Central.'+(skipped?' '+skipped+' ignorado(s) por formato ou tamanho.':''));
  }
  async function savePost(navigate=false) {
    const format=$('post-format').value,caption=$('post-caption').value.trim(),media=selectedMedia();
    if(!FORMATS[format] || caption.length>2200){$('form-feedback').textContent='Confira o formato e a legenda.';return;}
    if(!mediaValid(format,media)){
      $('form-feedback').textContent='Selecione mídias compatíveis com o formato. '+$('selection-hint').textContent;return;
    }
    const current=state.posts.find(p=>p.id===state.currentPostId);
    if(current && !['draft','approved','scheduled'].includes(current.status)){
      $('form-feedback').textContent='Esta publicação não pode ser editada.';return;
    }
    const changed=!current || current.format!==format || current.caption!==caption ||
      JSON.stringify(current.mediaIds)!==JSON.stringify(state.currentMediaIds);
    if(current && !changed){toast('Conteúdo sem alterações.');if(navigate)show('approval');return;}
    const data={format,caption,mediaIds:[...state.currentMediaIds]};
    if(current){data.id=current.id;data.version=state.currentPostVersion;}
    const saved=await api('drafts',{action:'draft',data});
    state.currentPostId=saved.id;
    $('form-feedback').textContent='';
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
    await refresh();toast('Publicação aprovada. Nenhum envio foi realizado.');
  }
  function schedulePost(id) {
    const post=state.posts.find(p=>p.id===id);
    if(!post || post.status!=='approved' || post.revision!==post.approvedRevision)return toast('Aprove a revisão atual primeiro.');
    state.pendingSchedule=id;
    $('schedule-feedback').textContent='';
    $('schedule-at').value='';
    $('schedule-dialog').showModal();
  }
  async function submitSchedule(event) {
    event.preventDefault();
    const post=state.posts.find(p=>p.id===state.pendingSchedule);
    if(!post || post.status!=='approved' || post.revision!==post.approvedRevision)return;
    const val=$('schedule-at').value;
    if(!/^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(val)){$('schedule-feedback').textContent='Informe uma data e um horário válidos.';return;}
    await api('posts/'+post.id+'/schedule',{action:'schedule',data:{version:post.version,localTime:val}});
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
      const events=state.posts.filter(p=>p.status==='scheduled' && p.scheduledAt &&
        new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(p.scheduledAt))===iso);
      events.forEach(post=>{
        const text=el('div','calendar-event',formatLabel(post.format)+' · '+(post.caption.slice(0,15)||'Sem legenda'));
        text.title=post.caption;cell.append(text);
      });
      target.append(cell);
    }
    const list=$('calendar-list');clear(list);
    const scheduled=state.posts.filter(p=>p.status==='scheduled').sort((a,b)=>a.scheduledAt-b.scheduledAt);
    if(!scheduled.length)return empty(list,'Nenhuma publicação agendada.');
    scheduled.forEach(p=>list.append(postRow(p,{approval:true})));
  }
  function wireEvents() {
    all('[data-view]').forEach(node=>node.addEventListener('click',()=>show(node.dataset.view)));
    all('[data-goto]').forEach(node=>node.addEventListener('click',()=>show(node.dataset.goto)));
    all('[data-new-format]').forEach(node=>node.addEventListener('click',()=>newDraft(node.dataset.newFormat)));
    $('new-post').addEventListener('click',()=>newDraft());
    $('clear-editor').addEventListener('click',()=>newDraft());
    $('post-format').addEventListener('change',()=>{formatHint();renderSelection();});
    $('post-caption').addEventListener('input',renderSelection);
    $('save-draft').addEventListener('click',()=>guard(()=>savePost(false)));
    $('post-form').addEventListener('submit',e=>{e.preventDefault();guard(()=>savePost(true));});
    $('upload-trigger').addEventListener('click',()=>$('media-input').click());
    $('media-input').addEventListener('change',e=>guard(async()=>{await uploadFiles(e.target.files);e.target.value='';}));
    $('open-library-picker').addEventListener('click',()=>{state.pickerIds=[...state.currentMediaIds];renderPicker();$('media-dialog').showModal();});
    $('close-media-dialog').addEventListener('click',()=>$('media-dialog').close());
    $('apply-media-selection').addEventListener('click',()=>{state.currentMediaIds=[...state.pickerIds];$('media-dialog').close();renderSelection();});
    $('close-schedule-dialog').addEventListener('click',()=>$('schedule-dialog').close());
    $('schedule-form').addEventListener('submit',e=>guard(()=>submitSchedule(e)));
    $('prev-month').addEventListener('click',()=>{state.month=new Date(Date.UTC(state.month.getUTCFullYear(),state.month.getUTCMonth()-1,1));renderCalendar();});
    $('next-month').addEventListener('click',()=>{state.month=new Date(Date.UTC(state.month.getUTCFullYear(),state.month.getUTCMonth()+1,1));renderCalendar();});
  }
  async function guard(action) {
    try {await action();} catch(err) {
      console.error('Erro no laboratório editorial:',err?.name || 'Error');
      toast(err.message || 'Não foi possível concluir a operação. Entre novamente na Central.');
      try {await refresh();} catch (_) { /* keep the error visible */ }
    }
  }
  async function init() {
    wireEvents();
    try{await refresh();formatHint();}
    catch(err){
      console.error('Armazenamento editorial indisponível:',err?.name || 'Error');
      toast('Editorial indisponível. Entre novamente na Central e recarregue.');
      all('button').forEach(button=>{if(button.id!=='prev-month' && button.id!=='next-month')button.disabled=true;});
    }
  }
  document.addEventListener('DOMContentLoaded',init,{once:true});
})();
