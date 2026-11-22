/* Only loopback, synthetic photos/accounts. Never loads the real Central or Meta. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),readline=require('node:readline');
const assert=require('node:assert/strict');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'ig-avatar-'));
let child,browser;
(async()=>{
  child=spawn('python3',[path.join(__dirname,'publication_browser_fixture.py'),root,'--avatars'],{stdio:['ignore','pipe','inherit'],env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
  const lines=readline.createInterface({input:child.stdout});
  const config=await new Promise((resolve,reject)=>{lines.once('line',line=>resolve(JSON.parse(line)));child.once('exit',code=>reject(Error('Fixture exited '+code)));});lines.close();
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1280,height:900}});
  const errors=[],blocked=[];
  await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==config.url){blocked.push(route.request().url());return route.abort();}return route.continue();});
  const page=await context.newPage();page.setDefaultTimeout(8000);page.on('pageerror',e=>errors.push(e.message));
  page.on('console',msg=>{if(msg.type()==='error' && /Content Security Policy|Refused to|Uncaught/.test(msg.text()))errors.push(msg.text());});
  await page.goto(config.url+'/panel');await page.getByLabel('Senha').fill('synthetic-browser-publication-password');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();await page.locator('#messages').waitFor();
  const summary=page.locator('.ui-visual-account-picker summary'),picker=page.locator('.ui-visual-account-picker');
  await summary.waitFor();assert.equal(await page.locator('[data-native-account-picker]').isVisible(),false);
  await page.waitForFunction(()=>document.querySelector('summary img').naturalWidth===96);
  // Native details provides keyboard Enter/Space; links remain normal Tab targets.
  await summary.focus();await page.keyboard.press('Enter');assert.equal(await picker.getAttribute('open'),'');
  await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>document.activeElement.hasAttribute('data-account-link')),true);
  await page.keyboard.press('Escape');assert.equal(await picker.getAttribute('open'),null);assert.equal(await summary.evaluate(el=>el===document.activeElement),true);
  await summary.click();await page.locator('.crumb').click();assert.equal(await picker.getAttribute('open'),null);
  const second=await page.locator('[data-account-link]').nth(1).getAttribute('href');
  await summary.click();await page.locator('[data-account-link]').nth(1).click();await page.waitForURL(config.url+second);
  await page.waitForFunction(()=>document.querySelector('summary img').hidden);
  assert.ok((await summary.innerText()).includes('Segunda conta'));
  // Settings and Editorial destinations preserve each account, including local view.
  await page.goto(config.url+'/editorial/#approval');await summary.waitFor();await summary.click();
  const editorial=await page.locator('[data-account-link]').nth(1).getAttribute('href');
  await page.locator('[data-account-link]').nth(1).click();await page.waitForURL(config.url+editorial+'#approval');
  await page.goto(config.url+'/accounts');
  for(const width of [320,360,390]){
    await page.setViewportSize({width,height:844});await summary.click();
    await page.locator('[data-account-link] strong').nth(1).evaluate(el=>el.textContent='Conta com nome muito longo para identificação visual acessível');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`horizontal overflow at ${width}`);
    for(const selector of ['.ui-visual-account-picker summary','.ui-visual-account-picker nav','[data-account-link]']){
      const bounds=await page.locator(selector).first().boundingBox();assert.ok(bounds.x>=0 && bounds.x+bounds.width<=width+1,selector+' at '+width);
    }
    await page.screenshot({path:path.join(root,`avatar-${width}.png`)});
    await page.keyboard.press('Escape');
  }
  await page.emulateMedia({reducedMotion:'reduce'});await summary.focus();await page.keyboard.press('Space');await page.keyboard.press('Escape');
  // No JavaScript: native details and ordinary links still switch accounts.
  const nojs=await browser.newContext({javaScriptEnabled:false,storageState:await context.storageState()});
  const fallback=await nojs.newPage();await fallback.goto(config.url+'/accounts');
  assert.equal(await fallback.locator('.ui-visual-account-picker').isVisible(),true);
  await fallback.locator('.ui-visual-account-picker summary').click();
  await fallback.locator('[data-account-link]').nth(1).click();
  assert.ok(fallback.url().includes('/accounts?account='));
  assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
  console.log(JSON.stringify({status:'PASS',checks:['photo','missing-photo initials','keyboard','escape/outside','account navigation','Editorial hash','320/360/390','reduced motion','no-JS native links','CSP'],screenshots:root}));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(child)child.kill();});
