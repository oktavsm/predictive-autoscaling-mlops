# Titipin MLOps design system

Version 1.1.0 · reference-led Overview · 12 October 2026.

## Visual authority and intent

The user-supplied `dashboard_mockup.png` is the primary authority for composition, information density and visual tone. “Vercel minimal + Better Stack observability” describes restraint, consistent typography, time-scoped evidence and readable operational detail. It does not authorize replacing the supplied dashboard with a generic SaaS landing page.

The operator should answer: Is serving healthy? What is the next-minute workload? How many replicas are observed and recommended? What actually happened? Put the chart evidence ahead of explanatory prose. Keep labels short, units visible and causality bounded by source evidence.

Design dials: **ENERGY 1 / RHYTHM 2 / MOTION 1**. Quiet monitoring surfaces, an intentionally unequal chart/support hierarchy, and no ambient movement. The visual read was stated before revision: retain charcoal/blue/teal, compact cards, two large charts left, three support panels right, decision/SLO below.

Preserve the reference's charcoal canvas, slightly lighter panels, slate selected navigation, blue actual line, teal dashed forecast, and green readiness. Avoid lime product emphasis, gradients, glow, oversized headings, decorative dot grids, generic AI sparkle/brain/robot symbols and empty marketing panels. The custom geometric T is an original identity proposal; the dashboard itself carries the hierarchy.

## Foundation

### Semantic palette

Opaque sRGB colors. The complete paired palette appears below; `tokens/tokens.json` owns the values and `styles/variables.css` maps them to CSS. Use semantic names in consumers. Do not hardcode a hex color into a widget.

| Semantic token | Dark | Light |
|---|---|---|
| `bg` | `#101418` | `#F4F6F9` |
| `surface` | `#171C22` | `#FFFFFF` |
| `surface-raised` | `#1D2530` | `#EDF1F6` |
| `surface-hover` | `#252E39` | `#E6ECF4` |
| `text` | `#F3F5FA` | `#141B27` |
| `text-secondary` | `#C5CEDC` | `#3F4D64` |
| `text-muted` | `#A6B1C2` | `#56657B` |
| `border` | `#28313A` | `#D1D9E4` |
| `border-control` | `#78899F` | `#728197` |
| `accent` | `#7DA7FF` | `#265DB5` |
| `accent-soft` | `#1B2B46` | `#E8EFFB` |
| `on-accent` | `#111A2B` | `#FFFFFF` |
| `focus` | `#97BAFF` | `#265DB5` |
| `success` | `#65DBB1` | `#116747` |
| `success-soft` | `#143129` | `#E6F5ED` |
| `warning` | `#E9BC69` | `#785000` |
| `warning-soft` | `#332A19` | `#FFF3DA` |
| `danger` | `#FFA5AC` | `#A12641` |
| `danger-soft` | `#38232B` | `#FCE9ED` |
| `info` | `#97BAFF` | `#265DB5` |
| `info-soft` | `#1B2B46` | `#E8EFFB` |
| `chart-actual` | `#7DA7FF` | `#265DB5` |
| `chart-predicted` | `#57DDD2` | `#00766F` |
| `chart-capacity` | `#ADBCD1` | `#5B697D` |
| `chart-grid` | `#28313A` | `#D1D9E4` |
| `chart-threshold` | `#E9BC69` | `#785000` |
| `button-bg` | `#EDF1F7` | `#172131` |
| `button-text` | `#131922` | `#FFFFFF` |


Use `bg` for the canvas/sidebar; `surface` for panels; `surface-raised` for inset controls/table headers; `surface-hover` for hover and selected navigation. Elevation comes from these surfaces and borders, not shadows. A single dialog/toast shadow may establish overlay depth.

Blue `accent` serves links, the original mark and a few high-level values. `chart-actual` is blue; `chart-predicted` is teal. Green means healthy/ready or applied scale up. Amber means pending/stale or applied scale down, not automatic failure. Red means failed/invalid. Unknown uses text plus info color. A direction alone is not a favorable/adverse outcome.

