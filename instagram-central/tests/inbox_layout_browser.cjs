/* Synthetic inbox layout and local handoff only; never reads customer content. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),readline=require('node:readline');
const assert=require('node:assert/strict');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'ig-inbox-layout-'));
let child,browser;
(async()=>{
  child=spawn('python3',[path.join(__dirname,'publication_browser_fixture.py'),root,'--inbox-layout'],{stdio:['ignore','pipe','inherit'],env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
  const lines=readline.createInterface({input:child.stdout});
  const config=await new Promise((resolve,reject)=>{lines.once('line',line=>resolve(JSON.parse(line)));child.once('exit',code=>reject(Error('Fixture exited '+code)));});lines.close();
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1280,height:900},hasTouch:true,timezoneId:'America/Sao_Paulo'});
  const errors=[],external=[];
  await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==config.url){external.push('external');return route.abort();}return route.continue();});
  const page=await context.newPage();page.setDefaultTimeout(8000);page.on('pageerror',e=>errors.push(e.message));
  page.on('console',msg=>{if(msg.type()==='error' && /Content Security Policy|Refused to|Uncaught/.test(msg.text()))errors.push(msg.text());});
  const evidence=process.env.IG_EVIDENCE_DIR || root;fs.mkdirSync(evidence,{recursive:true});
  await page.goto(config.url+'/panel');await page.getByLabel('Senha').fill('synthetic-browser-publication-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();await page.locator('#messages').waitFor();
  if(process.env.IG_LAYOUT_BASELINE){
    const sizes=await page.locator('#inbox-messages .item-actions button').evaluateAll(nodes=>nodes.map(n=>({label:n.textContent,width:Math.round(n.getBoundingClientRect().width),height:Math.round(n.getBoundingClientRect().height)})));
    await page.screenshot({path:path.join(evidence,'inbox-before-desktop.png'),fullPage:true,animations:'disabled'});
    console.log(JSON.stringify({baseline:'eight-column table',sizes}));return;
  }
  assert.equal(await page.locator('.inbox-message').count(),2);assert.equal(await page.locator('#inbox-messages table').count(),0);
  assert.equal(await page.locator('#inbox-messages script').count(),0);
  assert((await page.locator('.inbox-draft').innerText()).includes('<script>not_script()</script>'));
  assert(!(await page.locator('#inbox-messages').innerText()).includes('Somente a segunda conta'));
  const sizes=[];
  for(const width of [1920,1440,1280,1100,768,390,360,320]){
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'page overflow at '+width);
    for(const card of await page.locator('.inbox-message').all()){
      const box=await card.boundingBox();assert.ok(box.x>=0 && box.x+box.width<=width+1,'card bounds at '+width);
      assert.ok(await card.evaluate(n=>n.scrollWidth<=n.clientWidth+1),'card overflow at '+width);
      for(const button of await card.locator('.inbox-message-actions button').all()){
        const b=await button.boundingBox();assert.ok(b.width>=90 && b.height>=44 && b.height<=72,'readable touch target at '+width);
        assert.ok(b.x>=box.x && b.x+b.width<=box.x+box.width+1 && b.y+b.height<=box.y+box.height+1,'action outside card at '+width);
        assert.ok(await button.evaluate(n=>n.scrollWidth<=n.clientWidth+1),'button clipping at '+width);
      }
      sizes.push({width,height:Math.round(box.height)});
    }
    if([1280,390,320].includes(width))await page.screenshot({path:path.join(evidence,'inbox-'+width+'.png'),fullPage:true,animations:'disabled'});
    if(width===390)await page.locator('.inbox-message').filter({hasText:'17559000000000002'}).screenshot({path:path.join(evidence,'inbox-short-card-390.png'),animations:'disabled'});
  }
  // Same native CSRF forms, now readable and tappable on mobile.
  const card=page.locator('.inbox-message').filter({hasText:'17559000000000002'});
  await card.getByRole('button',{name:'Assumir',exact:true}).tap();
  await card.getByText('Controle: Atendimento humano',{exact:true}).waitFor();
  assert.equal(await card.getByRole('button',{name:'Voltar ao bot',exact:true}).count(),1);
  await page.emulateMedia({reducedMotion:'reduce'});await card.getByRole('button',{name:'Aguardar',exact:true}).focus();
  await page.keyboard.press('Enter');await card.getByText('Controle: Aguardando',{exact:true}).waitFor();
  await card.locator('summary').click();assert((await card.locator('details').innerText()).includes('Pendente'));
  await page.setViewportSize({width:640,height:844});await page.locator('body').evaluate(n=>n.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'text enlargement overflow');
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  assert.equal((await (await page.request.get(config.url+'/__publication_test')).json()).published.length,0);
  console.log(JSON.stringify({status:'PASS',checks:['readable action labels and bounds','1920/1440/1280/1100/768/390/360/320x844','long URLs/newlines/emoji/draft','safe escaped content','account isolation','mobile native handoff','keyboard','reduced motion','text enlargement sample','CSP/no external or send'],sizes}));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close();if(child && child.exitCode===null){const done=new Promise(resolve=>child.once('exit',resolve));child.kill();await done;}
  fs.rmSync(root,{recursive:true,force:true});
});
