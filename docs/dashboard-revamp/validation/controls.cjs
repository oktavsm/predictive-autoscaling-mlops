// Run against a local mock API only; never use this action suite on production.
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const results=[];
const output=process.env.QA_OUTPUT || '/tmp/titipin-ui-qa';
fs.mkdirSync(output,{recursive:true});
const checks=(pass,label)=>{assert.ok(pass,label);results.push(label)};
const mock='http://127.0.0.1:18766';
async function state(value){await fetch(`${mock}/__state?value=${value}`)}
async function calls(){return (await(await fetch(`${mock}/__calls`)).json()).filter(c=>c.method==='POST')}
async function settle(page,title){
 await page.waitForTimeout(650);
 await page.getByRole('heading',{name:title,exact:true}).waitFor();
 await page.waitForFunction(()=>document.querySelector('[data-testid="stApp"]')?.getAttribute('data-test-script-state')==='notRunning');
 await page.waitForFunction(()=>![...document.querySelectorAll('[data-stale="true"]')].some(e=>e.getBoundingClientRect().width));
 await page.waitForTimeout(250);
}
async function select(page,title){
 await page.waitForTimeout(350);
 const option=page.getByTestId('stSidebar').getByText(title,{exact:true});
 if(!await option.isVisible())await page.getByTestId('stExpandSidebarButton').click();
 await option.click();await settle(page,title);
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH || '/home/oktaavsm/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome'});
 const context=await browser.newContext({viewport:{width:1448,height:1086},colorScheme:'dark'});
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await state('ready');await page.goto('http://127.0.0.1:18765');await settle(page,'Overview');
 await page.getByText('Auto-refresh',{exact:true}).click();await settle(page,'Overview');
 const pages=['Scaling Simulator','Drift & Retraining','Model Registry','Cluster Architecture','HPA vs Predictive','Telemetry Audit','FinOps & Carbon','Workload Injector'];
 for(const theme of ['dark','light']){
  await page.setViewportSize({width:1448,height:1086});await page.waitForTimeout(350);
  await page.getByRole('button',{name:'Main menu'}).click();
  await page.getByTestId('stMainMenuItem-theme-'+(theme==='dark'?'Dark':'Light')).click();await page.keyboard.press('Escape');
  if(await page.getByTestId('stSidebar').getAttribute('aria-expanded')==='false')await page.getByTestId('stExpandSidebarButton').click();
  await page.getByRole('button',{name:'Refresh now',exact:true}).click();
  await page.waitForFunction(expected=>getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()===expected,theme==='dark'?'#101418':'#F4F6F9');
  for(const title of pages){
   await page.setViewportSize({width:1448,height:1086});await select(page,title);
   checks(await page.getByTestId('stException').count()===0,`${theme} ${title}: no render exception`);
   checks(await page.getByTestId('stCaptionContainer').evaluateAll(es=>es.every(e=>getComputedStyle(e).opacity==='1')),`${theme} ${title}: captions preserve palette contrast without native opacity`);
   const text=await page.getByTestId('stMain').innerText();
   checks(!/\p{Extended_Pictographic}/u.test(text),`${theme} ${title}: no emoji in operational copy`);
   checks(await page.locator('.operation-title img[aria-hidden="true"][alt=""]').count()>0,`${theme} ${title}: local decorative SVG with text label`);
   for(const width of [1448,390,320]){
    await page.setViewportSize({width,height:1086});await page.waitForTimeout(250);
    checks(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${theme} ${title} ${width}px: no page overflow`);
    const panels=await page.locator('[class*="st-key-panel-"]').evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,right:r.right}}));
    checks(panels.every(r=>r.x>=-1&&r.right<=width+1),`${theme} ${title} ${width}px: panels inside viewport`);
    if(title==='Workload Injector'&&[1448,390].includes(width))await page.screenshot({path:`${output}/injector-${theme}-${width}.png`,fullPage:true});
   }
  }
 }
 checks((await calls()).length===0,'Workspace navigation, theme changes and resize never issue operational writes');
 await page.setViewportSize({width:1448,height:1086});await select(page,'Scaling Simulator');
 await page.getByRole('button',{name:'Flash sale (65 RPS)',exact:true}).click();await settle(page,'Scaling Simulator');
 await page.getByRole('button',{name:'Compute forecast',exact:true}).click();await page.getByTestId('stMetricValue').filter({hasText:'35.0 RPS'}).waitFor();await settle(page,'Scaling Simulator');
 checks((await calls()).at(-1).path==='/predict'&&(await calls()).at(-1).body.request_rate===65,'Preset and compute submit the selected telemetry');
 checks((await page.getByTestId('stMetricValue').allTextContents()).includes('35.0 RPS'),'Simulator renders acknowledged model output');
 await state('write_error');await page.getByRole('button',{name:'Compute forecast',exact:true}).click();await page.getByTestId('stAlert').filter({hasText:'No success was confirmed'}).waitFor();await settle(page,'Scaling Simulator');
 checks(await page.getByTestId('stAlert').filter({hasText:'No success was confirmed'}).isVisible(),'Prediction HTTP failure is visible');
 checks(await page.getByTestId('stMetricValue').count()===0,'Prediction failure removes previous result');
 await state('ready');await select(page,'Workload Injector');
 for(const label of ['steady normal','rush hour','flash sale','cooling down','quiet night','drift anomaly']){
  const before=(await calls()).length;
  await page.getByRole('button',{name:`Request ${label}`,exact:true}).click();await page.getByText('execution is not yet confirmed.',{exact:false}).waitFor();await settle(page,'Workload Injector');
  checks((await calls()).length===before+1,`${label}: one write per explicit click`);
  checks(await page.getByText('execution is not yet confirmed.',{exact:false}).count()===1,`${label}: acknowledgement is separate from execution`);
 }
 checks(await page.getByRole('button',{name:'Request drift anomaly',exact:true}).isEnabled(),'All six traffic profiles are available');
 await state('write_error');await page.getByRole('button',{name:'Request rush hour',exact:true}).click();await page.getByTestId('stAlert').filter({hasText:'No success was confirmed'}).waitFor();await settle(page,'Workload Injector');
 checks(await page.getByTestId('stAlert').filter({hasText:'No success was confirmed'}).isVisible(),'Workload HTTP failure is visible');
 checks(await page.getByText('Request accepted:',{exact:false}).count()===0,'Failed request clears prior accepted feedback');
 await state('ready');await select(page,'Drift & Retraining');
 await page.getByRole('button',{name:'Evaluate telemetry drift (PSI)',exact:true}).click();await page.getByTestId('stMetricValue').filter({hasText:'0.0800'}).waitFor();await settle(page,'Drift & Retraining');
 checks((await page.getByTestId('stMetricValue').allTextContents()).includes('0.0800'),'Drift evaluate reads and displays the API score');
 await page.getByRole('button',{name:'Trigger Event-Driven Retraining Pipeline',exact:true}).click();await page.getByText('Training accepted:',{exact:false}).waitFor();await settle(page,'Drift & Retraining');
 checks((await calls()).at(-1).path==='/monitoring/retrain/trigger','Retraining sends explicit trigger');
 checks(!((await page.getByTestId('stMain').innerText()).includes('Training job completed and champion loaded')),'ACK does not claim completion');
 await state('completed');await page.getByRole('button',{name:'Refresh now',exact:true}).click();await settle(page,'Drift & Retraining');
 checks((await page.getByTestId('stMetricValue').allTextContents()).includes('qa-v8'),'Completion shows the verified champion');
 await state('ready');await select(page,'Workload Injector');
 await page.getByRole('button',{name:'Launch Autonomous Lifecycle Simulation',exact:true}).click();await page.getByRole('button',{name:'Stop Running Scenario',exact:true}).waitFor();await settle(page,'Workload Injector');
 checks((await calls()).at(-1).path==='/monitoring/autonomous-scenario/start','Lifecycle start sends explicit trigger');
 await page.getByRole('button',{name:'Stop Running Scenario',exact:true}).click();await page.getByRole('button',{name:'Launch Autonomous Lifecycle Simulation',exact:true}).waitFor();await settle(page,'Workload Injector');
 checks((await calls()).at(-1).path==='/monitoring/autonomous-scenario/stop','Lifecycle stop sends explicit cancellation');
 await select(page,'Model Registry');
 checks(await page.getByTestId('stJson').count()===0,'Registry uses readable cards and tables');
 const links={'Open MLflow registry':'https://mlflow.titipin.me'};
 for(const [name,href] of Object.entries(links))checks(await page.getByRole('link',{name,exact:true}).getAttribute('href')===href,`${name}: configured URL`);
 await select(page,'HPA vs Predictive');checks(await page.getByRole('link',{name:'Inspect telemetry in Grafana',exact:true}).getAttribute('href')==='https://grafana.titipin.me','Benchmark source link opens configured Grafana');
 await select(page,'Workload Injector');
 await page.getByRole('button',{name:'Request rush hour',exact:true}).focus();await page.keyboard.press('Enter');await settle(page,'Workload Injector');
 checks((await calls()).at(-1).body.state==='BURST_BUSY','Injector supports keyboard activation');
 const reads=async()=>{const log=await(await fetch(`${mock}/__calls`)).json();return log.filter(c=>c.method==='GET'&&c.path==='/workload/status').length};
 const stopped=await reads();await page.waitForTimeout(3200);
 checks(await reads()===stopped,'Injector respects Auto-refresh off (no fixed two-second poll)');
 await page.getByText('Auto-refresh',{exact:true}).click();await settle(page,'Workload Injector');
 await page.getByTestId('stSlider').filter({hasText:'Read interval'}).locator('input[type="range"]').press('Home');await settle(page,'Workload Injector');
 const running=await reads();await page.waitForTimeout(6200);await settle(page,'Workload Injector');
 checks(await reads()>running,'Injector polls at the selected five-second read interval');
 await page.getByText('Auto-refresh',{exact:true}).click();await settle(page,'Workload Injector');
 const paused=await reads();await page.waitForTimeout(6200);
 checks(await reads()===paused,'Disabling Auto-refresh stops subsequent injector polling');
 checks(errors.length===0,'No browser JavaScript errors');
 fs.mkdirSync(output,{recursive:true});fs.writeFileSync(`${output}/controls.json`,JSON.stringify({checked_at:new Date().toISOString(),checks:results.length,results,errors,source:'Local mock API; no production actions'},null,2));
 console.log(`PASS ${results.length} browser assertions`);await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
