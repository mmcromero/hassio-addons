/* Local read-only counts and Story lifecycle; all Meta operations simulated. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),readline=require('node:readline'),assert=require('node:assert/strict');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'ig-metrics-'));let child,browser;
(async()=>{
  child=spawn('python3',[path.join(__dirname,'publication_browser_fixture.py'),root,'--stories'],{stdio:['ignore','pipe','inherit'],env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
  const lines=readline.createInterface({input:child.stdout});
  const config=await Promise.race([new Promise((resolve,reject)=>{lines.once('line',line=>{try{resolve(JSON.parse(line));}catch(e){reject(e);}});child.once('exit',code=>reject(Error('Fixture exited '+code)));}),new Promise((_,reject)=>setTimeout(()=>reject(Error('Fixture timeout')),10000).unref())]);lines.close();
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1440,height:1050},timezoneId:'America/Sao_Paulo'});
  const errors=[],blocked=[],metricRequests=[];
  await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==config.url){blocked.push('external');return route.abort();}return route.continue();});
  const page=await context.newPage();page.setDefaultTimeout(10000);
  page.on('pageerror',e=>errors.push(e.message));page.on('console',msg=>{if(msg.type()==='error'&&/Content Security Policy|Refused to|Uncaught/.test(msg.text()))errors.push(msg.text());});
  page.on('request',r=>{if(r.headers()['x-editorial-action']==='metrics')metricRequests.push(r.url());});
  await page.goto(config.url+'/panel');await page.getByLabel('Senha').fill('synthetic-browser-publication-password');await page.getByRole('button',{name:'Entrar',exact:true}).click();
  for(const [prefix,caption,likes] of [['','Conteúdo da primeira conta',12],['/accounts/'+config.second,'Conteúdo da segunda conta',24]]){
    await page.goto(config.url+prefix+'/editorial/#approval');
    const row=page.locator('#approval-list .item').filter({has:page.locator('.post-title',{hasText:caption})});
    await row.getByRole('button',{name:'Publicar agora',exact:true}).click();await page.locator('#confirm-publish').click();
    await row.locator('.chip.published').waitFor({timeout:18000});
    assert.equal(await row.locator('.metric-likes').innerText(),'Curtidas: —');
    let release,seen;const held=new Promise(resolve=>seen=resolve),wait=new Promise(resolve=>release=resolve);
    await page.route('**/editorial/api/posts/*/approve',async route=>{
      if(route.request().headers()['x-editorial-action']==='metrics'){seen();await wait;}await route.continue();
    },{times:1});
    await row.getByRole('button',{name:'Atualizar métricas',exact:true}).click();await held;
    assert.equal(await row.getByRole('button',{name:'Processando…',exact:true}).isDisabled(),true);
    release();await row.getByText('Curtidas: '+likes,{exact:true}).waitFor();
    assert.match(await row.locator('.metrics-time').innerText(),/^Última consulta confirmada:/);
    await page.reload();await row.getByText('Curtidas: '+likes,{exact:true}).waitFor();
    console.log('PASS persisted counts, real pending feedback and isolated account '+prefix+' = '+likes+' likes');
  }
  await page.goto(config.url+'/editorial/#approval');
  const expired=page.locator('#approval-list .item').filter({has:page.locator('.post-title',{hasText:'Story expirado'})});
  const fresh=page.locator('#approval-list .item').filter({has:page.locator('.post-title',{hasText:'Story recente'})});
  await expired.locator('.story-availability').waitFor();
  assert.match(await expired.locator('.story-availability').innerText(),/24 horas transcorrido/);
  assert.equal(await expired.locator('a').count(),0);
  assert.equal(await fresh.getByRole('link',{name:'Abrir Story (até 24h)',exact:true}).count(),1);
  await page.clock.install();await page.clock.setFixedTime(new Date(Date.now()+86400000));
  await page.locator('[data-view="overview"]').click();await page.locator('[data-view="approval"]').click();
  assert.equal(await fresh.locator('a').count(),0);
  assert.match(await fresh.locator('.story-availability').innerText(),/arquivo no aplicativo Instagram/);
  console.log('PASS recent Story has temporary link; expired Story keeps local history without archive/public-link promise');
  const row=page.locator('#approval-list .item').filter({has:page.locator('.post-title',{hasText:'Conteúdo da primeira conta'})});
  await page.request.get(config.url+'/__metrics_failure');
  await row.getByRole('button',{name:'Atualizar métricas',exact:true}).click();await row.locator('.metrics-error').waitFor();
  assert.equal(await row.locator('.metric-likes').innerText(),'Curtidas: 12');
  assert.match(await row.locator('.metrics-error').innerText(),/não confirma exclusão/);
  assert.equal(await row.locator('.chip.published').count(),1);
  assert.equal(metricRequests.length,3);
  const result=await (await page.request.get(config.url+'/__publication_test')).json();assert.equal(result.published.length,2);
  const evidence=process.env.IG_EVIDENCE_DIR || root;fs.mkdirSync(evidence,{recursive:true});
  await page.screenshot({path:path.join(evidence,'metrics-and-stories.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
  console.log('PASS failed read preserves counts and history; only 3 explicit metrics reads; no extra publish, CSP/browser errors or external requests');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close();if(child && child.exitCode===null){const done=new Promise(resolve=>child.once('exit',resolve));child.kill('SIGTERM');await done;}fs.rmSync(root,{recursive:true,force:true});
});
