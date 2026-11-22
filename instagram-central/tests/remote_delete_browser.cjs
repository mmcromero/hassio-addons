/* Local synthetic provider only. No real posts, tokens, Meta or HA. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),readline=require('node:readline');
const assert=require('node:assert/strict');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'ig-delete-'));
let child,browser;
(async()=>{
  child=spawn('python3',[path.join(__dirname,'publication_browser_fixture.py'),root,'--deletion'],{stdio:['ignore','pipe','inherit'],env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
  const lines=readline.createInterface({input:child.stdout});
  const config=await new Promise((resolve,reject)=>{lines.once('line',line=>resolve(JSON.parse(line)));child.once('exit',code=>reject(Error('Fixture exited '+code)));});lines.close();
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1280,height:900}});
  const errors=[],external=[],mutations=[];
  await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==config.url){external.push('external');return route.abort();}return route.continue();});
  const page=await context.newPage();page.setDefaultTimeout(8000);page.on('pageerror',e=>errors.push(e.message));
  page.on('console',msg=>{if(msg.type()==='error' && /Content Security Policy|Refused to|Uncaught/.test(msg.text()))errors.push(msg.text());});
  page.on('request',r=>{if(r.headers()['x-editorial-action']==='delete_remote')mutations.push(r);});
  await page.goto(config.url+'/panel');await page.getByLabel('Senha').fill('synthetic-browser-publication-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();await page.locator('#messages').waitFor();
  await page.goto(config.url+'/editorial/#history');
  const row=page.locator('#history-list .item').filter({hasText:'Excluir remoto sintético 0'});
  const open=()=>row.getByRole('button',{name:'Excluir',exact:true}).click();
  const observe=async()=>await (await page.request.get(config.url+'/__delete_observe')).json();
  const state=async()=>await (await page.request.get(config.url+'/editorial/api/state')).json();
  await open();assert.equal(await page.locator('#delete-local').isChecked(),true);
  await page.locator('#cancel-delete').click();assert.equal((await observe()).calls.length,0);
  await open();await page.locator('#delete-remote').check();
  assert.equal(await page.locator('#confirm-delete').isDisabled(),true);
  assert((await page.locator('#delete-description').innerText()).includes('@umdoislab'));
  await page.locator('#delete-remote-confirm').check();assert.equal(await page.locator('#confirm-delete').isDisabled(),false);
  for(const width of [320,360,390]){
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow at ${width}`);
    const bounds=await page.locator('#delete-dialog').boundingBox();assert.ok(bounds.x>=0 && bounds.x+bounds.width<=width+1);
    for(const target of ['#delete-scope label','#delete-remote-confirm-option','#confirm-delete']){
      const b=await page.locator(target).first().boundingBox();assert.ok(b.height>=44,target);
    }
    if(width===320 && process.env.IG_EVIDENCE_DIR)await page.screenshot({path:path.join(process.env.IG_EVIDENCE_DIR,'remote-delete-mobile-320.png')});
  }
  await page.emulateMedia({reducedMotion:'reduce'});await page.setViewportSize({width:1280,height:900});
  await page.request.get(config.url+'/__delete_refuse');await page.locator('#confirm-delete').click();
  await page.locator('#delete-feedback').filter({hasText:'recusou a exclusão'}).waitFor();
  assert.equal(await page.locator('#delete-dialog').evaluate(d=>d.open),true);
  assert.equal((await state()).posts.filter(p=>p.caption==='Excluir remoto sintético 0').length,1);
  assert.equal((await observe()).calls.length,1);
  await page.request.get(config.url+'/__delete_allow');
  let release,seen;
  const waiting=new Promise(resolve=>seen=resolve),held=new Promise(resolve=>release=resolve);
  await page.route('**/editorial/api/posts/*/approve',async route=>{if(route.request().headers()['x-editorial-action']==='delete_remote'){seen();await held;}await route.continue();},{times:1});
  await page.locator('#confirm-delete').click();await waiting;
  assert.equal(await page.locator('#confirm-delete').isDisabled(),true);
  assert.equal(await page.locator('#delete-remote').isDisabled(),true);
  await page.locator('#confirm-delete').evaluate(button=>button.click());release();
  await page.waitForFunction(()=>!document.getElementById('delete-dialog').open);
  assert.equal((await observe()).calls.length,2);assert.equal(mutations.length,2);
  assert.equal((await state()).posts.filter(p=>p.caption==='Excluir remoto sintético 0').length,0);
  assert.equal((await state()).media.length,1,'shared media must remain');
  // Local mode on a published record must not issue any DELETE to the provider.
  await page.locator('#history-list .item').filter({hasText:'Excluir remoto sintético 1'}).getByRole('button',{name:'Excluir',exact:true}).click();
  await page.locator('#confirm-delete').click();await page.waitForFunction(()=>!document.getElementById('delete-dialog').open);
  assert.equal((await observe()).calls.length,2);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  console.log('PASS remote/local deletion, cancel, explicit account confirmation, 320/360/390x844, 44px targets, reduced motion, provider refusal preserves post, busy duplicate guard, shared media, CSP and zero external calls');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close();if(child && child.exitCode===null){const done=new Promise(resolve=>child.once('exit',resolve));child.kill();await done;}
  fs.rmSync(root,{recursive:true,force:true});
});
