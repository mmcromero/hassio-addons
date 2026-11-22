const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),readline=require('node:readline');
const assert=require('node:assert/strict');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'ig-publication-'));
let child,browser;
(async()=>{
  child=spawn('python3',[path.join(__dirname,'publication_browser_fixture.py'),root],{stdio:['ignore','pipe','inherit'],env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
  const lines=readline.createInterface({input:child.stdout});
  const config=await Promise.race([new Promise((resolve,reject)=>{lines.once('line',line=>{try{resolve(JSON.parse(line));}catch(e){reject(e);}});child.once('exit',code=>reject(Error('Fixture exited '+code)));}),new Promise((_,reject)=>setTimeout(()=>reject(Error('Fixture timeout')),10000).unref())]);
  lines.close();
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1440,height:1050},timezoneId:'America/Sao_Paulo'});
  const errors=[],blocked=[],publishRequests=[];
  await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==config.url){blocked.push(route.request().url());return route.abort();}return route.continue();});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.headers()['x-editorial-action']==='publish')publishRequests.push(r.url());});
  await page.goto(config.url+'/panel');await page.getByLabel('Senha').fill('synthetic-browser-publication-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  for(const [prefix,user] of [['','umdoislab'],['/accounts/'+config.second,'second_account']]){
    await page.goto(config.url+prefix+'/editorial/');
    await page.getByRole('button',{name:'Verificar publicação',exact:true}).click();
    await page.getByText('Token e permissão de publicação conferidos para esta conta.',{exact:true}).waitFor();
    await page.locator('[data-view="approval"]').click();
    if(!prefix)await page.getByRole('button',{name:'Confirmar envio agendado',exact:true}).waitFor();
    await page.getByRole('button',{name:'Publicar agora',exact:true}).click();
    await page.locator('#publish-dialog').waitFor({state:'visible'});
    assert.equal(await page.locator('#publish-account').innerText(),'Conta de destino: @'+user);
    await page.getByRole('button',{name:'Confirmar publicação',exact:true}).click();
    await page.locator('#approval-list .chip.published').waitFor({timeout:18000});
    assert.equal(await page.getByRole('link',{name:'Ver no Instagram',exact:true}).count(),1);
    console.log('PASS browser publication: explicit confirmation, progress and published result for @'+user);
  }
  const response=await page.request.get(config.url+'/__publication_test');const result=await response.json();
  assert.equal(result.published.length,2);assert.equal(new Set(result.published.map(x=>x[0])).size,2);
  assert.equal(publishRequests.length,2);assert.equal(blocked.length,0);assert.deepEqual(errors,[]);
  await page.goto(config.url+'/editorial/');await page.locator('[data-view="approval"]').click();
  assert.equal(await page.getByRole('button',{name:'Confirmar envio agendado',exact:true}).count(),1);
  const evidence=process.env.IG_EVIDENCE_DIR || root;fs.mkdirSync(evidence,{recursive:true});
  await page.screenshot({path:path.join(evidence,'publication-accounts.png'),fullPage:true});
  console.log('PASS old schedule remained inactive; two accounts published once; no external requests or browser errors');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close();if(child && child.exitCode===null){const done=new Promise(resolve=>child.once('exit',resolve));child.kill('SIGTERM');await done;}
  fs.rmSync(root,{recursive:true,force:true});
});