`border` groups static content and may be low contrast. Any boundary required to recognize an input or standalone button uses `border-control`. Text-only actions and icon controls have explicit affordances and focus treatment. Never use only color to communicate state.

### Typography

Geist Sans is bundled locally for UI; Geist Mono for precise timestamps, identifiers, code and tabular values. Keep section headings and prominent metrics in Sans as in the reference. Both are variable WOFF2 fonts with their upstream SIL OFL. Fallbacks are `system-ui, sans-serif` and `ui-monospace, monospace`; no external font request is required.

| Role | Default | Weight / line height | Guidance |
|---|---|---|---|
| Page title | 30px / 1.875rem | 650 / 1.2 | 28px compact; sentence case; tracking −0.7px |
| Section heading | 17px / 1.0625rem | 600 / 1.4 | 16px compact |
| Metric | 25px / 1.5625rem | 600 / 1.25 | 19–23px for dense secondary values |
| Body | 14px / .875rem | 400 / 1.5 | Summary text 13px / 1.9 |
| Support | 13px / .8125rem | 400 / 1.5 | Chart description and metadata |
| Small | 12px / .75rem | 400 / 1.5 | Event rows and secondary metrics |
| Dense chart/meta | 11px / .6875rem | 400 / 1.5 | 10px only for ancillary notes; essential chart text ≥11px |

These sizes assume a 16px browser root. CSS uses rem for text so user preferences work. Use tabular numerals for times and aligned numeric columns. Do not uppercase entire navigation labels. Avoid tracking on body text. Headings wrap; event previews may truncate only when full text is available in details.

### Spacing, shape and layering

Base scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64px. Named optical tokens: `space.gutter = 18px` and `space.page = 26px` reproduce the reference. Use 18px between desktop panels, 16px compact. Panel padding 14px vertical / 19px horizontal; metric padding 18px / 20px. Showcase panels use 24px.

Panel corner 10px; compact input/button 6–7px; selected navigation 8px; dialog 12px. These slight optical variations are intentional. Do not round full panel edges into pills. Only status dots, active pod indicators and progress bars are capsules.

Desktop controls are 38px high; navigation 46px. Icon buttons are normally 32px, panel inspection controls 24px with separated hit areas. WCAG 2.2 minimum target is 24 × 24 CSS px or the applicable spacing exception. Below 900px, buttons and selects use at least 44px targets; panels grow to accommodate them. The `size.touch` token is 44px, while desktop density stays close to the reference.

Layer tokens: base 0, nav 20, dialog 40, toast 50. Native modal dialogs use the browser top layer. Focus outline is 2px with 4px offset and must not be clipped. No ambient animation. State transitions may use 120ms; reduced motion disables movement and smooth scrolling.

## Overview geometry

At the supplied 1448px desktop width:

| Region | Reference rule |
|---|---|
| Sidebar | 238px fixed, 18px horizontal padding, 24px top inset |
| Main | 26px horizontal inset, 24px top |
| Header | Title/description left; time + demo + replay and environment right |
| Status cards | Four equal columns, approximately 124px high; 17–18px gaps |
| Monitoring grid | Left:right ratio 1.78:1; 18px gutter |
| Left | Workload Forecast 314px; 18px gap; Scaling Decisions 320px |
| Right | Model Health 222px; Cluster Status 234px; Recent Events 160px; 18px gaps |
| Bottom | Two equal columns; decision summary and SLO; minimum 144px |
| Provenance footer | Discreet but visible, below the panels |

Heights above are default-density targets, not content clipping limits. Increase height for larger text, translations or longer source errors. The responsive HTML demonstrates the exceptions. Do not replace the two main charts with decorative KPI tiles. Keep card headlines, descriptions, axes and status distinctions aligned to the supplied image.

Navigation contains Overview, Autoscaling, Model Lifecycle, Infrastructure, Evaluation, Activity & Audit, Lab Controls. In this artifact these are anchors to actual sections; Lab Controls opens the component showcase. They are proposed information architecture, not existing production routes. All enabled links resolve. Do not invent a “page coming soon” modal to disguise missing navigation.

