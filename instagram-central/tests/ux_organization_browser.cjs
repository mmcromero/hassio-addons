/* Approved UX organization: synthetic local accounts, no Meta or Home Assistant. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),readline=require('node:readline');
const assert=require('node:assert/strict');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'ig-ux-'));
let child,browser;
(async()=>{
  child=spawn('python3',[path.join(__dirname,'publication_browser_fixture.py'),root,'--deletion','--avatars'],{stdio:['ignore','pipe','inherit'],env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
  const lines=readline.createInterface({input:child.stdout});
  const config=await new Promise((resolve,reject)=>{lines.once('line',line=>resolve(JSON.parse(line)));child.once('exit',code=>reject(Error('Fixture exited '+code)));});lines.close();
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1366,height:900},timezoneId:'America/Sao_Paulo',isMobile:true,hasTouch:true,deviceScaleFactor:2});
  const errors=[],external=[];
  await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==config.url){external.push('external');return route.abort();}return route.continue();});
  const page=await context.newPage();page.setDefaultTimeout(8000);page.on('pageerror',e=>errors.push(e.message));
  page.on('console',msg=>{if(msg.type()==='error' && /Content Security Policy|Refused to|Uncaught/.test(msg.text()))errors.push(msg.text());});
  const evidence=process.env.IG_EVIDENCE_DIR || root;fs.mkdirSync(evidence,{recursive:true});
  const screenshot=async name=>page.screenshot({path:path.join(evidence,name+'.png'),fullPage:true,animations:'disabled'});
  const fits=async width=>{
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'overflow at '+width);
    for(const tab of await page.getByRole('tab').all())if(await tab.isVisible()){
      const b=await tab.boundingBox();assert.ok(b.height>=44 && b.width>=44,'tab target at '+width);
    }
  };
  await page.goto(config.url+'/panel');await page.getByLabel('Senha').fill('synthetic-browser-publication-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();await page.locator('#messages').waitFor();
  await page.goto(config.url+'/panel?view=settings');
  assert.equal(await page.getByRole('tab',{name:'Conexão',exact:true}).getAttribute('aria-selected'),'true');
  assert.equal(await page.locator('[data-ui-pane]:visible').count(),1);
  await page.getByRole('tab',{name:'Conexão',exact:true}).focus();await page.keyboard.press('ArrowRight');
  assert.equal(await page.getByRole('tab',{name:'Diagnósticos',exact:true}).getAttribute('aria-selected'),'true');
  await page.locator('#check-publication').waitFor();await page.keyboard.press('End');
  assert.equal(await page.getByRole('tab',{name:'Ferramentas',exact:true}).getAttribute('aria-selected'),'true');
  await page.goBack();await page.locator('[data-ui-pane="diagnostics"]:visible').waitFor();
  for(const width of [320,360,390]){
    await page.setViewportSize({width,height:844});
    for(const name of ['Conexão','Diagnósticos','Ferramentas']){await page.getByRole('tab',{name,exact:true}).click();await fits(width);}
  }
  await page.getByRole('tab',{name:'Conexão',exact:true}).click();await screenshot('settings-mobile-390');
  const connectionHeight=await page.locator('[data-ui-pane="connection"]').evaluate(n=>Math.round(n.getBoundingClientRect().height));
  await page.goto(config.url+'/accounts');
  assert.equal(await page.locator('#account-list').isVisible(),true);assert.equal(await page.locator('#add-account').isVisible(),false);
  await page.locator('#account-list a[href="#add-account"]').click();
  await page.getByLabel('Nome da conta',{exact:true}).fill('Nome preservado');
  await page.getByLabel('Usuário do Instagram',{exact:true}).fill('conta_incompleta');
  await page.getByRole('link',{name:'Voltar às contas',exact:true}).click();await page.goBack();
  assert.equal(await page.getByLabel('Nome da conta',{exact:true}).inputValue(),'Nome preservado');
  // A route change loses the unsaved form; declining must keep every field.
  page.once('dialog',d=>d.dismiss());await page.locator('.brand').click();
  assert.ok(page.url().endsWith('#add-account'));
  await page.getByLabel('Nome da conta',{exact:true}).fill('');await page.getByLabel('Usuário do Instagram',{exact:true}).fill('');
  await page.getByRole('link',{name:'Voltar às contas',exact:true}).click();
  for(const width of [320,360,390]){await page.setViewportSize({width,height:844});await fits(width);}
  await screenshot('accounts-mobile-390');
  await page.goto(config.url+'/editorial/#approval');
  await page.locator('#approval-list .item').filter({hasText:'Conteúdo da primeira conta'}).getByRole('button',{name:'Editar',exact:true}).click();
  await page.locator('#post-caption').fill('Composição preservada ao alternar Conteúdo e Prévia');
  await page.getByRole('tab',{name:'Prévia',exact:true}).click();
  assert.equal(await page.locator('#post-form').isVisible(),false);
  assert((await page.locator('#preview-caption').innerText()).includes('Composição preservada'));
  await page.getByRole('tab',{name:'Conteúdo',exact:true}).click();
  assert((await page.locator('#post-caption').inputValue()).includes('Composição preservada'));
  await page.setViewportSize({width:1366,height:900});
  await page.locator('#post-form').waitFor();await page.locator('#editor-preview-pane').waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.locator('#post-caption').focus();await page.setViewportSize({width:390,height:430});
  await page.locator('#save-draft').scrollIntoViewIfNeeded();
  const focused=await page.locator('#save-draft').boundingBox();assert.ok(focused.y>=0 && focused.y+focused.height<=430);
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:'Salvar e revisar',exact:true}).tap();
  const review=page.locator('#approval-list .item').filter({hasText:'Composição preservada ao alternar Conteúdo e Prévia'});
  await review.getByRole('button',{name:'Aprovar',exact:true}).tap();
  await review.getByRole('button',{name:'Agendar',exact:true}).tap();
  await page.locator('#schedule-at').fill(new Date(Date.now()+3*86400000).toISOString().slice(0,16));
  await page.getByRole('button',{name:'Confirmar agenda',exact:true}).tap();
  await page.waitForFunction(()=>!document.getElementById('schedule-dialog').open);
  const scheduled=page.locator('#calendar-list .item').filter({hasText:'Composição preservada ao alternar Conteúdo e Prévia'});
  await scheduled.getByRole('button',{name:'Cancelar agenda',exact:true}).tap();
  await page.locator('#toast').filter({hasText:'Agendamento cancelado.'}).waitFor();
  await page.setViewportSize({width:1366,height:900});
  await page.locator('[data-view="history"]').click();
  const row=page.locator('#history-list .item').filter({hasText:'Excluir remoto sintético 0'});
  await row.locator('.metric-likes').waitFor();assert.equal(await row.locator('details').getAttribute('open'),null);
  assert.equal(await row.locator('.metric-likes').isVisible(),true);assert.equal(await row.locator('.metric-shares').isVisible(),false);
  await row.locator('summary').click();assert.equal(await row.locator('.metric-shares').isVisible(),true);
  await page.locator('#history-format').selectOption('feed');
  assert.equal(await row.locator('details').getAttribute('open'),'');
  await page.locator('[data-view="calendar"]').click();await page.goBack();
  await page.locator('#view-history:not(.hidden)').waitFor();assert.equal(await page.locator('#history-format').inputValue(),'feed');
  for(const width of [320,360,390]){await page.setViewportSize({width,height:844});await fits(width);}
  await screenshot('history-mobile-390');
  const cardHeight=await row.evaluate(n=>Math.round(n.getBoundingClientRect().height));
  await page.emulateMedia({reducedMotion:'reduce'});await page.locator('#new-post').click();
  await page.setViewportSize({width:320,height:844});
  await page.locator('#post-caption').fill('Conteúdo preparado no celular.');
  await page.locator('#open-library-picker').tap();
  await page.locator('#picker-grid button').first().tap();await page.locator('#apply-media-selection').tap();
  await fits(320);
  const remove=await page.locator('#selected-media button').first().boundingBox();assert.ok(remove.width>=44 && remove.height>=44);
  await screenshot('editor-content-mobile-320');
  await page.getByRole('tab',{name:'Prévia',exact:true}).tap();await fits(320);await screenshot('editor-preview-mobile-320');
  await page.setViewportSize({width:844,height:390});await fits(844);
  await page.setViewportSize({width:640,height:844});await page.locator('body').evaluate(n=>n.style.fontSize='200%');await fits(640);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  assert.equal((await (await page.request.get(config.url+'/__publication_test')).json()).published.length,0);
  console.log(JSON.stringify({status:'PASS',checks:['settings task tabs','keyboard/arrows/Home/End','browser Back','single accounts task','unsaved confirmation','preserved composition','responsive content/preview','touch: save/review/approve/schedule/cancel','touch: media picker and preview','reduced-height keyboard sample','compact cards and details','preserved filters','320/360/390x844','landscape 844x390','text enlargement sample','reduced motion','CSP/no external or publication'],connectionHeightAt390:connectionHeight,expandedCardHeightAt390:cardHeight,evidence}));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close();if(child && child.exitCode===null){const done=new Promise(resolve=>child.once('exit',resolve));child.kill();await done;}
  fs.rmSync(root,{recursive:true,force:true});
});
