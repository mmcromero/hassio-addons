/* Real Chromium cookie storage/redirect regression. Local HTTPS and provider stub only. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const http=require('node:http'); const fs=require('node:fs'); const path=require('node:path');
const os=require('node:os'); const readline=require('node:readline'); const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'ig15-oauth-'));
let child,browser;
async function start(){
 child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'oauth_browser_fixture.py'),root],{stdio:['ignore','pipe','pipe'],env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
 const reader=readline.createInterface({input:child.stdout});
 return Promise.race([
  new Promise((resolve,reject)=>{reader.once('line',line=>{reader.close();try{resolve(JSON.parse(line));}catch(_){reject(Error('Fixture response invalid'));}});child.once('exit',()=>reject(Error('Fixture exited')));}),
  new Promise((_,reject)=>setTimeout(()=>reject(Error('Fixture startup timeout')),10000).unref())]);
}
(async()=>{
 const data=await start();
 function control(route){return new Promise((resolve,reject)=>{const q=http.get({hostname:'127.0.0.1',port:data.control,path:route},r=>{let s='';r.on('data',v=>s+=v);r.on('end',()=>resolve(JSON.parse(s)));});q.on('error',reject);});}
 browser=await chromium.launch({executablePath:process.env.CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--ignore-certificate-errors','--no-proxy-server','--disable-background-networking','--disable-component-update','--host-resolver-rules=MAP probe-review.test 127.0.0.1, MAP alias-review.test 127.0.0.1, MAP meta-review.test 127.0.0.1, MAP * ~NOTFOUND']});
 const base='https://probe-review.test:'+data.https;
 async function context(){
  const ctx=await browser.newContext({ignoreHTTPSErrors:true,serviceWorkers:'block',extraHTTPHeaders:{Authorization:'Basic '+Buffer.from('admin:oauth_fixture_password_only_123').toString('base64')}});
  await ctx.route('**/*',route=>['probe-review.test','alias-review.test','meta-review.test'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  return ctx;
 }
 for(const kind of ['same_https','same_host_other_port','different_start_host','insecure_start','strip_set_cookie','strip_request_cookie','rewrite_nonce','wrong_forwarded_https','split_cookie_header']){
  await control('/set/'+kind);const ctx=await context();const page=await ctx.newPage();
  const origin=kind==='different_start_host'?'https://alias-review.test:'+data.https:kind==='insecure_start'?'http://probe-review.test:'+data.http:kind==='same_host_other_port'?'https://probe-review.test:'+data.other:base;
  const response=await page.goto(origin+'/oauth/meta/start?probe=1',{timeout:15000});
  const obs=await control('/observe');obs.case=kind;obs.status=response.status();
  const query=new URL(page.url()).searchParams;const nonce=query.get('probe');
  const expected='ig_oauth_state_'+crypto.createHash('sha256').update(nonce).digest('hex').slice(0,32);
  obs.expectedStored=(await ctx.cookies(base+'/oauth/meta/callback')).some(c=>c.name===expected);
  assert.equal(obs.status,['same_https','same_host_other_port','split_cookie_header'].includes(kind)?200:400,kind);
  const text=await page.locator('body').innerText();assert(text.includes('0.1.26'),kind+' version');assert(!text.includes(nonce),kind+' redaction');
  if(kind==='strip_request_cookie'||kind==='insecure_start'||kind==='strip_set_cookie'||kind==='different_start_host')assert(text.includes('Nenhum cabeçalho Cookie'),kind+' classification');
  if(kind==='rewrite_nonce')assert(text.includes('Cookies chegaram'),kind+' wrong-name classification');
  console.log('PASS probe '+JSON.stringify(obs));await ctx.close();
 }
 await control('/set/same_https');
 const ctx=await context();const first=await ctx.newPage();const second=await ctx.newPage();
 await first.goto(base+'/oauth/meta/start');await second.goto(base+'/oauth/meta/start');
 const cookies=(await ctx.cookies(base+'/oauth/meta/callback')).filter(c=>c.name.startsWith('ig_oauth_state_'));
 assert.equal(cookies.length,2,'independent cookie per tab');assert.notEqual(cookies[0].name,cookies[1].name);
 await first.getByRole('link',{name:'Voltar à Central'}).click();await second.getByRole('link',{name:'Voltar à Central'}).click();
 for(const page of [first,second])assert((await page.locator('body').innerText()).includes('verificada e autorizada'));
 const before=(await control('/observe')).exchanges;assert.equal(before,2);
 console.log('PASS concurrent OAuth tabs: two browser cookies and two mocked completions; no provider network');
 const drift=await ctx.newPage();await drift.goto(base+'/oauth/meta/start');await control('/drift');
 const result=drift.waitForResponse(r=>new URL(r.url()).pathname==='/oauth/meta/callback');await drift.getByRole('link',{name:'Voltar à Central'}).click();
 assert.equal((await result).status(),400);assert.equal((await control('/observe')).exchanges,before);
 console.log('PASS configuration drift rejected before exchange');await ctx.close();
 await control('/set/same_https');
 const workerContext=await browser.newContext({ignoreHTTPSErrors:true,serviceWorkers:'allow',
  extraHTTPHeaders:{Authorization:'Basic '+Buffer.from('admin:oauth_fixture_password_only_123').toString('base64')}});
 const old=await workerContext.newPage();await old.goto(base+'/worker-lab');
 await old.evaluate(async()=>{await navigator.serviceWorker.register('/sw-modern.js',{scope:'/'});await navigator.serviceWorker.ready;
  if(!navigator.serviceWorker.controller)await new Promise(r=>navigator.serviceWorker.addEventListener('controllerchange',r,{once:true}));});
 assert.equal(await old.evaluate(()=>!!navigator.serviceWorker.controller),true);
 assert.equal((await old.goto(base+'/oauth/meta/start?probe=1')).status(),400);
 console.log('PASS synthetic root worker interferes on old origin; reproduced without bypass');
 await control('/set/dedicated_host');
 const isolated='https://alias-review.test:'+data.https;
 const own=await workerContext.newPage();await own.goto(isolated+'/panel');
 assert.equal(await own.evaluate(()=>navigator.serviceWorker.controller===null),true);
 await own.getByLabel('Senha',{exact:true}).fill('oauth_fixture_password_only_123');
 await own.getByRole('button',{name:'Entrar',exact:true}).click();await own.waitForURL('**/panel');
 assert((await own.locator('body').innerText()).includes('Conexão com o Instagram'));
 const session=(await workerContext.cookies(isolated)).find(c=>c.name==='ig_panel_session');
 assert(session&&session.secure&&session.httpOnly&&session.sameSite==='Strict','proxy HTTPS session attributes');
 assert(!(await workerContext.cookies(base)).some(c=>c.name==='ig_panel_session'),'host-only session not sent to old HA hostname');
 const probe=await workerContext.newPage();assert.equal((await probe.goto(isolated+'/oauth/meta/start?probe=1')).status(),200);
 assert((await probe.locator('body').innerText()).includes('Teste aprovado'));
 assert.equal(await probe.evaluate(()=>navigator.serviceWorker.controller===null),true);
 console.log('PASS dedicated hostname, same TLS port: existing login, Secure/HttpOnly session, probe, no HA root worker');
 const proxyBefore=(await control('/observe')).exchanges;
 await probe.goto(isolated+'/oauth/meta/start');
 await probe.getByRole('link',{name:'Voltar à Central'}).click();
 assert((await probe.locator('body').innerText()).includes('verificada e autorizada'));
 assert.equal(new URL(probe.url()).origin,isolated);
 assert.equal((await control('/observe')).exchanges,proxyBefore+1);
 console.log('PASS proxy HTTPS OAuth: synthetic provider round trip returns to dedicated hostname and existing account store');

 await own.goto(isolated+'/panel');
 let checkPosts=0;
 own.on('request',request=>{if(request.method()==='POST'&&new URL(request.url()).pathname==='/panel/meta/check')checkPosts++;});
 // Hold the first submit at the document boundary, after the real region
 // listener runs, so native navigation cannot hide the pending UI from inspection.
 await own.evaluate(()=>document.addEventListener('submit',event=>event.preventDefault(),{once:true}));
 await own.getByRole('button',{name:'Verificar acesso Meta',exact:true}).click();
 assert.equal(await own.locator('#meta-actions').getAttribute('aria-busy'),'true');
 assert.equal(await own.getByRole('button',{name:'Verificando…',exact:true}).isDisabled(),true);
 assert((await own.locator('#meta-action-progress').innerText()).includes('Aguarde a conclusão'));
 assert.equal(await own.evaluate(()=>!document.querySelector('#meta-actions form').dispatchEvent(
   new Event('submit',{bubbles:true,cancelable:true}))),true,'second submission prevented');
 assert.equal(checkPosts,0,'held submit and repeated submit made no requests');
 await own.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
 assert.equal(await own.getByRole('button',{name:'Verificar acesso Meta',exact:true}).isEnabled(),true);
 assert.equal(await own.locator('#meta-action-progress').isHidden(),true);
 await own.getByRole('button',{name:'Verificar acesso Meta',exact:true}).click();
 await own.waitForURL('**/panel');
 assert.equal(checkPosts,1,'only one Meta check POST');
 console.log('PASS Meta loading feedback under CSP: immediate busy state, disabled button, live notice and one POST despite repeat submission');
 const diagnostic=own.getByLabel('Diagnóstico de recebimento',{exact:true});
 await diagnostic.waitFor();
 assert((await diagnostic.innerText()).includes('campo messages presente.'));
 assert((await diagnostic.innerText()).includes('Acesso aceito; há conversa visível'));
 assert((await diagnostic.innerText()).includes('Válido: Sim; pertence ao app configurado: Sim; instagram_basic: Sim; instagram_manage_messages: Sim.'));
 assert((await diagnostic.innerText()).includes('Objeto Instagram encontrado. Ativo: Sim; messages: Sim; HTTPS: Sim; caminho /webhook/instagram: Sim.'));
 assert(!(await own.locator('body').innerText()).includes('SYNTHETIC_CONVERSATION_ID'));
 assert((await own.getByRole('status').innerText()).includes('Verificação de identidade concluída'));
 console.log('PASS visible receiving audit after authenticated POST/303: subscription and conversation access, no private content');
 const primaryDigest=(await control('/observe')).primaryDigest;
 await own.goto(isolated+'/accounts');
 const contexts=[];
 for(const [name,user] of [['Second account','second_review'],['Third account','third_review']]){
  await own.getByLabel('Nome da conta',{exact:true}).fill(name);
  await own.getByLabel('Usuário do Instagram',{exact:true}).fill('@'+user);
  await own.getByRole('button',{name:'Adicionar conta',exact:true}).click();
  await own.waitForURL('**/accounts/*/panel');
  const accountPage=await workerContext.newPage();await accountPage.goto(own.url());
  const accountBase=own.url().replace(/\/panel$/,'');
  const popupPromise=workerContext.waitForEvent('page');
  await accountPage.getByRole('link',{name:'Conectar Instagram pela Meta',exact:true}).click();
  const popup=await popupPromise;await popup.getByRole('link',{name:'Voltar à Central'}).waitFor();
  contexts.push({page:accountPage,popup,base:accountBase,user});
  await own.goto(isolated+'/accounts');
 }
 for(const item of [...contexts].reverse()){
  await item.popup.getByRole('link',{name:'Voltar à Central'}).click();
  assert((await item.popup.locator('body').innerText()).includes('Conta @'+item.user+' verificada e autorizada'));
  assert.equal(await item.popup.getByRole('link',{name:'Voltar ao painel da conta',exact:true}).getAttribute('href'),new URL(item.base).pathname+'/panel');
  await item.page.reload();assert.equal(await item.page.locator('.account').innerText(),'@'+item.user);
 }
 assert.equal((await control('/observe')).primaryDigest,primaryDigest,'primary encrypted credential preserved byte-for-byte');
 const left=contexts[0].page,right=contexts[1].page;
 await left.getByRole('link',{name:'Editorial',exact:true}).click();
 await right.getByRole('link',{name:'Editorial',exact:true}).click();
 await left.locator('#count-all').filter({hasText:'0'}).waitFor();
 const image=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAAHUlEQVR4nGNMaljDQC5gIlvnqOZRzaOaRzVTRTMAyc8BtjG4iWEAAAAASUVORK5CYII=','base64');
 await left.locator('[data-view="library"]').click();
 await left.locator('#media-input').setInputFiles({name:'synthetic.png',mimeType:'image/png',buffer:image});
 await left.locator('#media-grid img').waitFor();
 await right.locator('[data-view="library"]').click();
 assert.equal(await right.locator('#media-grid img').count(),0,'other account library remains empty');
 await own.goto(isolated+'/accounts');
 assert.equal(await own.getByText('Conectada à Meta',{exact:false}).count(),3,'three independently stored account contexts');
 if(process.env.IG_EVIDENCE_DIR){fs.mkdirSync(process.env.IG_EVIDENCE_DIR,{recursive:true});await own.screenshot({path:path.join(process.env.IG_EVIDENCE_DIR,'accounts.png'),fullPage:true});await left.screenshot({path:path.join(process.env.IG_EVIDENCE_DIR,'account-editorial.png'),fullPage:true});}
 console.log('PASS multi-account Chromium: registration, two concurrent OAuth contexts, reverse callbacks, isolated Editorial media and preserved primary token');
 await workerContext.close();
 console.log('PASS OAuth Chromium: 9 probe cases, concurrent tabs, config binding. Local HTTPS only; no real Meta/HA.');
})().catch(error=>{console.error('FAIL OAuth Chromium '+error.name+' '+String(error.message).replace(/https?:\/\/[^\s]+/g,'[local-test-url]').replace(/[A-Za-z0-9_-]{40,}/g,'[synthetic-value]'));process.exitCode=1;}).finally(async()=>{
 if(browser)await browser.close();
 if(child&&child.exitCode===null){const done=new Promise(r=>child.once('exit',r));child.kill('SIGTERM');await done;}
 fs.rmSync(root,{recursive:true,force:true});
});
