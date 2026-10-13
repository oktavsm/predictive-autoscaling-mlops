const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const base=process.argv[2]||'http://127.0.0.1:18765';
const output=process.argv[3]||'/tmp';
let token=process.argv[4]?fs.readFileSync(process.argv[4],'utf8').trim():'qa-operator';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/home/oktaavsm/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome'});
 const context=await browser.newContext({viewport:{width:1448,height:1086}});
 const page=await context.newPage();const checks=[],errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const check=(value,label)=>{assert.ok(value,label);checks.push(label)};
 async function settle(p){await p.waitForTimeout(600);await p.waitForFunction(()=>document.querySelector('[data-testid="stApp"]')?.getAttribute('data-test-script-state')==='notRunning');}
 async function simulator(p){await p.goto(base,{waitUntil:'domcontentloaded'});await p.getByRole('heading',{name:'Overview',exact:true}).waitFor();if(await p.getByTestId('stExpandSidebarButton').isVisible())await p.getByTestId('stExpandSidebarButton').click();await p.getByTestId('stSidebar').getByText('Scaling Simulator',{exact:true}).click();await settle(p);}
 await simulator(page);
 check(!await page.getByRole('button',{name:'Compute forecast',exact:true}).isEnabled(),'anonymous session write control locked');
 check(await page.getByLabel('Operator token',{exact:true}).getAttribute('type')==='password','credential input masked');
 await page.getByLabel('Operator token',{exact:true}).fill(token);
 await page.getByRole('button',{name:'Unlock operator access',exact:true}).click();await settle(page);
 await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Compute forecast'&&!b.disabled));
 check(await page.getByRole('button',{name:'Compute forecast',exact:true}).isEnabled(),'verified operator unlocks controls');
 const second=await context.newPage();await simulator(second);
 check(!await second.getByRole('button',{name:'Compute forecast',exact:true}).isEnabled(),'another tab cannot inherit operator credential');await second.close();
 await page.getByTestId('stSidebar').getByText('Cluster Architecture',{exact:true}).click();await settle(page);await page.locator('.cluster-explorer').waitFor();
 check(!((await page.locator('.cluster-explorer').innerHTML()).includes(token)),'credential excluded from cluster component');
 check(await page.evaluate(secret=>![...Object.values(localStorage),...Object.values(sessionStorage)].some(value=>value.includes(secret)),token),'credential absent from browser persistent storage');
 await page.getByTestId('stSidebar').getByText('Scaling Simulator',{exact:true}).click();await settle(page);
 if(!await page.getByRole('button',{name:'Lock operator access',exact:true}).isVisible())await page.getByText('Operator access',{exact:true}).click();
 await page.getByRole('button',{name:'Lock operator access',exact:true}).click();await settle(page);
 check(!await page.getByRole('button',{name:'Compute forecast',exact:true}).isEnabled(),'explicit lock revokes session write access');
 check(await page.getByLabel('Operator token',{exact:true}).inputValue()==='','lock clears credential input');
 if(base.includes('127.0.0.1')){
  await page.getByLabel('Operator token',{exact:true}).fill(token);await page.getByRole('button',{name:'Unlock operator access',exact:true}).click();await settle(page);
  await page.request.get('http://127.0.0.1:18766/__state?value=auth_expired');
  await page.getByRole('button',{name:'Compute forecast',exact:true}).click();await settle(page);
  check(!await page.getByRole('button',{name:'Compute forecast',exact:true}).isEnabled(),'rejected action immediately relocks controls');
  check(await page.getByLabel('Operator token',{exact:true}).inputValue()==='','rejected action clears credential input');
  check(await page.getByText('Operator access expired or was rejected. Unlock access again.',{exact:true}).isVisible(),'rejected credential has visible recovery feedback');
  await page.request.get('http://127.0.0.1:18766/__state?value=ready');
 }
 check(errors.length===0,'no browser errors');
 fs.writeFileSync(output+'/operator-'+(base.includes('127.0.0.1')?'qa':'live')+'.json',JSON.stringify({checked_at:new Date().toISOString(),base,checks,errors,scope:base.includes('127.0.0.1')?'Mock-only credential verification, session isolation/lock and rejected-action recovery.':'Only credential verification and local session lock; no forecast, traffic or training action.'},null,2));
 console.log(checks.length+' operator-session checks passed');await browser.close();token='';
})().catch(e=>{console.error(String(e.stack||e).split(token).join('[redacted]'));process.exit(1)});
