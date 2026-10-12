const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname,'..');
const url = require('node:url').pathToFileURL(path.join(root,'index.html')).href;
const results=[];
function check(pass,label){assert.ok(pass,label);results.push({passed:true,check:label});}
async function settle(page){await page.evaluate(()=>document.fonts.ready);await page.waitForFunction(()=>document.getElementById('overview').hidden || document.querySelector('#forecast-chart svg'));await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));}
(async()=>{
 const browser=await chromium.launch({headless:true});
 const errors=[],requests=[];
 const context=await browser.newContext({acceptDownloads:true,reducedMotion:'reduce'});
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
 for(const width of [1448,1024,768,390,320]){
  await page.setViewportSize({width,height:1086});await page.goto(url);await settle(page);
  for(const theme of ['dark','light']){
   await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
   for(const view of ['overview','lab-controls']){
    await page.evaluate(view=>location.hash='#'+view,view);await page.waitForFunction(view=>!document.getElementById(view).hidden,view);await settle(page);
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${width}px ${theme} ${view}: no page overflow`);
    check(await page.evaluate(()=>Array.from(document.querySelectorAll('.view:not([hidden]) .panel')).every(e=>e.scrollHeight<=e.clientHeight+2)),`${width}px ${theme} ${view}: panels contain their content`);
    check(await page.evaluate(()=>Array.from(document.querySelectorAll('.view:not([hidden]) button')).every(b=>b.getAttribute('aria-label')||b.textContent.trim())),`${width}px ${theme} ${view}: all buttons named`);
    if(view==='overview')check(await page.locator('#forecast-chart svg').count()===1,`${width}px ${theme}: actual chart rendered`);
    const capture=(width===1448&&view==='overview')||(width===390&&view==='overview')||(theme==='dark'&&view==='lab-controls'&&[1448,390].includes(width));
    if(capture){const preview=await context.newPage();preview.on('pageerror',e=>errors.push(e.message));preview.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});await preview.setViewportSize({width,height:1086});await preview.goto(url+'#'+view);await preview.evaluate(theme=>{document.documentElement.dataset.theme=theme;document.querySelector('#theme-toggle span').textContent=theme==='dark'?'Light theme':'Dark theme';},theme);await settle(preview);await preview.screenshot({path:path.join(root,'previews',`${view==='overview'?'overview':'showcase'}-${theme}-${width===1448?'desktop':'mobile'}.png`),fullPage:true});await preview.close();}
   }
  }
 }
 await page.setViewportSize({width:1448,height:1086});await page.goto(url);await settle(page);
 await page.evaluate(()=>{document.body.tabIndex=-1;document.body.focus()});await page.keyboard.press('Tab');check(await page.locator('.skip-link').evaluate(e=>e===document.activeElement),'Keyboard first Tab reaches skip link');await page.keyboard.press('Enter');check(await page.locator('#main').evaluate(e=>e===document.activeElement),'Skip link moves focus to main');
 for(const hash of ['overview','autoscaling','model-lifecycle','infrastructure','evaluation','activity-audit','lab-controls']){const nav=page.locator(`#navigation a[href="#${hash}"]`);await nav.click();await page.locator('#'+hash).waitFor({state:'visible'});check(await page.locator('#'+hash).isVisible(),`${hash} navigation resolves to actual visible section`);}
 await page.locator('#navigation a[href="#overview"]').click();await page.waitForFunction(()=>!document.getElementById('overview').hidden);
 for(let i=0;i<4;i++){const card=page.locator('.metric-card').nth(i),href=await card.getAttribute('href');await card.click();check(await page.locator(href).isVisible(),`Metric card ${i+1} navigates to relevant panel`);await page.locator('#navigation a[href="#overview"]').click();}
 const geometry=await page.evaluate(()=>{const box=s=>{const r=document.querySelector(s).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}};return {sidebar:box('.sidebar'),forecast:box('.forecast-panel'),scaling:box('.scaling-panel'),health:box('.health-panel'),cluster:box('.cluster-panel'),events:box('.events-panel')};});
 check(geometry.sidebar.width===238,'Reference: 238px sidebar');
 check(geometry.forecast.height===314&&geometry.scaling.height===320,'Reference: forecast/scaling height 314/320px');
 check(geometry.health.x>geometry.forecast.x&&geometry.cluster.y>geometry.health.y&&geometry.events.y>geometry.cluster.y,'Reference: health/cluster/events in right column');
 check(Math.abs(geometry.forecast.width/geometry.health.width-1.78)<.02,'Reference: monitoring column ratio 1.78');
 for(const key of ['environment','forecast','scaling','model','cluster','events','decision','slo']){
  const trigger=page.locator(`#overview [data-detail="${key}"]`).first();await trigger.click();await page.waitForFunction(()=>document.getElementById('detail-dialog').open);
  check(await page.evaluate(()=>document.getElementById('detail-dialog').contains(document.activeElement)),`${key} modal receives focus`);
  await page.keyboard.press('Tab');check(await page.evaluate(()=>document.getElementById('detail-dialog').contains(document.activeElement)),`${key} modal retains keyboard focus`);
  await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.getElementById('detail-dialog').open);
  check(await trigger.evaluate(e=>e===document.activeElement),`${key} modal Escape restores trigger focus`);
 }
 for(let i=0;i<3;i++){await page.locator('.nodes button').nth(i).click();check((await page.locator('#dialog-title').innerText()).includes('cluster'),`Node ${i+1} opens census details`);await page.locator('#dialog-close').click();check(await page.locator('#detail-dialog').evaluate(e=>!e.open),'Dialog close button works');}
 for(const [minutes,count] of [['15',61],['30',121],['60',241]]){
  await page.selectOption('#time-window',minutes);await page.locator('[data-detail="forecast"]').first().click();
  check((await page.locator('#dialog-content').innerText()).includes(`${count} synthetic samples over ${minutes} minutes`),`${minutes}m selector filters real fixture rows`);
  await page.keyboard.press('Escape');
 }
 await page.locator('#refresh').click();check((await page.locator('#toast').innerText()).includes('still frozen'),'Replay does not imply live data');
 const downloadPromise=page.waitForEvent('download');await page.locator('#export').click();const download=await downloadPromise;const csv=fs.readFileSync(await download.path(),'utf8').trim().split('\n');
 check(csv.length===242&&csv[0].startsWith('synthetic,issued_at_utc,target_at_utc'),'CSV contains header plus 241 rows and source/target columns');
 check(csv.slice(1).every(line=>line.startsWith('true,')),'All exported telemetry rows labeled synthetic');
 check(csv.slice(1).every(line=>{const cells=line.split(',');return Date.parse(cells[2])-Date.parse(cells[1])===60000;}),'CSV forecast target is issue plus 60 seconds');
 await page.locator('#theme-toggle').click();check(await page.evaluate(()=>document.documentElement.dataset.theme==='light'),'Overview theme control switches theme');
 await page.locator('a[href="#lab-controls"]').last().click();await page.waitForFunction(()=>!document.getElementById('lab-controls').hidden);
 await page.locator('#showcase-theme').click();check(await page.evaluate(()=>document.documentElement.dataset.theme==='dark'),'Showcase theme control switches theme');
 await page.locator('#copy-policy').click();await page.waitForFunction(()=>document.getElementById('detail-dialog').open||document.getElementById('toast').textContent.includes('policy copied'));check(await page.evaluate(()=>document.getElementById('detail-dialog').open||document.getElementById('toast').textContent.includes('policy copied')),'Copy demo policy writes clipboard or opens explicit selectable fallback');if(await page.locator('#detail-dialog').evaluate(e=>e.open))await page.keyboard.press('Escape');
 const showcaseDownload=page.waitForEvent('download');await page.locator('#showcase-export').click();check((await showcaseDownload).suggestedFilename()==='titipin-synthetic-telemetry.csv','Showcase export downloads synthetic CSV');
 for(const value of ['', '-1', '2.5', '1001']){await page.fill('#capacity',value);await page.locator('#policy-form button').click();check(await page.locator('#capacity').getAttribute('aria-invalid')==='true'&&await page.locator('#capacity-error').isVisible(),`Capacity ${JSON.stringify(value)} gets inline validation`);}
 await page.fill('#capacity','25');await page.locator('#policy-form button').click();check((await page.locator('#policy-output').innerText()).includes('clamped to demo maximum 8'),'Local preview respects demo bounds');
 await page.fill('#capacity','65');await page.locator('#policy-form button').click();check((await page.locator('#policy-output').innerText()).includes('4 replicas'),'Valid capacity preview calculation');
 for(const state of ['loading','empty','error','stale','unknown','ready']){await page.selectOption('#state-select',state);check((await page.locator('#state-example').innerText()).length>20,`${state} state has useful explanation`);if(state==='loading')check(await page.locator('#state-example').getAttribute('aria-busy')==='true','Loading state exposes busy semantics');}
 await page.selectOption('#state-select','error');await page.locator('#retry-state').click();check(await page.locator('#state-select').inputValue()==='ready','Retry demo returns to ready locally');
 await page.setViewportSize({width:390,height:844});await page.goto(url+'#overview');await settle(page);await page.locator('#menu-toggle').click();check(await page.locator('#menu-toggle').getAttribute('aria-expanded')==='true','Mobile menu exposes expanded state');
 await page.locator('#navigation a[href="#overview"]').click();check(await page.locator('#menu-toggle').getAttribute('aria-expanded')==='false','Selecting current section closes mobile menu');
 await page.locator('#menu-toggle').click();await page.locator('#navigation a[href="#lab-controls"]').click();await page.waitForFunction(()=>!document.getElementById('lab-controls').hidden);check(await page.locator('#menu-toggle').getAttribute('aria-expanded')==='false','Mobile navigation changes view and closes');
 await page.locator('a[href="#overview"]').last().click();await page.waitForFunction(()=>!document.getElementById('overview').hidden);
 await page.locator('#menu-toggle').focus();await page.keyboard.press('Enter');await page.keyboard.press('Escape');check(await page.locator('#menu-toggle').getAttribute('aria-expanded')==='false','Keyboard Enter/Escape operates mobile menu');
 check(await page.locator('#menu-toggle').evaluate(e=>getComputedStyle(e).outlineStyle!=='none'),'Keyboard focus indicator visible');
 check(await page.locator('#overview button').evaluateAll(es=>es.filter(e=>e.getClientRects().length).every(e=>{const r=e.getBoundingClientRect();return r.height>=44&&r.width>=44;})),'Mobile Overview buttons meet 44px touch targets');
 for(const width of [1448,320]){
  await page.setViewportSize({width,height:1086});await page.evaluate(()=>document.documentElement.style.fontSize='32px');await page.waitForFunction(()=>document.documentElement.classList.contains('large-type'));await settle(page);
  for(const view of ['overview','lab-controls']){await page.evaluate(view=>location.hash='#'+view,view);await page.waitForFunction(view=>!document.getElementById(view).hidden,view);await settle(page);check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${width}px ${view}: 200% text no page overflow`);check(await page.evaluate(()=>Array.from(document.querySelectorAll('.view:not([hidden]) .panel')).every(e=>e.scrollHeight<=e.clientHeight+2)),`${width}px ${view}: 200% text not clipped in panels`);}
  await page.evaluate(()=>document.documentElement.style.fontSize='');
 }
 check(errors.length===0,'No browser JavaScript errors');check(requests.length===0,'No HTTP requests: offline artifact');
 fs.writeFileSync(path.join(root,'qa/browser-validation.json'),JSON.stringify({version:'1.1.0',status:'PASS',checks:results.length,viewport_widths:[1448,1024,768,390,320],themes:['dark','light'],views:['overview','lab-controls'],geometry,errors,external_requests:requests,results},null,2)+'\n');
 await browser.close();console.log(`PASS: ${results.length} browser assertions, 20 viewport/theme/view combinations, 200% text, dialogs, menu, forms, states and CSV.`);
})().catch(error=>{console.error(error);process.exit(1)});
