/* Manual inbox and initial-account connection UX. Synthetic local HTTPS only. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),readline=require('node:readline'),http=require('node:http');
const assert=require('node:assert/strict');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'ig-inbox-'));let child,browser;
(async()=>{
  child=spawn('python3',[path.join(__dirname,'oauth_browser_fixture.py'),root,'--inbox'],{stdio:['ignore','pipe','inherit'],env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
  const lines=readline.createInterface({input:child.stdout});
  const config=await Promise.race([new Promise((resolve,reject)=>{lines.once('line',line=>{try{resolve(JSON.parse(line));}catch(e){reject(e);}});child.once('exit',code=>reject(Error('Fixture exited '+code)));}),new Promise((_,reject)=>setTimeout(()=>reject(Error('Fixture timeout')),10000).unref())]);lines.close();
  const control=route=>new Promise((resolve,reject)=>{http.get({hostname:'127.0.0.1',port:config.control,path:route},r=>{let raw='';r.on('data',x=>raw+=x);r.on('end',()=>resolve(JSON.parse(raw)));}).on('error',reject);});
  await control('/set/dedicated_host');const origin='https://central.probe-review.test:'+config.https;
  browser=await chromium.launch({executablePath:process.env.CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--ignore-certificate-errors','--no-proxy-server','--disable-background-networking','--host-resolver-rules=MAP central.probe-review.test 127.0.0.1, MAP probe-review.test 127.0.0.1, MAP meta-review.test 127.0.0.1, MAP * ~NOTFOUND']});
  const context=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:1440,height:1100},timezoneId:'America/Sao_Paulo',serviceWorkers:'block'});
  const errors=[],blocked=[];let posts=0;
  await context.route('**/*',route=>{if(!['central.probe-review.test','probe-review.test','meta-review.test'].includes(new URL(route.request().url()).hostname)){blocked.push('external');return route.abort();}return route.continue();});
  const page=await context.newPage();page.setDefaultTimeout(10000);
  page.on('pageerror',e=>errors.push(e.message));page.on('console',msg=>{if(msg.type()==='error' && /Content Security Policy|Refused to|Uncaught/.test(msg.text()))errors.push(msg.text());});
  page.on('request',r=>{if(r.headers()['x-meta-inbox']==='refresh')posts++;});
  await page.goto(origin+'/panel');await page.getByLabel('Senha',{exact:true}).fill('oauth_fixture_password_only_123');await page.getByRole('button',{name:'Entrar',exact:true}).click();await page.waitForURL('**/panel');
  assert.equal((await control('/inbox-observe')).inboxReads,0);
  async function connect(){const opened=context.waitForEvent('page');await page.getByRole('link',{name:'Conectar Instagram pela Meta',exact:true}).click();const popup=await opened;await popup.getByRole('link',{name:'Voltar à Central'}).click();await popup.getByText('Nenhum conteúdo foi enviado.',{exact:false}).waitFor();await popup.close();await page.reload();}
  await page.getByRole('link',{name:'Configurações Meta',exact:true}).click();await connect();await page.getByRole('link',{name:'Caixa de entrada',exact:true}).click();

  await control('/inbox-mode/no_expansion');
  await page.locator('#refresh-inbox').click();
  await page.locator('#inbox-feedback').filter({hasText:'1 mensagem(ns) adicionada(s)'}).waitFor();
  assert((await page.locator('#inbox-messages').innerText()).includes('SYNTHETIC 11111111'));
  assert.equal(await page.locator('#inbox-messages script').count(),0);
  assert.deepEqual(await control('/inbox-observe'),{inboxReads:1,directReads:1,stored:1,queued:0});
  await page.locator('#refresh-inbox').click();
  await page.locator('#inbox-feedback').filter({hasText:'0 mensagem(ns) adicionada(s), 1 já armazenada(s)'}).waitFor();
  await control('/inbox-mode/partial');await page.locator('#refresh-inbox').click();
  await page.locator('#inbox-feedback').filter({hasText:'Busca parcial'}).waitFor();
  assert((await page.locator('#inbox-feedback').innerText()).includes('1 conversa(s) ficaram indisponíveis'));
  assert.deepEqual(await control('/inbox-observe'),{inboxReads:3,directReads:4,stored:2,queued:0});
  const before=await page.locator('#inbox-messages').innerText();
  await control('/inbox-mode/all_unavailable');await page.locator('#refresh-inbox').click();
  await page.locator('#inbox-feedback').filter({hasText:'A Meta recusou o acesso'}).waitFor();
  assert((await page.locator('#inbox-feedback').innerText()).includes('Conversas listadas: 1. Consultas diretas: 1.'));
  assert.equal(await page.locator('#inbox-messages').innerText(),before);
  assert.equal(await page.locator('#refresh-inbox').isEnabled(),true);
  assert.equal(await page.locator('#inbox-messages').getAttribute('aria-busy'),null);
  const counts=await control('/inbox-observe');await page.reload();
  assert.deepEqual(await control('/inbox-observe'),counts,'reload must not fetch content');
  for(const width of [320,360,390]){
    await page.setViewportSize({width,height:844});await page.locator('#refresh-inbox').focus();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    assert.ok((await page.locator('#refresh-inbox').boundingBox()).height>=44);
  }
  assert.equal(posts,4);assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
  console.log('PASS HTTPS manual click: missing expansion -> direct edge, dedup, partial result warns/preserves readable texts, all unavailable preserves inbox, no polling or queue, no private provider IDs/tokens, 320/360/390/CSP');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(child&&child.exitCode===null){const done=new Promise(resolve=>child.once('exit',resolve));child.kill('SIGTERM');await done;}fs.rmSync(root,{recursive:true,force:true});});
