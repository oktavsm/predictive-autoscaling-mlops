# Titipin MLOps design kit · 1.1.0

Reference-led revision of the supplied Overview mockup. Dark charcoal, blue actual telemetry, teal forecast, compact monitoring panels. Open **[index.html](index.html)** directly in a modern browser; it works offline and needs no installation.

**All telemetry is synthetic.** “Production” and “AWS K3s” name the demo scenario. This kit does not connect to a service, apply scaling, or prove deployment health.

## Start here

1. Review [Overview](index.html) against the preserved [reference PNG](dashboard_mockup.png).
2. Open **Lab Controls** for the component showcase. Theme, time range, inspection dialogs, synthetic CSV export, input validation and state previews work locally.
3. Read [design system](docs/DESIGN-SYSTEM.md), [token contract](docs/TOKEN-CONTRACT.md) and [agent handoff](docs/AGENT-HANDOFF.md) before implementation.
4. Use the [source evidence](docs/SOURCES.md) to distinguish implemented APIs from design proposals.

## Package

```text
dashboard_revamp/
├── index.html                    # Self-contained Overview + component showcase
├── README.md / LICENSE.md
├── dashboard_mockup.png          # User-supplied visual authority; unchanged
├── docs/
│   ├── DESIGN-SYSTEM.md           # Complete visual, interaction and a11y specification
│   ├── TOKEN-CONTRACT.md          # JSON → CSS mapping and change policy
│   ├── AGENT-HANDOFF.md           # Verified Streamlit/API integration instructions
│   └── SOURCES.md                 # Source boundaries and screenshot provenance
├── tokens/tokens.json
├── styles/                       # variables, overview components, accessibility
├── assets/
│   ├── fonts/                    # Geist Sans / Mono WOFF2 + OFL
│   ├── icons/                    # 24 original SVG glyphs + sprite + semantic manifest
│   └── logo/                     # Original Ahead mark + outlined wordmark variants
├── source/                       # Editable HTML/JS before embedding
├── data/                         # Synthetic fixture + generation/interpretation notes
├── tools/                        # Offline builder, validation and package utilities
├── previews/                     # Rendered desktop/light/mobile/showcase evidence
├── qa/                           # Structural, contrast, browser and preservation evidence
├── anti-slop/audit-002-2026-10-12.md # Post-completion reference comparison + delivery gate
├── MANIFEST.json                 # SHA-256 of packaged payload files
└── titipin-mlops-design-kit-v1.1.0.zip
```

The ZIP contains one top-level `titipin-mlops-design-kit/` folder. It excludes itself, its checksum and the manifest's own hash. `MANIFEST.json` covers the remaining payload, including the original reference. A companion `.zip.sha256` authenticates the archive.

## What changed from v1.0

The rejected lime theme and reorganized Overview were replaced with the supplied composition: 238px sidebar, four status cards, forecast/scaling at left, model/cluster/events at right, and decision/SLO panels below. The original reference now governs placement, density and palette. The previous technical audit was not evidence of visual fidelity.

Intentional corrections to the screenshot: explicit synthetic/demo labels; pending recommendation separate from applied events; no AI sparkle, unsupported confidence score, uncertainty band or unexplained trend delta. A labeled +60s inset prevents a 1-hour history from implying that the future segment has the same time scale. The original logo proposal is retained in blue, rather than tracing the screenshot's mark.

## Rebuild and verify

From this folder, with Python 3:

```sh
python3 tools/build-standalone.py
python3 tools/validate.py
```

The builder is deterministic and embeds CSS, fonts, icons, logo and fixture in `index.html`. No build dependency is downloaded. Browser QA additionally requires Playwright + Chromium in the review environment; see `qa/README.md`. It is not required to open the artifact.

After changes, regenerate screenshots, rerun browser checks, update the audit, then run `python3 tools/package.py`. Do not reuse old QA reports after editing the sources. Screenshots are review evidence; the HTML is the responsive reference.

## Scope and ownership

Delivered in `docs/.agents/dashboard_revamp` at the user's request. Application code, existing tracked WIP and deployments are outside this change. The repository remains Streamlit + FastAPI + predictive scaler. This kit does not authorize a framework migration.

SVGs and UI source are original work for this delivery; Geist fonts retain their upstream OFL. The supplied PNG is reference material and excluded from the kit's original-artwork licensing claim. See [LICENSE.md](LICENSE.md).
