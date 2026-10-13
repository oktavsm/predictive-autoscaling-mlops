export default function ({ data, parentElement }) {
  const root = parentElement.querySelector('.cluster-explorer');
  const list = value => Array.isArray(value) ? value.filter(x => x && typeof x === 'object') : [];
  const cluster = data.cluster || {}, health = data.health || {}, workload = data.workload || {};
  const nodes = list(cluster.nodes), pods = list(cluster.pods), services = list(cluster.services);
  const catalog = data.catalog.components, flows = data.catalog.flows;
  const components = Object.fromEntries(catalog.map(c => [c.id, c]));
  const esc = value => String(value ?? 'Unknown').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const paths = {
    server:'M4 3h16v7H4z M4 14h16v7H4z M7 6h1 M7 17h1 M12 6h5 M12 17h5',
    pod:'M12 3 21 8v9l-9 5-9-5V8z M3 8l9 5 9-5 M12 13v9',
    traffic:'M3 6h12 M11 2l4 4-4 4 M21 18H9 M13 14l-4 4 4 4 M3 14v6 M21 4v6',
    gateway:'M3 7h6v10H3z M15 3h6v18h-6z M9 12h6 M11 9l3 3-3 3',
    application:'M3 4h18v16H3z M3 8h18 M8 12l-3 2 3 2 M16 12l3 2-3 2 M13 11l-2 6',
    telemetry:'M3 19h18 M3 19V5 M6 14l4-6 4 4 5-8',
    scaling:'M4 4h5v5H4z M15 15h5v5h-5z M15 4h5v5h-5z M9 6h6 M6 9v8h9',
    model:'M3 6h6v6H3z M15 3h6v6h-6z M15 15h6v6h-6z M9 9l6-3 M9 9l6 9',
    orchestrator:'M12 2l9 5v10l-9 5-9-5V7z M12 7v5l5 3 M12 12l-5 3 M12 12V7',
    console:'M3 4h18v16H3z M3 8h18 M7 12l3 2-3 2 M13 16h4',
    pipeline:'M2 9h5v6H2z M10 4h5v6h-5z M17 14h5v6h-5z M7 12l3-5 M15 7l5 7',
    registry:'M4 3h16v18H4z M8 7h8 M8 11h8 M8 15h4 M15 14l2 2 3-4',
    storage:'M3 6c0-4 18-4 18 0s-18 4-18 0v12c0 4 18 4 18 0V6 M3 12c0 4 18 4 18 0',
    chart:'M4 20V4 M4 20h17 M8 16v-5 M13 16V7 M18 16v-8',
    search:'M16 16l5 5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
    external:'M14 3h7v7 M21 3l-11 11 M10 3H3v18h18v-7'
  };
  const icon = name => `<svg class="icon" aria-hidden="true" viewBox="0 0 24 24"><path d="${paths[name] || paths.pod}"/></svg>`;
  const badge = ([label, tone]) => `<span class="badge ${tone}">${esc(label)}</span>`;
  const matches = c => pods.filter(p => p.namespace === c.namespace && c.match.some(prefix => p.name?.startsWith(prefix)));
  function podStatus(p) {
    if (p.phase === 'Succeeded') return ['Completed', 'unknown'];
    if (p.phase === 'Failed') return ['Failed', 'bad'];
    if (p.phase === 'Running' && p.containers > 0 && p.ready === p.containers) return ['Ready', 'good'];
    return [p.phase === 'Running' ? 'Not ready' : p.phase || 'Unknown', 'warn'];
  }
  function status(c) {
    if (c.id === 'k6') return workload.daemon_alive === true ? ['Heartbeat connected', 'good'] : ['Heartbeat unavailable', 'unknown'];
    if (c.id === 'caddy') return ['Configured · not probed', 'unknown'];
    if (c.id === 'kubernetes') return nodes.length ? [nodes.every(n => n.ready === true) ? 'Nodes Ready' : 'Node warning', nodes.every(n => n.ready === true) ? 'good' : 'warn'] : ['Inventory unavailable', 'unknown'];
    const found = matches(c), active = found.filter(p => !['Succeeded', 'Failed'].includes(p.phase));
    if (c.id === 'training' && !active.length) return found.length ? ['No active Job · retained history', 'unknown'] : ['No retained Job', 'unknown'];
    if (!found.length) return ['No matching workload', 'unknown'];
    return active.length && active.every(p => podStatus(p)[0] === 'Ready') ? [`${active.length} pod${active.length === 1 ? '' : 's'} Ready`, 'good'] : ['Workload warning', 'warn'];
  }
  const memory = value => {
    const m = String(value || '').match(/^(\d+(?:\.\d+)?)(Ki|Mi|Gi)$/);
    return m ? `${(Number(m[1]) / ({Ki:1048576, Mi:1024, Gi:1}[m[2]])).toFixed(1)} GiB` : value || 'Unknown';
  };
  let state = {view:'placement', flow:'serving', selected:'component:inference', namespace:'All', search:'', expanded:[]};
  try { state = {...state, ...JSON.parse(sessionStorage.getItem('titipin-cluster-explorer') || '{}')}; } catch {}
  if (!['placement','flow'].includes(state.view)) state.view = 'placement';
  if (!flows.some(f => f.id === state.flow)) state.flow = 'serving';
  if (!Array.isArray(state.expanded)) state.expanded = [];
  for (const [key, value] of Object.entries(data.palette || {})) root.style.setProperty(`--${key}`, value);
  const save = () => { try { sessionStorage.setItem('titipin-cluster-explorer', JSON.stringify(state)); } catch {} };
  const selected = id => `aria-pressed="${state.selected === id}"`;
  const button = (id, text) => `<button type="button" data-select="${esc(id)}" ${selected(id)}>${esc(text)}</button>`;
  const facts = pairs => `<dl class="details">${pairs.map(([k,v]) => `<div class="detail"><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>`;
  const tooltip = (id, text) => `<span class="hover-note" role="tooltip" id="tip-${esc(id)}">${esc(text)}</span>`;
  const caption = (text, cls='scope-note') => `<p class="${cls}">${esc(text)}</p>`;
  root.innerHTML = `<div class="toolbar"><div class="tabs" role="group" aria-label="Cluster view"><button class="tab" data-view="placement">Workload placement</button><button class="tab" data-view="flow">System flow</button></div><label class="search">${icon('search')}<input aria-label="Search cluster" placeholder="Find node, pod or component" type="search" value="${esc(state.search)}"></label></div><div class="layout"><section class="map-panel" aria-label="Cluster map"></section><aside class="inspector" aria-label="Component inspector" aria-live="polite"></aside></div>`;
  const map = root.querySelector('.map-panel'), inspector = root.querySelector('.inspector');
  function choose(id) {
    state.selected = id; save(); render();
    const heading = inspector.querySelector('h2');
    heading?.focus({preventScroll:true});
    if (root.getBoundingClientRect().width < 1100) inspector.scrollIntoView({block:'start', behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
  }
  function placement() {
    const query = String(state.search).toLowerCase();
    const filtered = pods.filter(p => (state.namespace === 'All' || p.namespace === state.namespace) && `${p.name} ${p.namespace} ${p.node || ''}`.toLowerCase().includes(query));
    const visibleNodes = nodes.filter(n => n.name?.toLowerCase().includes(query) || filtered.some(p => p.node === n.name));
    map.innerHTML = `<div class="eyebrow">K3s / AWS · observed placement</div><h2>Where the workloads run</h2>${caption(`${nodes.filter(n=>n.ready === true).length}/${nodes.length} nodes Ready · ${pods.filter(p=>podStatus(p)[0] === 'Ready').length} Ready pods · ${services.length} services`)}<div class="filters" role="group" aria-label="Namespace filter">${['All','mlops','monitoring','titipin'].map(ns=>`<button class="filter" data-namespace="${ns}" aria-pressed="${ns === state.namespace}">${ns}</button>`).join('')}</div><div class="node-grid">${visibleNodes.map(n => {
      const found = filtered.filter(p => p.node === n.name), expanded = state.expanded.includes(n.name), shown = expanded || query ? found : found.slice(0,6);
      return `<article class="node"><button class="node-head" data-select="${esc('node:'+n.name)}" ${selected('node:'+n.name)} aria-describedby="tip-node-${esc(n.name)}"><span class="node-title">${icon('server')}${esc(n.name)}</span><span class="node-summary">${badge(n.ready === true ? ['Ready','good'] : ['Not ready','warn'])}<small>${esc(n.role)}</small></span><span class="node-capacity">${esc(n.allocatable?.cpu || '?')} CPU · ${esc(memory(n.allocatable?.memory))} allocatable</span>${tooltip('node-'+n.name, `${n.name}: ${n.role}. Select for conditions, capacity and Kubernetes version.`)}</button><div class="pods">${shown.map(p=>`<button class="pod" data-select="${esc('pod:'+p.namespace+'/'+p.name)}" ${selected('pod:'+p.namespace+'/'+p.name)} aria-label="Inspect ${esc(p.name)}" aria-describedby="tip-pod-${esc(p.name)}">${icon('pod')}<span class="pod-text"><span class="pod-name">${esc(p.name)}</span><span class="pod-meta">${esc(p.namespace)} · ${esc(p.ready)}/${esc(p.containers)} containers</span></span>${badge(podStatus(p))}${tooltip('pod-'+p.name, `${p.name} · ${p.phase}. Select for resource requests, limits and restart details.`)}</button>`).join('') || caption('No matching pods on this node.','empty')}${found.length > 6 && !query ? `<button class="more" data-expand="${esc(n.name)}">${expanded ? 'Show fewer pods' : `Show ${found.length-6} more pods`}</button>` : ''}</div></article>`;
    }).join('')}</div>${!visibleNodes.length ? caption(nodes.length ? 'No nodes or pods match the current filter.' : 'Node inventory unavailable. No placement is assumed.','empty') : ''}`;
    const unplaced = filtered.filter(p => !p.node || !nodes.some(n => n.name === p.node));
    if (unplaced.length) map.insertAdjacentHTML('beforeend', `<h3 style="margin-top:18px">Unplaced / node outside snapshot</h3><div class="related">${unplaced.map(p=>button('pod:'+p.namespace+'/'+p.name,p.name)).join('')}</div>`);
    map.insertAdjacentHTML('beforeend', `<div class="remote">${icon('traffic')}<div class="body">${button('component:k6','Remote VM · cp-bcc')}${caption('Traffic source outside the AWS Kubernetes cluster.')}${badge(status(components.k6))}</div></div>${caption('CPU and memory are declared allocatable capacity, not measured utilization. Pod counts cover mlops, monitoring and titipin only.')}`);
  }
  let observer;
  function flow() {
    const current = flows.find(f => f.id === state.flow), selectedId = state.selected.replace('component:','');
    const neighbors = new Set(current.edges.filter(e=>e[0]===selectedId || e[1]===selectedId).flatMap(e=>e.slice(0,2)));
    map.innerHTML = `<div class="eyebrow">Titipin / operational architecture</div><h2>How the system connects</h2>${caption('Connections describe configured architecture. They are not packet traces or verified dependency health.')}<div class="flow-tabs" role="group" aria-label="Architecture flow">${flows.map(f=>`<button data-flow="${f.id}" aria-pressed="${f.id === current.id}">${esc(f.name)}</button>`).join('')}</div>${caption(current.description)}<div class="graph"><svg class="graph-lines" aria-hidden="true"></svg><div class="lanes">${current.lanes.map(lane=>`<div class="lane">${lane.map(id=>{
      const c=components[id], hit=`${c.name} ${c.description} ${matches(c).map(p=>p.name).join(' ')}`.toLowerCase().includes(String(state.search).toLowerCase());
      return `<button class="system ${neighbors.has(id) ? 'neighbor' : ''}" data-component="${id}" data-select="component:${id}" ${selected('component:'+id)} ${!hit ? 'hidden' : ''} aria-describedby="tip-${id}">${icon(c.icon)}<span class="system-name">${esc(c.name)}</span><span class="kind">${esc(c.kind)}</span>${badge(status(c))}${tooltip(id,c.summary)}</button>`;
    }).join('')}</div>`).join('')}</div></div><div class="connections" aria-label="Configured connections"><h3>${neighbors.size ? 'Selected component connections' : 'Configured connections'}</h3>${current.edges.filter(e=>!neighbors.size || e[0]===selectedId || e[1]===selectedId).map(([a,b,label])=>`<div class="connection">${button('component:'+a,components[a].name)}<span aria-hidden="true">→</span>${button('component:'+b,components[b].name)}<small>${esc(label)}</small></div>`).join('')}</div>`;
    if (state.search && !map.querySelector('.system:not([hidden])')) map.querySelector('.graph').insertAdjacentHTML('beforeend',caption('No components match the current search.','empty'));
    const graph = map.querySelector('.graph'), svg = map.querySelector('.graph-lines');
    function draw() {
      const bounds = graph.getBoundingClientRect();
      svg.setAttribute('viewBox',`0 0 ${bounds.width} ${bounds.height}`);
      svg.innerHTML = '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="currentColor"/></marker></defs>';
      for (const [a,b,label] of current.edges) {
        const from = graph.querySelector(`[data-component="${a}"]:not([hidden])`), to = graph.querySelector(`[data-component="${b}"]:not([hidden])`);
        if (!from || !to) continue;
        const ar=from.getBoundingClientRect(), br=to.getBoundingClientRect(), right=br.left>ar.left;
        const x1=(right?ar.right:ar.left)-bounds.left, y1=ar.top+ar.height/2-bounds.top, x2=(right?br.left:br.right)-bounds.left, y2=br.top+br.height/2-bounds.top;
        const offset=Math.max(20,Math.abs(x2-x1)/2)*(right?1:-1);
        let path=`M${x1},${y1} C${x1+offset},${y1} ${x2-offset},${y2} ${x2},${y2}`;
        if(Math.abs(ar.left-br.left)<1) {
          const x=ar.left+ar.width/2-bounds.left, down=br.top>ar.top;
          const start=(down?ar.bottom:ar.top)-bounds.top, end=(down?br.top:br.bottom)-bounds.top;
          path=`M${x},${start} L${x},${end}`;
        }
        svg.insertAdjacentHTML('beforeend',`<path class="edge ${a===selectedId || b===selectedId ? 'active' : ''}" d="${path}" marker-end="url(#arrow)"><title>${esc(label)}</title></path>`);
      }
    }
    observer = new ResizeObserver(draw); observer.observe(graph); draw();
  }
  function inspect() {
    const [type, ...parts] = String(state.selected).split(':'), id = parts.join(':');
    let item, glyph, title, subtitle, observed, body;
    if (type === 'node' && (item = nodes.find(n=>n.name === id))) {
      glyph='server'; title=item.name; subtitle=`Kubernetes node · ${item.role}`; observed=badge(item.ready === true ? ['Ready','good'] : ['Not ready','warn']);
      body=caption('Kubernetes reports this node’s scheduling capacity and conditions. Ready does not mean spare capacity.','description')+facts([['Scheduling',item.unschedulable ? 'Cordoned' : 'Schedulable'],['Capacity CPU',item.capacity?.cpu],['Allocatable CPU',item.allocatable?.cpu],['Capacity memory',memory(item.capacity?.memory)],['Allocatable memory',memory(item.allocatable?.memory)],['Pod capacity',item.allocatable?.pods],['Scoped pods',pods.filter(p=>p.node===id).length],['Kubelet',item.info?.kubeletVersion],['Runtime',item.info?.containerRuntimeVersion],['OS',item.info?.osImage],['Architecture',item.info?.architecture]])+`<h3>Reported conditions</h3>`+facts(list(item.conditions).map(c=>[c.type,`${c.status} · ${c.reason || 'No reason reported'}`]));
    } else if (type === 'pod' && (item=pods.find(p=>p.namespace+'/'+p.name===id))) {
      glyph='pod'; title=item.name; subtitle=`${item.namespace} · Kubernetes pod`; observed=badge(podStatus(item));
      body=caption('Phase, container readiness and restarts come from this Kubernetes snapshot. Resources below are declared requests and limits.','description')+facts([['Node',item.node || 'Unscheduled'],['Phase',item.phase],['Ready containers',`${item.ready}/${item.containers}`],['Restarts',item.restarts],['Created (UTC)',item.created_at],['Owner',list(item.owner).map(o=>o.kind+'/'+o.name).join(', ') || 'No controller reported']])+list(item.container_details).map(c=>`<h3>${esc(c.name)}</h3>${facts([['Ready',c.ready === true ? 'Yes' : 'No'],['State',Object.entries(c.state || {}).map(([k,v])=>`${k}${v.reason ? ': '+v.reason : ''}`).join(', ') || 'Not reported'],['CPU request / limit',`${c.requests?.cpu || 'Not set'} / ${c.limits?.cpu || 'Not set'}`],['Memory request / limit',`${c.requests?.memory || 'Not set'} / ${c.limits?.memory || 'Not set'}`]])}`).join('')+`<h3>Component roles</h3><div class="related">${catalog.filter(c=>matches(c).includes(item)).map(c=>button('component:'+c.id,c.name)).join('') || caption('No catalog role mapped to this pod.')}</div>`;
    } else {
      item=components[id] || components.inference; glyph=item.icon; title=item.name; subtitle=`${item.plane} · ${item.kind}`; observed=badge(status(item));
      body=caption(item.description,'description')+`<h3>Why it exists</h3>${caption(item.why,'description')}<h3>Interfaces · configured</h3><ul>${item.interfaces.map(i=>`<li>${esc(i)}</li>`).join('')}</ul>`;
      if(item.id==='inference') body+=facts([['Loaded model',health.model_version],['Algorithm',health.model_algorithm],['Model ready',health.model_ready === true ? 'Yes' : health.model_ready === false ? 'No' : 'Unknown']]);
      if(item.id==='scaler') body+=facts([['Predictive loop',health.predictive_loop],['Decision evaluation',health.last_scaling_observation || 'Not reported']]);
      if(item.id==='k6') body+=facts([['Reported profile',workload.daemon_current_state],['Reported VUs',workload.daemon_vus],['Heartbeat age',workload.last_heartbeat_seconds_ago == null ? 'Not reported' : `${workload.last_heartbeat_seconds_ago}s`]]);
      const found=matches(item);
      if(item.match.length) body+=`<h3>Observed workloads</h3><div class="related">${found.map(p=>button('pod:'+p.namespace+'/'+p.name,p.name)).join('') || caption('No matching pod in this snapshot. Configured role does not prove execution.')}</div>`;
      const linkedServices=services.filter(s=>s.namespace===item.namespace && found.some(p=>Object.entries(s.selector || {}).length>0 && Object.entries(s.selector).every(([k,v])=>p.labels?.[k] === v)));
      if(linkedServices.length) body+=`<h3>Observed service ports</h3>${linkedServices.map(s=>facts([['Service',`${s.namespace}/${s.name}`],...list(s.ports).map(p=>[p.name || p.protocol,`${p.port} → ${p.targetPort}${p.nodePort ? ' · NodePort '+p.nodePort : ''}`])])).join('')}`;
      body+=`<h3>What to investigate</h3>${caption(item.failure,'description')}`;
      const related = new Set(flows.flatMap(f=>f.edges).filter(e=>e[0]===item.id || e[1]===item.id).flatMap(e=>e.slice(0,2)).filter(x=>x!==item.id));
      body+=`<h3>Connected components</h3><div class="related">${[...related].map(id=>button('component:'+id,components[id].name)).join('')}</div>`;
      const url=data.links?.[item.link];
      if(url && /^https:\/\//.test(url)) body+=`<a class="inspect-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Open ${esc(item.name)} ${icon('external')}</a>`;
    }
    inspector.innerHTML=`<div class="eyebrow">Component inspector</div><div class="inspect-top">${icon(glyph)}${observed}</div><h2 tabindex="-1" class="inspect-heading">${esc(title)}</h2><div class="subtitle">${esc(subtitle)}</div>${body}`;
  }
  function render() {
    observer?.disconnect();
    root.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.view===state.view));
    if(state.view==='placement') placement(); else flow();
    const parsed=Date.parse(cluster.timestamp), age=Number.isFinite(parsed) ? Math.max(0,(Date.now()-parsed)/1000) : null;
    map.insertAdjacentHTML('beforeend',caption(`Source: ${cluster.source || 'Kubernetes inventory unavailable'} · Snapshot: ${cluster.timestamp || 'Not reported'}${age !== null && age > 45 ? ' · Older than 45s' : ''}`));
    inspect();
  }
  const click = event => {
    const b=event.target.closest('button'); if(!b) return;
    if(b.dataset.select) {choose(b.dataset.select);return;}
    if(b.dataset.view) state.view=b.dataset.view;
    if(b.dataset.flow) {state.flow=b.dataset.flow;state.search='';root.querySelector('input').value='';}
    if(b.dataset.namespace) state.namespace=b.dataset.namespace;
    if(b.dataset.expand) state.expanded=state.expanded.includes(b.dataset.expand) ? state.expanded.filter(n=>n!==b.dataset.expand) : [...state.expanded,b.dataset.expand];
    const focusKey=['flow','namespace','expand'].find(key=>b.dataset[key]);
    const focusValue=focusKey && b.dataset[focusKey];
    save();render();
    if(focusKey) [...root.querySelectorAll(`button[data-${focusKey}]`)].find(item=>item.dataset[focusKey]===focusValue)?.focus({preventScroll:true});
  };
  const input = event => {state.search=event.target.value;save();render();};
  const key = event => {if(event.key==='Escape') root.querySelectorAll('button').forEach(b=>b.classList.add('hide-tooltip'));};
  const showTooltip = event => event.target.closest('button')?.classList.remove('hide-tooltip');
  root.addEventListener('click',click);root.querySelector('input').addEventListener('input',input);root.addEventListener('keydown',key);root.addEventListener('pointerover',showTooltip);root.addEventListener('focusin',showTooltip);
  render();
  return () => {observer?.disconnect();root.removeEventListener('click',click);root.removeEventListener('keydown',key);root.removeEventListener('pointerover',showTooltip);root.removeEventListener('focusin',showTooltip);};
}