## Chart grammar and statistical honesty

1. **Actual:** solid blue 2px stroke, 7% blue area fill to zero. Preserve real peaks; never smooth away workload spikes.
2. **Forecast:** dashed teal 2px stroke, explicit target time and horizon. Only the latest point at issue time +60s is promised by the fixture.
3. **Inset:** history ends at the dashed Now boundary; the right 16% (minimum 66px) illustrates a separately scaled +60s region. Axis break and the note “Future inset: separate +60s time scale” are mandatory. The connecting dashed segment is a visual guide, not intermediate model outputs. Production may instead use a uniform time axis if sufficient pixels and labels are available.
4. **No confidence band:** the current project has no verified quantiles/uncertainty contract. Do not borrow the reference's shaded forecast interval or turn a scalar model score into an interval.
5. **Axes:** workload in req/s, zero baseline, fixture range 0–400. Observed replicas use step interpolation and a zero-based integer axis 0–10 (policy max 8 remains separately visible). Show WIB timezone in nearby text; CSV retains UTC.
6. **Scaling events:** triangle + label at the actual operation timestamp; green up / amber down. Pending 3→4 is textual context and not an applied step.
7. **Model error:** MAE = mean absolute error across 61 matched target pairs in 15m. The mini line plots per-pair absolute error, in req/s. Do not call that line a rolling MAE series. Validation MAE remains distinct.
8. **SLO:** p95, success fraction and CPU saturation have named windows/denominators. Synthetic success/CPU sparklines are illustrative, not evidence derived from the aggregate counts. Do not add flattering deltas.
9. **Grid:** sparse 1px low-contrast horizontals and time ticks. No crosshair required in the artifact. Never use a chart grid as a page texture.
10. **Responsive:** compute SVG viewBox from the actual container. Preserve 11px labels; use two time intervals below 420px instead of shrinking an entire desktop plot. Recompute when fonts, theme views or sizes change.
11. **Alternatives:** meaningful chart name, inspect-data dialog and full synthetic CSV. Inspection tables have headers and named keyboard-scroll regions. Color/pattern/labels jointly identify each series.

If a production observation or metric is unavailable, show unavailable with reason. Do not fill gaps with the kit's data. Forecast origin/target alignment, recommended/applied state and ready/observed replicas are contractual distinctions.

## Reusable components and behavior

| Component | Anatomy / rules | States and interaction |
|---|---|---|
| Workspace shell | Brand, caption, nav, environment/footer | Selected aria-current, hover, focus; mobile expandable in flow |
| Page header | H1, scope/provenance, controls | Time selector updates history; replay keeps frozen synthetic time |
| Metric card | Domain glyph, label, headline, supporting unit, chevron | Real anchor; hover border-control; focus outline |
| Monitoring panel | H2, short scope text, inspection control, visualization | Partial failure stays local; title always remains |
| Status | Dot + readable text; optional soft background | Healthy, pending/stale, failed, unknown; no color-only state |
| Node tile | Node name + Ready text + dot | Opens full synthetic census; production requires actual source |
| Pod slots | Active count + policy bound, outlined inactive slots | Slots encode quantity, not readiness from a decision record |
| Resource meter | Label, native meter, percent | Named denominator; missing never zero |
| Event row | Status/direction, timestamp, event name | Truncated preview opens full detail through panel inspection |
| Decision summary | Recommendation, issue time, horizon, calculation, status | Pending distinct from applied; no unverifiable confidence |
| SLO group | Metric name, number/unit, spark | Window and denominator in inspection; no fabricated delta |
| Button | Verb, optional utility glyph | Primary neutral fill; secondary border; disabled explained nearby |
| Input | Persistent label, unit, hint, error, local result | Integer 1–1000, aria-invalid + described error, focus first error |
| Table | Caption, scoped column headings, units | Numeric right aligned, named horizontal scroll region |
| Dialog | Named title, close button, content, provenance | Native modal, focus contained, Escape closes, focus returns to trigger |
| Toast | Short confirmation, status semantics | No network success claims; live region; never sole error evidence |
| State pattern | Title, reason, next useful action | Ready/loading/empty/error/stale/unknown; retry is local in mockup |

