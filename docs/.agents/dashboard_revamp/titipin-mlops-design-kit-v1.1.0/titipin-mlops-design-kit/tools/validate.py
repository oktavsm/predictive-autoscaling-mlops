#!/usr/bin/env python3
"""Validate kit resources, fixture semantics, offline embedding and contrast."""
from pathlib import Path
from html.parser import HTMLParser
import json
import math
import re
import xml.etree.ElementTree as ET
import hashlib

root = Path(__file__).resolve().parents[1]
checks = []
def check(condition, message):
    checks.append({'passed': bool(condition), 'check': message})
    if not condition:
        raise AssertionError(message)

tokens = json.loads((root / 'tokens/tokens.json').read_text())
css = (root / 'styles/variables.css').read_text()
for theme in ['dark', 'light']:
    block = re.search(r'(?:\[data-theme="' + theme + r'"\])\s*\{([^}]+)', css).group(1)
    for name, token in tokens['color'][theme].items():
        check(f'--{name}: {token["$value"]};' in block, f'CSS matches token color.{theme}.{name}')
for group in ['space','radius','size','breakpoint','font-size','duration']:
    for name, token in tokens[group].items():
        val = token['$value']
        check(f'--{group}-{name}: {val["value"]:g}{val["unit"]};' in css, f'CSS matches token {group}.{name}')
for group in ['weight','z']:
    for name, token in tokens[group].items():
        check(f'--{group}-{name}: {token["$value"]};' in css, f'CSS matches token {group}.{name}')

icons = json.loads((root / 'assets/icons/manifest.json').read_text())
check(len(icons) == 24, '24 individually named original icons')
for file in list((root / 'assets/icons').glob('*.svg')) + list((root / 'assets/logo').glob('*.svg')):
    xml = ET.parse(file)
    check(xml.getroot().tag.endswith('svg'), f'Valid SVG XML: {file.name}')
    text = file.read_text()
    check(not re.search(r'<(?:script|foreignObject|image|text)\b|onload=|javascript:|https?://(?!www.w3.org)', text), f'SVG has no executable, font or remote resource: {file.name}')

