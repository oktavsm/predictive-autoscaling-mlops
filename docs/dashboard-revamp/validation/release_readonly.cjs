const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const base=process.argv[2];
const output=process.argv[3];
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/home/oktaavsm/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome'});
 const page=await browser.newPage({viewport:{width:1448,height:1086},colorScheme:'dark'});
 const errors=[];const checks=[];const writes=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(['POST','PUT','PATCH','DELETE'].includes(r.method())&&!r.url().includes('_stcore'))writes.push(r.method()+' '+r.url())});
 async function settle(){await page.getByText('Decision Summary',{exact:true}).waitFor({timeout:90000});await page.waitForFunction(()=>getComputedStyle(document.documentElement).getPropertyValue('--bg').trim());await page.waitForFunction(()=>document.querySelector('[data-testid="stApp"]')?.getAttribute('data-test-script-state')==='notRunning');await page.waitForFunction(()=>![...document.querySelectorAll('[data-stale="true"]')].some(e=>e.getBoundingClientRect().width));await page.waitForTimeout(800);}
 function check(value,label){assert.ok(value,label);checks.push(label)}
 await page.goto(base,{waitUntil:'domcontentloaded',timeout:60000});await settle();
 if(await page.getByTestId('stExpandSidebarButton').isVisible())await page.getByTestId('stExpandSidebarButton').click();
 await page.waitForFunction(()=>document.querySelectorAll('[data-testid="stRadio"] input[type="radio"]').length===9);
 check(await page.title()==='Titipin MLOps','new application title');
 check(await page.getByRole('radio').count()===9,'nine workspace options');
 check(await page.getByTestId('stMetric').count()===4,'four live metrics');
 check(await page.getByTestId('stException').count()===0,'no Streamlit exception');
 await page.getByText('Auto-refresh',{exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('input[type="checkbox"]')?.checked===false);await settle();
 const charts=await page.getByTestId('stVegaLiteChart').count();
 const status=await page.locator('.status').first().innerText();
 check(charts===(['Recent observations','Stale observations'].includes(status)?2:0),'chart count matches source state');
 const metrics=await page.getByTestId('stMetricValue').allInnerTexts();
 await page.screenshot({path:output+'/production-dark-desktop.png',fullPage:true});
 await page.getByRole('button',{name:'Main menu',exact:true}).click();await page.getByTestId('stMainMenuItem-theme-Light').click();await page.keyboard.press('Escape');await page.getByRole('button',{name:'Refresh now',exact:true}).click();await settle();
 await page.waitForFunction(()=>getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()==='#F4F6F9',{timeout:30000});
 check(await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--bg').trim())==='#F4F6F9','light theme after refresh');
 await page.screenshot({path:output+'/production-light-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(400);
 check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'mobile no page overflow');
 await page.screenshot({path:output+'/production-light-mobile.png',fullPage:true});
 await page.setViewportSize({width:1448,height:1086});await page.waitForTimeout(500);
 for(const title of ['Scaling Simulator','Drift & Retraining','Model Registry','Cluster Architecture','HPA vs Predictive','Telemetry Audit','FinOps & Carbon','Workload Injector']){
  const option=page.getByTestId('stSidebar').getByText(title,{exact:true});
  if(!await option.isVisible())await page.getByTestId('stExpandSidebarButton').click();
  await option.click();await page.getByRole('heading',{name:title,exact:true}).waitFor();await page.waitForTimeout(700);
  await page.waitForFunction(()=>document.querySelector('[data-testid="stApp"]')?.getAttribute('data-test-script-state')==='notRunning');
  check(await page.getByTestId('stException').count()===0,title+': no render exception');
  check(await page.locator('.operation-title img').evaluateAll(es=>es.length>0&&es.every(e=>e.complete&&e.naturalWidth>0)),title+': kit SVG images loaded');
  check(!/\p{Extended_Pictographic}/u.test(await page.getByTestId('stMain').innerText()),title+': no decorative emoji');
 }
 check(await page.getByRole('button',{name:'Request drift anomaly',exact:true}).isDisabled(),'drift action visibly disabled');
 await page.screenshot({path:output+'/production-injector-light-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(400);
 check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'injector mobile no overflow');
 await page.screenshot({path:output+'/production-injector-light-mobile.png',fullPage:true});
 console.log('write targets',writes.map(item=>item.split('?')[0]));
 check(errors.length===0,'no browser page errors');check(writes.length===0,'no operational browser writes');
 const result={url:base,checked_at:new Date().toISOString(),checks,status,metrics,charts,errors,writes};
 fs.writeFileSync(output+'/browser-smoke.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));await browser.close();
})().catch(e=>{console.error(e.message);process.exit(1)});
