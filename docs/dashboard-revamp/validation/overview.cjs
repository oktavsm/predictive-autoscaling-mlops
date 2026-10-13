const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const evidence='/tmp/titipin-ui-qa';
const checks=[];
function check(pass,label){assert.ok(pass,label);checks.push(label)}
async function settle(page){await page.getByText('Decision Summary',{exact:true}).waitFor({timeout:60000});await page.waitForFunction(()=>getComputedStyle(document.documentElement).getPropertyValue('--bg').trim());await page.evaluate(()=>document.fonts.ready);await page.waitForFunction(()=>![...document.querySelectorAll('[data-stale="true"]')].some(e=>e.getBoundingClientRect().width));await page.waitForTimeout(800)}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/home/oktaavsm/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome'});
 const context=await browser.newContext({viewport:{width:1448,height:1086},colorScheme:'dark'});
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await fetch('http://127.0.0.1:18766/__state?value=ready');
 await page.goto('http://127.0.0.1:18765');await settle(page);
 await page.getByText('Change the app menu theme, then Refresh now',{exact:false}).waitFor();await page.screenshot({path:evidence+'/initial.png',fullPage:true});
 await page.getByText('Auto-refresh',{exact:true}).click();await settle(page);
 for(const theme of ['dark','light']){
  await page.getByRole('button',{name:'Main menu'}).click();
  await page.getByTestId('stMainMenuItem-theme-'+(theme==='dark'?'Dark':'Light')).click();await page.keyboard.press('Escape');
  if(await page.getByTestId('stSidebar').getAttribute('aria-expanded')==='false')await page.getByTestId('stExpandSidebarButton').click();
  await page.getByRole('button',{name:'Refresh now',exact:true}).click();
  await page.waitForFunction(expected=>getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()===expected,theme==='dark'?'#101418':'#F4F6F9');
  await settle(page);await page.keyboard.press('Escape');
  for(const width of [1448,1024,768,390,320]){
   await page.setViewportSize({width,height:1086});await page.waitForTimeout(400);
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${width}px ${theme}: no page overflow`);
   const geometry=await page.locator('[class*="st-key-panel-"]').evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,right:r.right,width:r.width}}));
   check(geometry.every(r=>r.right<=width+1&&r.x>=-1),`${width}px ${theme}: all panels inside viewport`);
   const gridWidth=await page.locator('.st-key-overview-grid').evaluate(e=>e.getBoundingClientRect().width);
   if(width<1120)check(geometry.every(r=>r.width>=gridWidth-2),`${width}px ${theme}: panels stack at readable width`);
   check(await page.getByTestId('stVegaLiteChart').count()===2,`${width}px ${theme}: two evidence charts`);
   if([1448,320,390].includes(width))await page.screenshot({path:`${evidence}/overview-${theme}-${width}.png`,fullPage:true});
  }
 }
 await page.setViewportSize({width:1448,height:1086});
 await page.getByText('SLO Snapshot',{exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:evidence+'/overview-bottom-light.png',fullPage:true});
 if(await page.getByTestId('stSidebar').getAttribute('aria-expanded')==='false')await page.getByTestId('stExpandSidebarButton').click();
 await page.getByText('Inspect observations / export CSV',{exact:true}).click();
 check(await page.getByRole('button',{name:'Export observations CSV'}).isVisible(),'Observation inspector exposes export');
 const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Export observations CSV'}).click();
 const csv=fs.readFileSync(await(await downloaded).path(),'utf8').trim().split('\n');
 const header=csv[0].split(',');check(csv.length===61,'CSV exports all 60 validated records');
 const issued=header.indexOf('issued_at_utc'),target=header.indexOf('forecast_target_utc'),synthetic=header.indexOf('synthetic');
 check(csv.slice(1).every(row=>{const cells=row.split(',');return Date.parse(cells[target])-Date.parse(cells[issued])===60000&&cells[synthetic]==='True'}),'CSV retains synthetic provenance and +60s target time');
 await page.getByText('Inspect model provenance',{exact:true}).click();
 check(await page.getByText("Validation MAE is stored training metadata",{exact:false}).isVisible(),'Model provenance inspector works');
 await page.getByText('Inspect recorded operations',{exact:true}).click();
 check(await page.getByTestId('stDataFrame').count()===2,'Operation inspector exposes separate action records');
 await page.getByText('Connected services',{exact:true}).click();
 check(await page.getByRole('link',{name:'Grafana Observability'}).getAttribute('href')==='https://grafana.titipin.me','Service URL remains configured');
 await page.locator('.skip-link').focus();await page.keyboard.press('Enter');
 check(await page.locator('#workspace-title').evaluate(e=>e===document.activeElement),'Skip link moves keyboard focus to workspace title');
 await page.getByRole('button',{name:'Refresh now',exact:true}).focus();
 check(await page.getByRole('button',{name:'Refresh now',exact:true}).evaluate(e=>getComputedStyle(e).outlineStyle!=='none'),'Keyboard focus is visible');
 await page.keyboard.press('Enter');await settle(page);
 for(const state of ['empty','error','stale','invalid','partial']){
  await fetch('http://127.0.0.1:18766/__state?value='+state);
  await page.getByRole('button',{name:'Refresh now',exact:true}).click();await settle(page);
  const text=await page.locator('[data-testid="stMain"]').innerText();
  check(!text.includes('Traceback'),`${state}: renders without traceback`);
  if(['empty','error','invalid'].includes(state))check(await page.getByTestId('stVegaLiteChart').count()===0,`${state}: no fabricated charts`);
  else check(await page.getByTestId('stVegaLiteChart').count()===2,`${state}: valid charts remain visible`);
  await page.screenshot({path:`${evidence}/state-${state}.png`,fullPage:true});
  const calls=await(await fetch('http://127.0.0.1:18766/__calls')).json();
  check(calls.every(r=>r.method==='GET'&&['/health','/scaling/decisions','/scaling/actions','/operations/audit','/monitoring/drift'].includes(r.path)),`${state}: only approved read endpoints`);
 }
 await fetch('http://127.0.0.1:18766/__state?value=ready');await page.getByRole('button',{name:'Refresh now',exact:true}).click();await settle(page);
 await page.setViewportSize({width:320,height:1086});await page.evaluate(()=>document.documentElement.style.fontSize='32px');await page.waitForTimeout(500);
 check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'320px at 200% text: no page overflow');
 await page.screenshot({path:`${evidence}/large-text.png`,fullPage:true});
 check(errors.length===0,'No browser page errors');
 fs.writeFileSync(`${evidence}/validation.json`,JSON.stringify({checks:checks.length,results:checks,errors},null,2));
 console.log(`PASS ${checks.length} browser assertions`);
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
