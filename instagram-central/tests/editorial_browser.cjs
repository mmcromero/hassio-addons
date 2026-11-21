/* Local Chromium regression. Uses installed Playwright/Chromium; installs nothing. */
const {chromium} = require('playwright');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline');
const assert = require('node:assert/strict');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ig-browser-'));
const evidence = process.env.IG_EVIDENCE_DIR || path.resolve(__dirname, '../../docs/evidence');
fs.mkdirSync(evidence,{recursive:true});
let child, browser;
async function start(){
  child=spawn(process.env.PYTHON || 'python', [path.join(__dirname,'browser_fixture.py'),root],{stdio:['ignore','pipe','inherit']});
  const lines=readline.createInterface({input:child.stdout});
  const data=await Promise.race([
    new Promise((resolve,reject)=>{lines.once('line',line=>{try{resolve(JSON.parse(line));}catch(e){reject(e);}});child.once('exit',code=>reject(Error('Fixture exited '+code)));}),
    new Promise((_,reject)=>setTimeout(()=>reject(Error('Fixture startup timed out')),10000).unref())
  ]);
  lines.close();return data.url;
}
async function stop(){
  if(child && child.exitCode===null){const done=new Promise(resolve=>child.once('exit',resolve));child.kill('SIGTERM');await done;}
}
(async()=>{
  const url=await start();
  browser=await chromium.launch({executablePath:process.env.CHROMIUM || '/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1440,height:1000},timezoneId:'America/Sao_Paulo'});
  const errors=[], blocked=[];
  let injectedScheduleUrl=null;
  await context.route('**/*',route=>{
    const requested=new URL(route.request().url());
    if(requested.origin!==url){blocked.push(requested.origin);return route.abort();}
    return route.continue();
  });
  const page=await context.newPage();
  page.on('pageerror',error=>errors.push({message:error.message,url:'pageerror'}));
  page.on('console',message=>{if(message.type()==='error')errors.push({message:message.text(),url:message.location().url});});
  await page.goto(url+'/');
  await page.getByLabel('Senha').fill('browser_fixture_password_only_123');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await page.getByRole('cell',{name:'Mensagem sintética para regressão',exact:true}).waitFor();
  assert.equal(await page.locator('.sidebar').count(),1,'Messages must share Editorial sidebar');
  assert.equal(await page.locator('.topbar').count(),1,'Messages must share Editorial header');
  assert.equal(await page.getByRole('button',{name:'Sair',exact:true}).count(),1);
  await page.screenshot({path:path.join(evidence,'ig-mensagens-desktop.png'),fullPage:true});
  await page.getByRole('button',{name:'Assumir',exact:true}).click();
  await page.getByRole('cell',{name:'human',exact:true}).waitFor();
  await page.getByRole('link',{name:'Editorial',exact:true}).click();
  await page.locator('#count-all').filter({hasText:'0'}).waitFor();
  const response=page.waitForResponse(r=>r.url().endsWith('/api/state'));
  await page.locator('[data-view="library"]').click();
  const image=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAAHUlEQVR4nGNMaljDQC5gIlvnqOZRzaOaRzVTRTMAyc8BtjG4iWEAAAAASUVORK5CYII=','base64');
  await page.locator('#media-input').setInputFiles({name:'synthetic.png',mimeType:'image/png',buffer:image});
  await response;
  await page.locator('#media-grid img').waitFor();
  assert.equal(await page.locator('#media-grid img').evaluate(img=>img.complete && img.naturalWidth>0),true);
  // H11 diagnostic: failed media playback/thumbnail must be explained near the media,
  // even if the HTTP reason (session/proxy/decoder) cannot be inferred.
  await page.locator('#media-grid img').first().evaluate(media=>media.dispatchEvent(new Event('error')));
  await page.locator('#media-grid .media-load-failed').waitFor({state:'visible'});
  assert.match(await page.locator('#media-grid .media-load-failed').innerText(),/Atualize a página/);
  await page.getByRole('button',{name:'+ Nova publicação',exact:true}).click();
  await page.locator('#post-caption').fill('Conteúdo sintético — revisão local');
  await page.locator('#open-library-picker').click();
  await page.locator('#picker-grid button').click();
  await page.locator('#apply-media-selection').click();
  await page.getByRole('button',{name:'Salvar e revisar',exact:true}).click();
  await page.locator('#view-approval').waitFor({state:'visible'});
  await page.getByRole('button',{name:'Aprovar',exact:true}).waitFor();
  await page.getByRole('button',{name:'Aprovar',exact:true}).click();
  await page.getByRole('button',{name:'Agendar',exact:true}).click();
  // H10: contextual schedule modal and visible, persistent error next to confirmation.
  const scheduleDialog=page.locator('#schedule-dialog');
  assert.equal(await scheduleDialog.locator('.schedule-post-preview').count(),1);
  assert.match(await scheduleDialog.locator('.schedule-post-title').innerText(),/Conteúdo sintético/);
  assert.match(await scheduleDialog.locator('.schedule-post-excerpt').innerText(),/Conteúdo sintético/);
  assert.equal(await scheduleDialog.locator('.schedule-post-thumb img').count(),1);
  assert.equal(await scheduleDialog.locator('.schedule-post-kind').innerText(),'Publicação');
  const yesterday=new Date(Date.now()-86400000).toISOString().slice(0,10)+'T12:00';
  await page.locator('#schedule-at').fill(yesterday);
  await page.getByRole('button',{name:'Confirmar agenda',exact:true}).click();
  const dateError=scheduleDialog.locator('#schedule-feedback[role="alert"]');
  await dateError.waitFor({state:'visible'});
  assert.match(await dateError.innerText(),/já passaram/);
  assert.equal(await dateError.evaluate(el=>el.nextElementSibling?.querySelector('button')?.textContent.trim()),'Confirmar agenda');
  assert.equal(await scheduleDialog.isVisible(),true);
  assert.equal(await page.locator('#schedule-at').inputValue(),yesterday);
  const beforeScheduling=await page.evaluate(async()=> (await(await fetch('./api/state')).json()).posts[0]);
  assert.equal(beforeScheduling.status,'approved');
  assert.equal(beforeScheduling.scheduledAt,null);
  const future=new Date(Date.now()+2*86400000).toISOString().slice(0,10)+'T09:30';
  await page.locator('#schedule-at').fill(future);
  // A reverse proxy may return an HTML error rather than JSON; do not display parser text.
  const schedulePattern='**/editorial/api/posts/*/schedule';
  await page.route(schedulePattern,route=>{injectedScheduleUrl=route.request().url();return route.fulfill({
    status:502,contentType:'text/html',body:'502 Bad Gateway'
  });});
  await page.getByRole('button',{name:'Confirmar agenda',exact:true}).click();
  await dateError.waitFor({state:'visible'});
  assert.match(await dateError.innerText(),/servidor respondeu de forma inesperada/);
  assert.equal(await scheduleDialog.isVisible(),true);
  assert.equal(await page.locator('#schedule-at').inputValue(),future);
  await page.screenshot({path:path.join(evidence,'ig-schedule-context-inline-error.png')});
  await page.unroute(schedulePattern);
  await page.getByRole('button',{name:'Confirmar agenda',exact:true}).click();
  await page.locator('#view-calendar').waitFor({state:'visible'});
  await page.getByRole('button',{name:'Cancelar agenda',exact:true}).waitFor();
  await page.screenshot({path:path.join(evidence,'ig-editorial-desktop.png'),fullPage:true});
  await page.reload();
  await page.locator('#count-scheduled').filter({hasText:'1'}).waitFor();
  await page.locator('[data-view="approval"]').click();
  await page.getByRole('button',{name:'Cancelar agenda',exact:true}).click();
  await page.getByRole('button',{name:'Agendar',exact:true}).waitFor();
  await page.getByRole('button',{name:'Editar',exact:true}).click();
  await page.locator('#post-caption').fill('Conteúdo sintético editado');
  await page.getByRole('button',{name:'Salvar e revisar',exact:true}).click();
  await page.locator('#view-approval').waitFor({state:'visible'});
  await page.getByRole('button',{name:'Aprovar',exact:true}).waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(evidence,'ig-editorial-mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Editorial mobile overflows viewport');
  await page.getByRole('link',{name:'← Mensagens e conexão',exact:true}).click();
  await page.getByRole('cell',{name:'Mensagem sintética para regressão',exact:true}).waitFor();
  await page.getByRole('cell',{name:'human',exact:true}).waitFor();
  // Restart process against the same temporary volume; persisted cookie/data remain usable.
  await stop();const restarted=await start();
  const cookies=await context.cookies();
  await context.unroute('**/*');
  await context.route('**/*',route=>new URL(route.request().url()).origin===restarted ? route.continue() : route.abort());
  await context.addCookies(cookies.map(c=>({...c,domain:'127.0.0.1'})));
  await page.goto(restarted+'/editorial/');
  await page.locator('#count-all').filter({hasText:'1'}).waitFor();
  await page.locator('#count-draft').filter({hasText:'1'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Sair',exact:true}).count(),1);
  // H07 regression: the Editorial header logs out using the existing shared session.
  await page.getByRole('button',{name:'Sair',exact:true}).click();
  await page.getByRole('button',{name:'Entrar',exact:true}).waitFor();
  assert.equal((await context.request.get(restarted+'/editorial/api/state')).status(),403);
  // New private 0.1.8 regression: local carousel captions, navigation, and read-only modal.
  await page.getByLabel('Senha').fill('browser_fixture_password_only_123');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await page.getByRole('link',{name:'Editorial',exact:true}).click();
  await page.locator('[data-view="library"]').click();
  const image2=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAAHUlEQVR4nGNMaljDQC5gIlvnqOZRzaOaRzVTRTMAyc8BtjG4iWEAAAAASUVORK5CYII=','base64');
  await page.locator('#media-input').setInputFiles({name:'synthetic-2.png',mimeType:'image/png',buffer:image2});
  await page.locator('#media-grid .media-card').nth(1).waitFor();
  assert.equal(await page.locator('#media-grid .media-card').count(),2);
  await page.getByRole('button',{name:'+ Nova publicação',exact:true}).click();
  assert.equal(await page.locator('#post-format option[value="carousel"]').count(),0);
  await page.locator('#open-library-picker').click();
  const mediaCards=page.locator('#picker-grid button');
  await mediaCards.nth(0).click();
  await page.locator('#picker-grid button').nth(1).click();
  await page.getByRole('button',{name:'Usar mídias selecionadas'}).click();
  await page.locator('#carousel-caption-options').waitFor({state:'visible'});
  await page.locator('input[name="caption-mode"][value="per_slide"]').check();
  await page.locator('.slide-caption-input').nth(0).fill('Primeira legenda individual');
  await page.locator('.slide-caption-input').nth(1).fill('Segunda legenda individual');
  await page.locator('#phone-media').getByRole('button',{name:'Próxima imagem'}).click();
  assert.match(await page.locator('#preview-caption').innerText(),/Segunda legenda individual/);
  assert.match(await page.locator('#phone-media').innerText(),/2 \/ 2/);
  await page.getByRole('button',{name:'Salvar e revisar',exact:true}).click();
  await page.locator('#view-approval').waitFor({state:'visible'});
  const targetRow=page.locator('#approval-list .item').filter({hasText:'Primeira legenda individual'});
  await targetRow.waitFor();
  assert.equal(await targetRow.locator('.post-preview-thumb').count(),1);
  assert.equal(await targetRow.locator('.item-content .chip').count(),1);
  assert.equal(await targetRow.getByRole('button',{name:'Editar',exact:true}).count(),1);
  assert.equal(await targetRow.getByRole('button',{name:'Aprovar',exact:true}).count(),1);
  await targetRow.locator('.post-preview-trigger').click();
  const previewDialog=page.locator('#preview-dialog');
  await previewDialog.waitFor({state:'visible'});
  assert.equal(await previewDialog.getByRole('button',{name:'Editar'}).count(),0);
  assert.equal(await previewDialog.getByRole('button',{name:'Aprovar'}).count(),0);
  await previewDialog.getByRole('button',{name:'Próxima imagem'}).click();
  assert.match(await previewDialog.locator('#modal-preview-caption').innerText(),/Segunda legenda individual/);
  await page.screenshot({path:path.join(evidence,'ig-editorial-preview-modal-desktop.png')});
  await previewDialog.getByRole('button',{name:'Fechar visualização'}).click();
  // H02 regression: calendar reservation remains visible and approvable after editing.
  await targetRow.getByRole('button',{name:'Aprovar',exact:true}).click();
  await targetRow.getByRole('button',{name:'Agendar',exact:true}).click();
  const reservedLocal=new Date(Date.now()+4*86400000).toISOString().slice(0,10)+'T12:30';
  await page.locator('#schedule-at').fill(reservedLocal);
  await page.getByRole('button',{name:'Confirmar agenda',exact:true}).click();
  await page.locator('#calendar-list .item').filter({hasText:'Primeira legenda individual'}).waitFor();
  const beforeEdit=await page.evaluate(async()=> (await(await fetch('./api/state')).json()).posts.find(p=>p.captionMode==='per_slide'));
  assert(beforeEdit.scheduledAt,'Expected active scheduled publication');
  await page.locator('#calendar-list .item').filter({hasText:'Primeira legenda individual'})
    .getByRole('button',{name:'Editar',exact:true}).click();
  await page.locator('.slide-caption-input').nth(1).fill('Segunda legenda revisada');
  await page.getByRole('button',{name:'Salvar e revisar',exact:true}).click();
  await page.locator('#view-approval').waitFor({state:'visible'});
  await page.locator('[data-view="calendar"]').click();
  const pendingCalendar=page.locator('#calendar-list .item.pending-review');
  await pendingCalendar.waitFor();
  assert.match(await pendingCalendar.innerText(),/Aguardando nova aprovação/);
  assert.equal(await pendingCalendar.getByRole('button',{name:'Aprovar',exact:true}).count(),1);
  if(await page.locator('.calendar-event.awaiting-review').count()===0)
    await page.locator('#next-month').click();
  assert.equal(await page.locator('.calendar-event.awaiting-review').count(),1);
  const awaiting=await page.evaluate(async()=> (await(await fetch('./api/state')).json()).posts.find(p=>p.captionMode==='per_slide'));
  assert.equal(awaiting.status,'draft');
  assert.equal(awaiting.scheduledAt,null);
  assert.equal(awaiting.pendingScheduledAt,beforeEdit.scheduledAt);
  const reapproved=page.waitForResponse(r=>r.url().includes('/api/posts/') && r.url().endsWith('/approve') && r.request().method()==='POST');
  await pendingCalendar.getByRole('button',{name:'Aprovar',exact:true}).click();
  assert.equal((await reapproved).status(),200);
  await pendingCalendar.waitFor({state:'hidden'});
  const restored=await page.evaluate(async()=> (await(await fetch('./api/state')).json()).posts.find(p=>p.captionMode==='per_slide'));
  assert.equal(restored.status,'scheduled');
  assert.equal(restored.scheduledAt,beforeEdit.scheduledAt);
  assert.equal(restored.pendingScheduledAt,null);
  assert.equal(await page.locator('#calendar-list .item.pending-review').count(),0);
  const cancelling=page.waitForResponse(r=>r.url().includes('/api/posts/') && r.url().endsWith('/cancel') && r.request().method()==='POST');
  await page.locator('#calendar-list .item').filter({hasText:'Primeira legenda individual'})
    .getByRole('button',{name:'Cancelar agenda',exact:true}).click();
  assert.equal((await cancelling).status(),200);
  const cancelled=await page.evaluate(async()=> (await(await fetch('./api/state')).json()).posts.find(p=>p.captionMode==='per_slide'));
  assert.equal(cancelled.status,'approved');
  assert.equal(cancelled.scheduledAt,null);
  assert.equal(cancelled.pendingScheduledAt,null);
  await page.reload();
  await page.locator('[data-view="approval"]').click();
  await page.locator('#approval-list .item').filter({hasText:'Primeira legenda individual'}).waitFor();
  const persisted=await page.evaluate(async()=>{
    const response=await fetch('./api/state',{credentials:'same-origin',cache:'no-store'});
    return response.json();
  });
  const carousel=persisted.posts.find(p=>p.captionMode==='per_slide');
  assert(carousel && carousel.format==='carousel','Carousel type must be persisted automatically');
  assert.deepEqual(carousel.slideCaptions,['Primeira legenda individual','Segunda legenda revisada']);
  await page.setViewportSize({width:390,height:844});
  await page.locator('#approval-list .item').filter({hasText:'Primeira legenda individual'}).locator('.post-preview-trigger').click();
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),
    'Carousel preview must not overflow mobile viewport');
  await previewDialog.getByRole('button',{name:'Fechar visualização'}).click();
  // H09: stale tab must show a persistent failure, not a success-like green toast.
  const tabB=await context.newPage();
  await tabB.goto(restarted+'/editorial/');
  await tabB.locator('[data-view="approval"]').click();
  await tabB.locator('#approval-list .item').filter({hasText:'Primeira legenda individual'})
    .getByRole('button',{name:'Editar',exact:true}).click();
  await page.locator('#approval-list .item').filter({hasText:'Primeira legenda individual'})
    .getByRole('button',{name:'Editar',exact:true}).click();
  await page.locator('.slide-caption-input').nth(1).fill('H09 - alteração A');
  const savedA=page.waitForResponse(r=>r.url().endsWith('/api/drafts') && r.request().method()==='POST');
  await page.getByRole('button',{name:'Salvar rascunho',exact:true}).click();
  assert.equal((await savedA).status(),200);
  await tabB.locator('.slide-caption-input').nth(1).fill('H09 - alteração B');
  const response409=tabB.waitForResponse(r=>r.url().endsWith('/api/drafts') && r.request().method()==='POST');
  await tabB.getByRole('button',{name:'Salvar rascunho',exact:true}).click();
  assert.equal((await response409).status(),409,'Stale edit must be refused');
  const alert409=tabB.locator('#form-feedback[role="alert"]');
  await alert409.waitFor({state:'visible'});
  assert.match(await alert409.innerText(),/Não foi salvo:/);
  assert.match(await alert409.innerText(),/outra aba/);
  assert.equal(await tabB.locator('#toast.error').count(),1);
  assert.equal(await tabB.locator('.slide-caption-input').nth(1).inputValue(),'H09 - alteração B');
  // Verify the warning is durable even after the transient toast is gone.
  await tabB.waitForTimeout(4100);
  assert.equal(await alert409.isVisible(),true);
  const afterConflict=await page.evaluate(async()=> (await(await fetch('./api/state')).json()).posts.find(p=>p.captionMode==='per_slide'));
  assert.equal(afterConflict.slideCaptions[1],'H09 - alteração A','Stale edit must not overwrite A');
  await tabB.close();
  await page.getByRole('link',{name:'← Mensagens e conexão',exact:true}).click();
  await page.locator('.topbar').waitFor();
  assert.equal(await page.getByRole('button',{name:'Sair',exact:true}).count(),1);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),
    'Responsive Messages page must not overflow viewport');
  await page.getByRole('button',{name:'Sair',exact:true}).click();
  await page.getByRole('button',{name:'Entrar',exact:true}).waitFor();
  assert.equal((await context.request.get(restarted+'/editorial/api/state')).status(),403);
  const unexpectedErrors=errors.filter(error=>!(error.url===injectedScheduleUrl && error.message==='Failed to load resource: the server responded with a status of 502 (Bad Gateway)'));
  assert.deepEqual(unexpectedErrors,[],'Unexpected browser console/page errors');
  assert.deepEqual(blocked,[],'Unexpected non-loopback requests');
  console.log('PASS Chromium: shared login/logout, H10 schedule summary and inline errors, malformed server response recovery, calendar reapproval, H09 stale save, mobile. No external requests.');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close();await stop();fs.rmSync(root,{recursive:true,force:true});
});