Inspection buttons and export controls must do what their labels promise. The standalone's capacity form previews a calculation without editing the dashboard's canonical synthetic policy. This prevents the Overview from showing a changed target alongside frozen recommendations.

## Responsive rules

- **≥1120px:** monitoring columns; four status cards. Below 1321px, legends return to normal flow to prevent collision with descriptions. Desktop sidebar remains fixed.
- **900–1119px:** four cards become 2×2; main charts stack; health/cluster pair; events span the row; bottom panels stack.
- **641–899px:** navigation becomes an in-flow collapsed menu. Four metrics may remain on one row; monitoring charts stack; health/cluster pair. No overlay obscures content.
- **≤640px:** metrics 2×2, all monitoring and bottom panels one column; 16px page inset. Header controls wrap, secondary environment suffix may hide but demo provenance remains. No horizontal page scrolling at 320px.
- **Large text:** above a 20px user root size, switch to one-column content, auto panel heights, wrapping navigation/events, taller chart/data alternatives. Keep real content rather than clipping into fixed reference heights.
- Tables scroll within named regions. Touch/pointer actions never require hover. Use native selects and input behavior.
- Preserve reading order: headline status, workload evidence, scaling evidence, health, cluster, events, summary, SLO. The DOM follows that order.

## Accessibility and UI/UX acceptance

Target WCAG 2.2 AA for implementation; the kit is not a certification. Verify the deployed Streamlit/iframe context independently.

Text contrast ≥4.5:1 (large text ≥3:1); essential non-text strokes/boundaries ≥3:1. Prescribed color pairings are measured in `qa/contrast.json`. Decorative panel borders/gridlines are not input boundaries. Keyboard focus is visible in both themes; a skip link reaches main. Native semantics include navigation, articles/headings, form labels, meter, table and modal dialog.

Test keyboard-only navigation, selector changes, menu expansion, dialog containment/Escape/focus restoration, invalid field feedback, and retry. Dynamic status uses polite live regions; blocking errors remain beside the input/panel. Never pulse a green dot to imply live data. Respect reduced motion and high-contrast/forced-colors preferences.

Check 320, 390, 768, 1024 and 1448 CSS px, both themes and both views. Also test 200% text resize and a 200% zoom-equivalent viewport reflow. Ensure charts remain readable and controls do not overlap. Automated checks establish specific assertions, not universal accessibility.

## Operational copy and telemetry states

Use concrete verbs and facts: “Recommend 3 → 4”, “Pending”, “Observed at …”, “Unavailable: aligned history required”. Avoid “AI-powered”, “intelligent insights”, “seamless”, or generic “Everything looks great”. Summary prose cites the arithmetic and status; never claim an operation happened solely because a recommendation exists.

Loading means no observation yet. Empty means the source returned no rows for the selected window. Error means a request/validation failed. Stale retains clearly dated last-known data; the production threshold must be configured. Unknown means the capability/source is not exposed. The showcase's 2m stale threshold is illustrative and distinct from the future implementation polling proposal.

Keep `synthetic: true` in fixture rows and exports, visible synthetic labels in the page and dialogs, and demo labels in screenshots. Do not label synthetic data Live. Export time fields are issue and target UTC, not two names for the same timestamp.

## Implementation boundary

Use the verified Streamlit + FastAPI architecture in AGENT-HANDOFF.md. Node census, allocatable-resource percentages, HTTP counts and aligned historical forecasts are design requirements with source gaps. They are not new implemented APIs. No package installation, repository rewrite, backend behavior change or deployment is implied by this visual artifact.

After modifying tokens/source: rebuild, validate, inspect actual screenshots against the supplied PNG, rerun browser cases, update audit findings and regenerate manifest/ZIP. Never call the system production-verified solely because the HTML renders.
