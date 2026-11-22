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
  let seen,release;const received=new Promise(resolve=>seen=resolve),held=new Promise(resolve=>release=resolve);
  await page.route('**/panel/meta/check',async route=>{seen();await held;await route.continue();},{times:1});
  await page.getByRole('button',{name:'Atualizar mensagens',exact:true}).click();await received;
  assert.equal(await page.locator('#refresh-inbox').isDisabled(),true);assert.equal(await page.locator('#inbox-messages').getAttribute('aria-busy'),'true');
  assert.equal(await page.locator('#refresh-inbox').innerText(),'Buscando na Meta…');await page.locator('#refresh-inbox').evaluate(node=>node.click());assert.equal(posts,1);release();
  await page.locator('#inbox-feedback').filter({hasText:'1 mensagem(ns) adicionada(s)'}).waitFor();
  assert((await page.locator('#inbox-messages').innerText()).includes('SYNTHETIC 11111111 <script>not_script()</script>'));
  assert(!(await page.locator('#inbox-messages').innerText()).includes('OUTGOING_NEVER_IMPORTED'));
  assert.equal(await page.locator('#inbox-messages script').count(),0);assert.equal((await control('/inbox-observe')).queued,0);
  assert((await page.locator('#inbox-messages').innerText()).includes('Consulta manual à Meta'));
  const first=await page.locator('#inbox-messages').innerText();
  const evidence=process.env.IG_EVIDENCE_DIR||root;fs.mkdirSync(evidence,{recursive:true});await page.screenshot({path:path.join(evidence,'manual-inbox-desktop.png'),fullPage:true});
  await page.getByRole('button',{name:'Atualizar mensagens',exact:true}).click();await page.locator('#inbox-feedback').filter({hasText:'0 mensagem(ns) adicionada(s), 1 já armazenada(s)'}).waitFor();assert.equal((await control('/inbox-observe')).stored,1);
  await page.route('**/panel/meta/check',route=>route.fulfill({status:504,contentType:'text/html',body:'<h1>Gateway timeout</h1>'}),{times:1});await page.locator('#refresh-inbox').click();await page.locator('#inbox-feedback').filter({hasText:'As mensagens já armazenadas foram preservadas'}).waitFor();assert.equal(await page.locator('#inbox-messages').innerText(),first);
  await page.reload();assert.equal((await control('/inbox-observe')).inboxReads,2);
  await page.emulateMedia({reducedMotion:'reduce'});
  for(const width of [320,360,390]){await page.setViewportSize({width,height:844});await page.locator('#refresh-inbox').focus();assert.equal(await page.locator('#refresh-inbox').evaluate(n=>n===document.activeElement),true);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert((await page.locator('#refresh-inbox').boundingBox()).height>=44);}
  await page.screenshot({path:path.join(evidence,'manual-inbox-mobile.png'),fullPage:true});
  await page.setViewportSize({width:844,height:390});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.setViewportSize({width:1440,height:1100});await page.getByRole('link',{name:'Contas conectadas',exact:true}).click();await page.locator('#account-list a[href="#add-account"]').click();await page.getByLabel('Nome da conta',{exact:true}).fill('Segunda conta');await page.getByLabel('Usuário do Instagram',{exact:true}).fill('second_review');await page.getByRole('button',{name:'Adicionar conta',exact:true}).click();await page.waitForURL('**/accounts/*/panel?view=settings');
  const second=new URL(page.url()).pathname.replace(/\/panel$/,'');
  assert.equal(await page.locator('#meta-actions button').first().isDisabled(),true);await page.getByText('Próximo passo: autorizar esta conta na Meta.',{exact:true}).waitFor();
  assert.equal(await page.getByRole('link',{name:'Conectar Instagram pela Meta',exact:true}).getAttribute('class'),'btn primary');await page.screenshot({path:path.join(evidence,'new-account-authorization.png'),fullPage:true});
  for(const width of [320,360,390]){await page.setViewportSize({width,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert((await page.getByRole('link',{name:'Conectar Instagram pela Meta',exact:true}).boundingBox()).height>=44);}
  await page.screenshot({path:path.join(evidence,'new-account-authorization-mobile.png'),fullPage:true});await page.setViewportSize({width:1440,height:1100});
  const missing=await page.evaluate(async()=>{const form=document.querySelector('#meta-actions form');const response=await fetch(form.action,{method:'POST',body:new URLSearchParams(new FormData(form))});return {url:response.url,text:await response.text()};});
  assert(missing.url.includes(second+'/panel?view=settings&meta_result=authorization_missing'));assert(missing.text.includes('ainda não tem uma autorização Meta utilizável'));assert(!missing.text.includes('Meta access or subscription not verified'));
  await connect();assert.equal(await page.locator('#meta-actions button').first().isEnabled(),true);await page.getByRole('link',{name:'Caixa de entrada',exact:true}).click();
  await page.locator('#refresh-inbox').click();await page.locator('#inbox-feedback').filter({hasText:'1 mensagem(ns) adicionada(s)'}).waitFor();const secondText=await page.locator('#inbox-messages').innerText();assert(secondText.includes('SYNTHETIC 22222222'));assert(!secondText.includes('SYNTHETIC 11111111'));assert.equal((await control('/inbox-observe')).stored,2);
  await page.getByRole('link',{name:'Configurações Meta',exact:true}).click();await page.locator('.ui-visual-account-picker summary').click();await page.locator('[data-account-link][href="/panel?view=settings"]').click();await page.waitForURL(origin+'/panel?view=settings');
  await control('/inbox-reject-token');await page.getByRole('tab',{name:'Diagnósticos',exact:true}).click();await page.getByRole('button',{name:'Verificar acesso Meta',exact:true}).click();await page.waitForURL('**/panel?view=settings&meta_result=token_invalid');await page.getByRole('link',{name:'Reconectar Instagram pela Meta',exact:true}).waitFor();assert((await page.locator('#meta-feedback').innerText()).includes('recusou a credencial salva'));await page.screenshot({path:path.join(evidence,'refused-token-settings.png'),fullPage:true});
  assert(!/SYNTHETIC_TOKEN_NOT_REAL_|SYNTHETIC_UNUSED_APP_SECRET/.test(await page.locator('body').innerText()));assert.equal(blocked.length,0);assert.deepEqual(errors,[]);
  console.log('PASS Chromium HTTPS: explicit inbox GET/no polling or send, one pending click/loading/skeleton, dedup and safe text, HTML504 preserves inbox, reload zero Graph reads, manual rows outside queue, two-account isolation; new-account OAuth CTA/check disabled, missing-token POST returns same settings, refused credential reconnect feedback, mobile/keyboard/reduced motion/CSP');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(child&&child.exitCode===null){const done=new Promise(resolve=>child.once('exit',resolve));child.kill('SIGTERM');await done;}fs.rmSync(root,{recursive:true,force:true});});
