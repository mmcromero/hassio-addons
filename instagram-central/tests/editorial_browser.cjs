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
  await context.route('**/*',route=>{
    const requested=new URL(route.request().url());
    if(requested.origin!==url){blocked.push(requested.origin);return route.abort();}
    return route.continue();
  });
  const page=await context.newPage();
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
  await page.goto(url+'/');
  await page.getByLabel('Senha').fill('browser_fixture_password_only_123');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await page.getByRole('cell',{name:'Mensagem sintética para regressão',exact:true}).waitFor();
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
  await page.getByRole('button',{name:'+ Nova publicação',exact:true}).click();
  await page.locator('#post-caption').fill('Conteúdo sintético — revisão local');
  await page.locator('#open-library-picker').click();
  await page.locator('#picker-grid button').click();
  await page.locator('#apply-media-selection').click();
  await page.getByRole('button',{name:'Salvar e revisar',exact:true}).click();
  await page.getByRole('button',{name:'Aprovar',exact:true}).waitFor();
  await page.getByRole('button',{name:'Aprovar',exact:true}).click();
  await page.getByRole('button',{name:'Agendar',exact:true}).click();
  const future=new Date(Date.now()+2*86400000).toISOString().slice(0,10)+'T09:30';
  await page.locator('#schedule-at').fill(future);
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
  await page.getByRole('link',{name:'← Mensagens e conexão',exact:true}).click();
  await page.getByRole('button',{name:'Sair',exact:true}).click();
  await page.getByRole('button',{name:'Entrar',exact:true}).waitFor();
  assert.equal((await context.request.get(restarted+'/editorial/api/state')).status(),403);
  assert.deepEqual(errors,[],'Browser console/page errors');
  assert.deepEqual(blocked,[],'Unexpected non-loopback requests');
  console.log('PASS Chromium: login, Mensagens/handoff, navigation, upload, private preview, draft, approval, São Paulo schedule, reload, cancel, edit invalidation, mobile, process restart, logout. No external requests.');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close();await stop();fs.rmSync(root,{recursive:true,force:true});
});
