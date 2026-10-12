'use strict';
const fixture = JSON.parse(document.getElementById('fixture').textContent);
const $ = id => document.getElementById(id);
const time = (stamp, seconds=false) => new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Jakarta',hour:'2-digit',minute:'2-digit',...(seconds?{second:'2-digit'}:{})}).format(new Date(stamp));
const latest = fixture.rows.at(-1);
const number = value => Number(value).toLocaleString('en-US',{maximumFractionDigits:2});
const icon = name => `<svg aria-hidden="true"><use href="#icon-${name}"/></svg>`;
let toastTimer;
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4200);}
function visibleRows(){const cutoff=Date.parse(latest.timestamp)-Number($('time-window').value)*60000;return fixture.rows.filter(r=>Date.parse(r.timestamp)>=cutoff);}
const pt=(x,y)=>`${x.toFixed(2)},${y.toFixed(2)}`;
function frame(w,h,max,ticks,rows,historyEnd=w-10,left=34){
 const scale=parseFloat(getComputedStyle(document.documentElement).fontSize)/16;left*=scale;
 const top=24*scale,bottom=h-25*scale,y=v=>bottom-v/max*(bottom-top),x=i=>left+i/(rows.length-1)*(historyEnd-left);
 let content='';
 ticks.forEach(v=>{content+=`<line class="grid-line" x1="${left}" y1="${y(v)}" x2="${w-10}" y2="${y(v)}"/><text x="${left-9}" y="${y(v)+4}" text-anchor="end">${v}</text>`;});
 const count=w/scale<420?2:6;
 for(let i=0;i<=count;i++){const idx=Math.round(i/count*(rows.length-1));const xx=x(idx);content+=`<line class="grid-line" x1="${xx}" y1="${top}" x2="${xx}" y2="${bottom}"/><text x="${xx}" y="${h-5}" text-anchor="${i===0?'start':i===count?'end':'middle'}">${time(rows[idx].timestamp)}</text>`;}
 return {top,bottom,x,y,content};
}
function svg(w,h,content){return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" aria-hidden="true">${content}</svg>`;}
function drawForecast(){
 const el=$('forecast-chart'),w=el.clientWidth,h=el.clientHeight;if(!w)return;
 const rows=visibleRows(),end=w-Math.max(66,w*.16),{x,y,bottom,content}=frame(w,h,400,[0,100,200,300,400],rows,end);
 const line=rows.map((r,i)=>pt(x(i),y(r.actual_rps))).join(' ');
 const futureEnd=w-10, futureY=y(latest.prediction_for_plus_60s_rps);
 el.innerHTML=svg(w,h,content+`<polygon class="actual-area" points="${pt(x(0),bottom)} ${line} ${pt(end,bottom)}"/><polyline class="actual-stroke" points="${line}"/><line class="boundary" x1="${end}" x2="${end}" y1="21" y2="${bottom}"/><text class="annotation" x="${end-4}" y="14" text-anchor="end">Now</text><text class="annotation" x="${futureEnd}" y="14" text-anchor="end">+60s</text><path class="predicted-stroke" d="M${pt(end,y(latest.actual_rps))} L${pt(futureEnd,futureY)}"/><circle cx="${futureEnd}" cy="${futureY}" r="3" fill="var(--chart-predicted)"/><text x="${futureEnd}" y="${futureY-9}" text-anchor="end" class="annotation">240</text><path d="M${end+6},${bottom-4} l4,8 m3,-8 l4,8" stroke="var(--text-muted)" fill="none"/>`);
 $('forecast-range').textContent=`${time(rows[0].timestamp)}–${time(latest.timestamp)} WIB · req/s`;
 el.setAttribute('aria-label',`Synthetic workload over ${$('time-window').value} minutes. Current actual 186 req/s, latest point forecast 240 req/s at 18:11 WIB. Future inset uses a separate time scale; the dashed connector is a visual guide.`);
}
function drawScaling(){
 const el=$('scaling-chart'),w=el.clientWidth,h=el.clientHeight;if(!w)return;
 const rows=visibleRows(),{x,y,bottom,content}=frame(w,h,10,[0,2,4,6,8,10],rows);
 let path=`M${pt(x(0),y(rows[0].observed_replicas))}`;
 rows.slice(1).forEach((r,i)=>path+=`H${x(i+1).toFixed(2)}V${y(r.observed_replicas).toFixed(2)}`);
 let events='';
 fixture.scaling_events.filter(e=>e.timestamp>=rows[0].timestamp).forEach(e=>{
  const idx=rows.findIndex(r=>r.timestamp===e.timestamp),xx=x(idx),yy=y(e.to),up=e.to>e.from;
  const points=up?`${pt(xx,yy-7)} ${pt(xx-6,yy+5)} ${pt(xx+6,yy+5)}`:`${pt(xx,yy+7)} ${pt(xx-6,yy-5)} ${pt(xx+6,yy-5)}`;
  events+=`<polygon points="${points}" fill="var(--${up?'success':'warning'})"/><text x="${xx}" y="${yy-31}" text-anchor="middle" class="annotation">${w<420?'':up?'Scale up':'Scale down'}</text><text x="${xx}" y="${yy-17}" text-anchor="middle" class="annotation">${e.from} → ${e.to}</text>`;
 });
 el.innerHTML=svg(w,h,content+`<path class="actual-area" d="${path}L${pt(x(rows.length-1),bottom)}L${pt(x(0),bottom)}Z"/><path class="actual-stroke" d="${path}"/>`+events);
}
function drawError(){
 const el=$('error-chart'),w=el.clientWidth,h=el.clientHeight;if(!w)return;
 const rows=fixture.rows.slice(-61),x=i=>2+i/60*(w-28),y=v=>h-22-v/.4*(h-30);
 let c='';[0,.2,.4].forEach(v=>{c+=`<line class="grid-line" x1="0" y1="${y(v)}" x2="${w-24}" y2="${y(v)}"/><text x="${w}" y="${y(v)+3}" text-anchor="end">${v}</text>`;});
 const line=rows.map((r,i)=>pt(x(i),y(r.prediction_error_rps))).join(' ');
 c+=`<polyline class="actual-stroke" points="${line}" style="stroke-width:1.4"/><text x="0" y="${h-3}">${time(rows[0].timestamp)}</text><text x="${(w-24)/2}" y="${h-3}" text-anchor="middle">${time(rows[30].timestamp)}</text><text x="${w-24}" y="${h-3}" text-anchor="end">${time(latest.timestamp)}</text>`;
 el.innerHTML=svg(w,h,c);
}
function spark(id,values,color){const el=$(id),w=el.clientWidth,h=el.clientHeight;if(!w)return;const min=Math.min(...values)-1,max=Math.max(...values)+1;const line=values.map((v,i)=>pt(i/(values.length-1)*w,h-2-(v-min)/(max-min)*(h-4))).join(' ');el.innerHTML=svg(w,h,`<polygon points="0,${h} ${line} ${w},${h}" fill="var(--${color})" fill-opacity=".07"/><polyline points="${line}" fill="none" stroke="var(--${color})" stroke-width="1.3"/>`);}
function renderCharts(){drawForecast();drawScaling();drawError();spark('latency-spark',fixture.rows.slice(-40).map(r=>r.p95_latency_ms),'chart-actual');spark('success-spark',fixture.illustrative_sparklines.success_percent,'success');spark('cpu-spark',fixture.illustrative_sparklines.cpu_percent,'chart-actual');}
function tableRows(rows){return rows.map(r=>`<tr><td>${time(r.timestamp,true)}</td><td>${time(new Date(Date.parse(r.timestamp)+60000),true)}</td><td class="numeric">${number(r.actual_rps)}</td><td class="numeric">${number(r.prediction_for_plus_60s_rps)}</td><td class="numeric">${r.observed_replicas}</td><td>Synthetic</td></tr>`).join('');}
$('telemetry-table').innerHTML=tableRows(fixture.rows.slice(-6));
$('recent-events').innerHTML=fixture.events.map((e,i)=>`<li><i class="dot ${i===0?'warning':i===1?'accent':'success'}"></i><time datetime="${e.timestamp}">${time(e.timestamp)}</time><span class="event-text">${e.label}<span class="event-extra">${i===0?'(pending)':i===1?'(241 rows)':i===2?'(PSI 0.08)':''}</span></span></li>`).join('');
const details={
 environment:['Production · demo','<p>This is an offline visual reference. “Production” names the synthetic scenario; it does not indicate a connection to AWS, Kubernetes or an inference service.</p><p>The fixture is frozen at 12 October 2026, 18:10 WIB. Refresh replays the same data.</p>'],
 decision:['Recommendation evidence','<p>At 18:10 WIB, the latest +60s forecast is <b>240 req/s</b>. With synthetic capacity of <b>65 req/s/pod</b>, ceil(240 ÷ 65) = <b>4 replicas</b>. The demo policy bounds are 1–8.</p><p>Current observed replicas: <b>3</b>. Recommendation: <b>4</b>. State: <b>Pending</b>. The recommendation has not been applied. No confidence score or business saving is inferred.</p>'],
 model:['Model health definitions','<dl><dt>Model</dt><dd>demo-v2.4 · XGBoost · synthetic</dd><dt>PSI</dt><dd>0.08 · synthetic reference baseline</dd><dt>Recent online MAE</dt><dd>0.12 req/s · 61 aligned target pairs</dd><dt>Online MAE window</dt><dd>17:55–18:10 WIB (15m)</dd><dt>HTTP errors</dt><dd>20 / 5,000 requests = 0.4%</dd></dl><p>MAE compares the observation at time t with the forecast issued at t−60s. It is distinct from validation MAE. The mini chart shows absolute errors, not a rolling MAE time series.</p><p>The demo algorithm and version are fixture labels, not claims about the repository’s active model.</p>'],
 cluster:['Synthetic cluster census','<dl><dt>Ready nodes</dt><dd>node-a, node-b, node-c</dd><dt>Ready pods</dt><dd>3 · policy maximum 8</dd><dt>CPU / allocatable CPU</dt><dd>54%</dd><dt>Memory / allocatable memory</dt><dd>61%</dd></dl><p>All counts are synthetic. The replica decision buffer in the existing project does not provide a Kubernetes readiness census, node inventory, or these utilization denominators. Production must show unavailable until a verified source exists.</p>'],
 slo:['SLO definitions','<dl><dt>Latency p95</dt><dd>42 ms · synthetic 15m observation</dd><dt>Illustrative latency target</dt><dd>100 ms · not approved runtime policy</dd><dt>Success rate</dt><dd>4,980 / 5,000 = 99.6%</dd><dt>CPU saturation</dt><dd>54% of allocatable CPU</dd></dl><p>The sparkline shapes are synthetic illustration. Success-rate sparkline is not reconstructed from the aggregate request counts. No trend deltas or SLO compliance guarantee are inferred.</p>'],
 scaling:['Synthetic applied events',`<div class="table-scroll" tabindex="0" role="region" aria-label="Synthetic applied scaling events"><table><thead><tr><th scope="col">Applied WIB</th><th scope="col">Observed change</th><th scope="col">Provenance</th></tr></thead><tbody>${fixture.scaling_events.map(e=>`<tr><td>${time(e.timestamp)}</td><td>${e.from} → ${e.to}</td><td>Synthetic</td></tr>`).join('')}</tbody></table></div><p>The 18:10 recommendation, 3 → 4, is pending. It is not plotted as an applied event.</p>`],
 events:['Recent events',fixture.events.map(e=>`<p><b>${time(e.timestamp)} WIB · ${e.label}</b><br>${e.detail}</p>`).join('')]
};
function showDetail(key){
 let detail=details[key];
 if(key==='forecast'){const rows=visibleRows();detail=['Forecast data & time scales',`<p>${rows.length} synthetic samples over ${$('time-window').value} minutes, at 15-second cadence. Times are WIB (UTC+07:00). The right inset has a separate +60s time scale; the dashed connector is a visual guide to the latest point forecast, not a continuous predicted trajectory.</p><p>Now: 186 req/s at 18:10. Latest forecast: 240 req/s at 18:11. No uncertainty interval is available.</p><div class="table-scroll" tabindex="0" role="region" aria-label="Latest synthetic forecast rows"><table><thead><tr><th scope="col">Issued WIB</th><th scope="col">Target WIB</th><th scope="col">Actual req/s</th><th scope="col">Forecast req/s</th><th scope="col">Pods</th><th scope="col">Source</th></tr></thead><tbody>${tableRows(rows.slice(-6))}</tbody></table></div><p>Use Export synthetic CSV for all 241 observations. Forecasts are stored by issue time; join to observations by target time for evaluation.</p>`];}
 if(!detail)return;$('dialog-title').textContent=detail[0];$('dialog-content').innerHTML=detail[1];$('detail-dialog').showModal();$('dialog-close').focus();
}
document.addEventListener('click',e=>{const trigger=e.target.closest('[data-detail]');if(trigger)showDetail(trigger.dataset.detail);});
$('dialog-close').onclick=()=>$('detail-dialog').close();
$('detail-dialog').addEventListener('keydown',e=>{if(e.key!=='Tab')return;const focusable=Array.from(e.currentTarget.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea,[tabindex="0"]')).filter(el=>el.getClientRects().length);const first=focusable[0],last=focusable.at(-1);if((e.shiftKey&&document.activeElement===first)||(!e.shiftKey&&document.activeElement===last)){e.preventDefault();(e.shiftKey?last:first).focus();}});
$('detail-dialog').addEventListener('click',e=>{if(e.target===$('detail-dialog')){const b=e.target.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)e.target.close();}});
function closeMenu(){$('navigation').classList.remove('open');$('menu-toggle').setAttribute('aria-expanded','false');}
$('menu-toggle').onclick=()=>{const open=$('navigation').classList.toggle('open');$('menu-toggle').setAttribute('aria-expanded',String(open));};
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenu();});
function route(){const hash=location.hash||'#overview',showcase=hash==='#lab-controls';$('overview').hidden=showcase;$('lab-controls').hidden=!showcase;document.querySelectorAll('#navigation a').forEach(a=>{if(a.hash===hash)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});if(!document.querySelector('#navigation [aria-current]'))document.querySelector('#navigation a').setAttribute('aria-current','page');closeMenu();requestAnimationFrame(()=>{renderCharts();if(showcase)window.scrollTo(0,0);});}
window.addEventListener('hashchange',route);
document.querySelectorAll('#navigation a').forEach(a=>a.addEventListener('click',()=>{closeMenu();if(a.hash===location.hash)route();}));
function toggleTheme(){const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=theme;$('theme-toggle').querySelector('span').textContent=theme==='dark'?'Light theme':'Dark theme';toast(`${theme==='dark'?'Dark':'Light'} theme`);}
$('theme-toggle').onclick=toggleTheme;$('showcase-theme').onclick=toggleTheme;
$('time-window').onchange=renderCharts;
$('refresh').onclick=()=>{renderCharts();toast('Synthetic fixture replayed · still frozen at 18:10 WIB');};
function exportCsv(){const header='synthetic,issued_at_utc,target_at_utc,actual_rps,forecast_rps_60s,observed_replicas,recommended_replicas,p95_latency_ms';const rows=fixture.rows.map(r=>[true,r.timestamp,new Date(Date.parse(r.timestamp)+60000).toISOString(),r.actual_rps,r.prediction_for_plus_60s_rps,r.observed_replicas,r.recommended_replicas,r.p95_latency_ms].join(','));const url=URL.createObjectURL(new Blob([header+'\n'+rows.join('\n')+'\n'],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='titipin-synthetic-telemetry.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Exported 241 synthetic rows · all timestamps in UTC');}
$('export').onclick=exportCsv;$('showcase-export').onclick=exportCsv;
$('copy-policy').onclick=async()=>{const text='SYNTHETIC DEMO POLICY: capacity=65 req/s/pod; replicas=1..8; horizon=60s. Not runtime configuration.';try{await navigator.clipboard.writeText(text);toast('Synthetic demo policy copied');}catch{details.copy=['Copy synthetic demo policy',`<p>Select and copy the text below. Clipboard access is unavailable in this browser context.</p><textarea aria-label="Synthetic demo policy" rows="4" style="width:100%">${text}</textarea>`];showDetail('copy');}};
$('policy-form').onsubmit=e=>{e.preventDefault();const input=$('capacity'),value=Number(input.value),valid=input.value.trim()!==''&&Number.isInteger(value)&&value>=1&&value<=1000;input.setAttribute('aria-invalid',String(!valid));$('capacity-error').hidden=valid;if(!valid){$('capacity-error').textContent='Enter a whole number from 1 to 1000 req/s.';$('policy-output').textContent='Preview unavailable until capacity is valid.';input.focus();return;}const raw=Math.ceil(240/value),bounded=Math.min(8,Math.max(1,raw));$('policy-output').textContent=`240 ÷ ${value} = ${raw} replicas · ${raw>8?'clamped to demo maximum '+bounded:'within demo bounds 1–8'} · local preview`;};
const states={ready:['success','Healthy · synthetic','p95 42 ms · observed at 18:10 WIB.'],loading:['info','Loading observations','Waiting for the first response. No value or healthy state is implied.'],empty:['info','No observations in this window','Choose a wider time range or inspect the source.'],error:['danger','Telemetry unavailable','The source did not respond. No value is inferred.'],stale:['warning','Stale · last observed at 18:05 WIB','Last-known p95: 42 ms. Age: 5m; illustrative stale threshold: 2m.'],unknown:['info','Controller mode unknown','A verified controller-status source is not available.']};
function renderState(){const state=$('state-select').value,[color,title,text]=states[state];$('state-example').setAttribute('aria-busy',String(state==='loading'));$('state-example').innerHTML=`<i class="dot ${color}"></i><div><h3 class="${color}">${title}</h3><p>${text}</p>${state==='loading'?'<div class="skeleton"></div>':''}</div>${state==='error'?'<button class="button" id="retry-state">Retry demo</button>':''}`;if(state==='error')$('retry-state').onclick=()=>{$('state-select').value='ready';renderState();toast('Demo state reset · no request sent');};}
$('state-select').onchange=renderState;renderState();
const colors=['bg','surface','surface-raised','text','text-secondary','text-muted','accent','chart-actual','chart-predicted','success','warning','danger'];$('swatches').innerHTML=colors.map(name=>`<div class="swatch"><i style="background:var(--${name})"></i><span>${name}</span><code>var(--${name})</code></div>`).join('');
const icons=Array.from(document.querySelectorAll('.symbol-sheet symbol')).map(s=>s.id.replace('icon-',''));$('icon-gallery').innerHTML=icons.map(name=>`<div class="icon-sample">${icon(name)}<span>${name}</span></div>`).join('');
function checkTextScale(){document.documentElement.classList.toggle('large-type',parseFloat(getComputedStyle(document.documentElement).fontSize)>20);}
new MutationObserver(checkTextScale).observe(document.documentElement,{attributes:true,attributeFilter:['style']});
window.addEventListener('resize',checkTextScale);checkTextScale();
const resizeObserver=new ResizeObserver(()=>requestAnimationFrame(renderCharts));['forecast-chart','scaling-chart','error-chart','latency-spark','success-spark','cpu-spark'].forEach(id=>resizeObserver.observe($(id)));
route();document.fonts.ready.then(renderCharts);
