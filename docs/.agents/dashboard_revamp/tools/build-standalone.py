#!/usr/bin/env python3
"""Rebuild the offline mockup from the bundled editable sources."""
from pathlib import Path
import base64
import json
import re

root = Path(__file__).resolve().parents[1]
css = '\n'.join((root / 'styles' / name).read_text() for name in ['variables.css', 'overview.css', 'accessibility.css'])
for name in ['Geist-Variable.woff2', 'GeistMono-Variable.woff2']:
    encoded = base64.b64encode((root / 'assets/fonts' / name).read_bytes()).decode()
    css = css.replace("../assets/fonts/" + name, 'data:font/woff2;base64,' + encoded)

symbols = re.sub(r'^<svg[^>]*>|</svg>\s*$', '', (root / 'assets/icons/sprite.svg').read_text())
logo = re.sub(r'^<svg[^>]*><title>.*?</title>|</svg>\s*$', '', (root / 'assets/logo/lockup.svg').read_text())
fixture = json.loads((root / 'data/synthetic-telemetry.json').read_text())
mark = re.sub(r'^<svg[^>]*><title>.*?</title>|</svg>\s*$', '', (root / 'assets/logo/mark.svg').read_text())
html = (root / 'source/overview.html').read_text()
html = html.replace('/* EMBEDDED_STYLES */', css)
html = html.replace('<!-- ICON_SYMBOLS -->', symbols)
html = html.replace('<!-- LOGO_PATHS -->', logo)
html = html.replace('<!-- LOGO_MARK -->', mark)
html = html.replace('/* FIXTURE_JSON */', json.dumps(fixture, separators=(',', ':')).replace('</', '<\\/'))
html = html.replace('/* EMBEDDED_SCRIPT */', (root / 'source/overview.js').read_text())
(root / 'index.html').write_text(html)
print(f'Built {root / "index.html"} ({len(html.encode()):,} bytes)')