fixture = json.loads((root / 'data/synthetic-telemetry.json').read_text())
check(fixture['synthetic'] is True, 'Root fixture is labeled synthetic')
rows = fixture['rows']
check(len(rows) == 241, '241 samples across 60 minutes')
from datetime import datetime
times = [datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')).timestamp() for r in rows]
check(all(b-a == 15 for a,b in zip(times,times[1:])), 'UTC observations have exact 15-second cadence')
check(times[-1]-times[0] == 3600, 'Fixture spans exactly 3600 seconds')
for row in rows:
    check(row['synthetic'] is True, 'Every fixture row is synthetic')
    check(all(math.isfinite(row[k]) and row[k]>=0 for k in ['actual_rps','prediction_for_plus_60s_rps','p95_latency_ms']), 'Fixture numeric values are finite and nonnegative')
    p = fixture['policy']
    recommended = min(p['max_replicas'],max(p['min_replicas'], math.ceil(row['prediction_for_plus_60s_rps']/p['target_rps_per_pod'])))
    check(row['recommended_replicas'] == recommended, 'Fixture recommendation respects capacity and bounds')
check(rows[-1]['actual_rps']==186 and rows[-1]['prediction_for_plus_60s_rps']==240 and rows[-1]['recommended_replicas']==4 and rows[-1]['observed_replicas']==3, 'Overview numbers match latest fixture')
check(all(e['synthetic'] for e in fixture['events']), 'All events are synthetic')
for i,r in enumerate(rows):
    expected=round(abs(r['actual_rps']-rows[i-4]['prediction_for_plus_60s_rps']),2) if i>=4 else None
    check(r['prediction_error_rps']==expected, 'Error joins forecast to actual by target time, never issue time')
mae=round(sum(r['prediction_error_rps'] for r in rows[-61:])/61,2)
check(mae==fixture['model']['online_mae_rps']==.12, '15m online MAE matches 61 aligned target pairs')
for e in fixture['scaling_events']:
    i=next(i for i,r in enumerate(rows) if r['timestamp']==e['timestamp'])
    check(e['synthetic'] and rows[i-1]['observed_replicas']==e['from'] and rows[i]['observed_replicas']==e['to'], 'Applied event matches observed step')
check(fixture['cluster']['ready_pods']==rows[-1]['observed_replicas'], 'Synthetic ready pod census matches current observation')
check(100*fixture['http']['failed_count']/fixture['http']['request_count']==fixture['http']['error_percent'], 'HTTP error fraction matches counts')
check(fixture['http']['success_percent']==100-fixture['http']['error_percent'], 'HTTP success/error percentages complement')
check(fixture['illustrative_sparklines']['synthetic'] and fixture['illustrative_sparklines']['cpu_percent'][-1]==54 and fixture['illustrative_sparklines']['success_percent'][-1]==99.6, 'Illustrative spark endpoints and provenance agree')
check(hashlib.sha256((root/'dashboard_mockup.png').read_bytes()).hexdigest()=='b3b36ebf3a86989f8e365e0b1b0f67c15841532bbde1f3dc15484e286bdc0a18', 'User reference PNG preserved byte-for-byte')

html = (root / 'index.html').read_text()
check(not any(x in html for x in ['/* EMBEDDED_', '<!-- ICON_SYMBOLS -->', '<!-- LOGO_PATHS -->','<!-- LOGO_MARK -->','/* FIXTURE_JSON */']), 'Standalone placeholders resolved')
check(html.count('data:font/woff2;base64,') == 2, 'Both offline variable fonts embedded')
check('fetch(' not in html and 'XMLHttpRequest' not in html and 'WebSocket(' not in html, 'Standalone contains no network request implementation')
check('All telemetry synthetic' in html and 'Synthetic telemetry.' in html, 'Persistent synthetic labels present')
check('synthetic,issued_at_utc,target_at_utc' in html, 'CSV retains synthetic flag and issue/target timestamps')
class Parser(HTMLParser):
    def __init__(self): super().__init__(); self.ids=[]; self.refs=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if attrs.get('id'): self.ids.append(attrs['id'])
        for key in ['href','src']:
            val=attrs.get(key,'')
            if val: self.refs.append((key,val))
p=Parser();p.feed(html)
check(len(p.ids)==len(set(p.ids)), 'No duplicate static HTML IDs')
for key,ref in p.refs:
    if ref.startswith('#'): check(ref[1:] in p.ids, f'Local anchor or SVG reference resolves: {ref}')
    elif not ref.startswith(('data:','http:','https:')): check((root/ref).exists(), f'Local document reference resolves: {ref}')

def luminance(color):
    channels=[int(color[i:i+2],16)/255 for i in [1,3,5]]
    linear=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in channels]
    return sum(x*w for x,w in zip(linear,[.2126,.7152,.0722]))
def ratio(a,b):
    x,y=sorted([luminance(a),luminance(b)])
    return (y+.05)/(x+.05)
contrast=[]
for theme,values in tokens['color'].items():
    vals={k:v['$value'] for k,v in values.items()}
    pairs=[(fg,bg,4.5) for fg in ['text','text-secondary','text-muted'] for bg in ['bg','surface','surface-raised','surface-hover']]
    pairs += [(name,name+'-soft',4.5) for name in ['success','warning','danger','info','accent']]
    pairs += [(fg,bg,4.5) for fg in ['success','warning','danger','info','accent'] for bg in ['bg','surface','surface-raised','surface-hover']]
    pairs += [('on-accent','accent',4.5),('button-text','button-bg',4.5)]
    pairs += [(fg,bg,3) for fg in ['border-control','focus','chart-actual','chart-predicted','chart-capacity','chart-threshold'] for bg in ['bg','surface','surface-raised','surface-hover']]
    for fg,bg,minimum in pairs:
        value=ratio(vals[fg],vals[bg]);passed=value>=minimum
        contrast.append({'theme':theme,'foreground':fg,'background':bg,'ratio':round(value,2),'minimum':minimum,'passed':passed})
        check(passed,f'{theme} {fg}/{bg} contrast {value:.2f}:1 >= {minimum}:1')
(root/'qa/contrast.json').write_text(json.dumps(contrast,indent=2)+'\n')
report={'status':'PASS','checks':len(checks),'contrast_pairs':len(contrast),'scope':'Structural/data/color checks only. Browser evidence is separate.','results':checks}
(root/'qa/structural-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'PASS: {len(checks)} structural/data/token checks, including {len(contrast)} contrast pairings.')
