const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const base=process.argv[2] || 'http://127.0.0.1:18765';
const output=process.argv[3] || '/tmp';
const live=process.argv.includes('--live');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH || '/home/oktaavsm/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome'});
 const page=await browser.newPage({viewport:{width:1600,height:1200},colorScheme:'dark',reducedMotion:'reduce'});
 const errors=[],writes=[],checks=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(['POST','PUT','PATCH','DELETE'].includes(r.method())&&!r.url().includes('_stcore'))writes.push(r.method()+' '+r.url())});
 function check(value,label){assert.ok(value,label);checks.push(label)}
 const root=page.locator('.cluster-explorer');
 async function settle(){await page.waitForTimeout(650);await page.waitForFunction(()=>document.querySelector('[data-testid="stApp"]')?.getAttribute('data-test-script-state')==='notRunning');await page.waitForFunction(()=>![...document.querySelectorAll('[data-stale="true"]')].some(e=>e.getBoundingClientRect().width));await root.locator('h2').first().waitFor();}
 async function refresh(){if(await page.getByTestId('stExpandSidebarButton').isVisible())await page.getByTestId('stExpandSidebarButton').click();await page.getByRole('button',{name:'Refresh now',exact:true}).click();await settle();}
 async function theme(name){await page.getByRole('button',{name:'Main menu',exact:true}).click();await page.getByTestId('stMainMenuItem-theme-'+name).click();await page.keyboard.press('Escape');await refresh();}
 await page.goto(base,{waitUntil:'domcontentloaded'});
 await page.getByRole('heading',{name:'Overview',exact:true}).waitFor();
 if(await page.getByTestId('stExpandSidebarButton').isVisible())await page.getByTestId('stExpandSidebarButton').click();
 await page.getByText('Auto-refresh',{exact:true}).click();
 await page.getByTestId('stSidebar').getByText('Cluster Architecture',{exact:true}).click();await settle();
 check(await root.locator('.node').count()===3,'three nodes from inventory');
 check((await root.innerText()).includes('not measured utilization'),'capacity is not utilization');
 check(await root.locator('.usage-meter').count()>0,'observed usage bars available');
 check((await root.innerText()).includes('CPU rate over 2 minutes'),'usage window and source labelled');
 check(await page.getByTestId('stException').count()===0,'no Streamlit exception');
 const first=root.locator('.node-head').first();
 await first.hover();check(await first.getByRole('tooltip').isVisible(),'node hover explanation');
 await first.focus();await page.keyboard.press('Escape');check(!await first.getByRole('tooltip').isVisible(),'Escape dismisses tooltip');
 await page.keyboard.press('Enter');check((await root.locator('.inspector').innerText()).includes('Kubelet'),'keyboard node selection opens runtime detail');
 const pod=root.locator('.pod').first();await pod.click();check((await root.locator('.inspector').innerText()).includes('Ready containers'),'pod selection opens container detail');
 check((await root.locator('.inspector').innerText()).includes('Restarts'),'pod restart evidence');
 const more=root.locator('.more').first();if(await more.count()){const before=await root.locator('.pod').count();await more.click();check(await root.locator('.pod').count()>before,'expand hidden pods');await root.getByRole('button',{name:'Show fewer pods',exact:true}).first().click();check(await root.locator('.pod').count()===before,'collapse pods');}
 for(const namespace of ['mlops','monitoring','titipin']){await root.locator(`[data-namespace="${namespace}"]`).click();const labels=await root.locator('.pod-meta').allInnerTexts();check(labels.every(t=>t.startsWith(namespace+' ·')),namespace+' filter');}
 await root.locator('[data-namespace="All"]').click();
 await root.getByRole('searchbox',{name:'Search cluster'}).fill('no-matching-component');check((await root.innerText()).includes('No nodes or pods match'),'search empty state');
 await root.getByRole('searchbox',{name:'Search cluster'}).fill('');
 if(!live){
  check(!await page.evaluate(()=>window.clusterInjected),'inventory HTML is not executable');
  await root.getByRole('button',{name:'<img src=x onerror=window.clusterInjected=true>',exact:true}).click();
  check((await root.locator('.inspector h2').innerText()).includes('<img'),'hostile name is literal text');
  check((await root.locator('.inspector').innerText()).includes('Unscheduled'),'unscheduled pod explicit');
  await root.getByRole('searchbox',{name:'Search cluster'}).fill('drift-retrain-qa');await root.locator('[data-select="pod:mlops/drift-retrain-qa"]').first().click();check((await root.locator('.inspector').innerText()).includes('Completed'),'completed job is distinct from ready');await root.getByRole('searchbox',{name:'Search cluster'}).fill('');
 }
 await root.getByRole('button',{name:'System flow',exact:true}).click();
 for(const flow of ['serving','training','observability']){
  await root.locator(`[data-flow="${flow}"]`).click();
  const buttons=root.locator('.system');
  for(let i=0;i<await buttons.count();i++){
   const id=await buttons.nth(i).getAttribute('data-component');await buttons.nth(i).click();
   check((await root.locator('.inspector').innerText()).includes('What to investigate'),flow+'/'+id+' explanation');
   check(await root.locator('.edge.active').count()>0,flow+'/'+id+' highlighted edges');
  }
 }
 await root.locator('[data-flow="serving"]').click();
 await root.locator('[data-component="caddy"]').hover();check(await root.locator('#tip-caddy').isVisible(),'system hover explanation');
 await root.locator('[data-component="caddy"]').click();check((await root.locator('.inspector').innerText()).includes('Configured · not probed'),'host service is not invented healthy');
 await root.locator('[data-component="inference"]').click();
 check(await root.locator('.inspect-link').getAttribute('href')==='https://model.titipin.me/docs','service link destination');
 if(!live)check((await root.locator('.inspector').innerText()).includes('30800'),'observed NodePort');
 await refresh();check(await root.locator('[data-view="flow"]').getAttribute('aria-pressed')==='true','view survives refresh');
 check(await root.locator('[data-component="inference"]').getAttribute('aria-pressed')==='true','selection survives refresh');
 for(const mode of ['Dark','Light']){
  await page.setViewportSize({width:1600,height:1200});await page.waitForTimeout(350);
  await theme(mode);
  check(await root.evaluate(e=>getComputedStyle(e).getPropertyValue('--bg').trim())===(mode==='Dark'?'#101418':'#F4F6F9'),mode+' component tokens');
  for(const view of ['flow','placement']){
   await root.locator(`[data-view="${view}"]`).click();
   for(const width of [1600,1024,390,320]){
    await page.setViewportSize({width,height:width<500?844:1200});await page.waitForTimeout(150);
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${mode}/${view}/${width} page overflow`);
    check(await root.evaluate(e=>e.scrollWidth<=e.clientWidth+1),`${mode}/${view}/${width} component overflow`);
    if(width===1600 || width===390){await page.mouse.move(0,0);await root.evaluate(e=>e.scrollIntoView({block:'start'}));await page.screenshot({path:`${output}/cluster-${live?'live':'qa'}-${mode.toLowerCase()}-${view}-${width}.png`,fullPage:true});}
   }
  }
 }
 await root.evaluate(e=>{e.style.fontSize='200%'});check(await root.evaluate(e=>e.scrollWidth<=e.clientWidth+1),'320px enlarged root text does not overflow');
 await page.setViewportSize({width:1600,height:1200});
 if(!live){
  for(const state of ['cluster_empty','cluster_error']){
   await page.request.get('http://127.0.0.1:18766/__state?value='+state);await refresh();
   check(await root.locator('.node').count()===0,state+' has no fabricated nodes');
   check((await root.innerText()).includes('Node inventory unavailable'),state+' explanation');
  }
  await page.request.get('http://127.0.0.1:18766/__state?value=usage_unavailable');await refresh();
  check(await root.locator('.usage-meter').count()===0,'missing usage does not become a zero percent bar');
  check((await root.innerText()).includes('CPU Unavailable'),'missing usage is explicit');
  await page.request.get('http://127.0.0.1:18766/__state?value=ready');await refresh();
  const calls=await(await page.request.get('http://127.0.0.1:18766/__calls')).json();check(calls.every(c=>c.method==='GET'),'component uses read-only sources');
 }
 check(errors.length===0,'no browser page errors');check(writes.length===0,'no operational browser writes');
 const result={base,checked_at:new Date().toISOString(),fixture:!live,checks,errors,writes};
 fs.writeFileSync(output+`/cluster-${live?'live':'qa'}.json`,JSON.stringify(result,null,2));console.log(checks.length+' checks passed');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
