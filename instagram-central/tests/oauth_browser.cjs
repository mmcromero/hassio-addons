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
 browser=await chromium.launch({executablePath:process.env.CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--no-proxy-server','--disable-background-networking','--disable-component-update','--host-resolver-rules=MAP probe-review.test 127.0.0.1, MAP alias-review.test 127.0.0.1, MAP meta-review.test 127.0.0.1, MAP * ~NOTFOUND']});
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
  const text=await page.locator('body').innerText();assert(text.includes('0.1.16'),kind+' version');assert(!text.includes(nonce),kind+' redaction');
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
 console.log('PASS OAuth Chromium: 9 probe cases, concurrent tabs, config binding. Local HTTPS only; no real Meta/HA.');
})().catch(error=>{console.error('FAIL OAuth Chromium '+error.name);process.exitCode=1;}).finally(async()=>{
 if(browser)await browser.close();
 if(child&&child.exitCode===null){const done=new Promise(r=>child.once('exit',r));child.kill('SIGTERM');await done;}
 fs.rmSync(root,{recursive:true,force:true});
});
