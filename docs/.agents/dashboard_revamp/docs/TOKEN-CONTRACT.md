# Token contract

Version 1.1.0. `tokens/tokens.json` is the source of truth. Token objects use DTCG-style `$type` and `$value`; this is a documented portable subset, not a claim of certification against every token-tool importer. All colors are opaque sRGB hex strings. Dimensions and durations use `{ "value": number, "unit": string }`. There are no unresolved aliases. Import adapters may need conversion to a tool's native schema.

## Naming and mapping

| JSON path | CSS name | Meaning |
|---|---|---|
| `color.dark.bg`, `color.light.bg` | `--bg` | Canvas |
| `color.<theme>.surface` | `--surface` | Panel and form; sidebar uses bg |
| `color.<theme>.surface-raised` | `--surface-raised` | Header row and inset control group |
| `color.<theme>.surface-hover` | `--surface-hover` | Hover affordance |
| `color.<theme>.text` | `--text` | Primary text |
| `color.<theme>.text-secondary` | `--text-secondary` | Supporting text |
| `color.<theme>.text-muted` | `--text-muted` | Metadata, never disabled by default |
| `color.<theme>.border` | `--border` | Decorative grouping only |
| `color.<theme>.border-control` | `--border-control` | Interactive boundaries; ≥3:1 |
| `color.<theme>.accent` | `--accent` | Links, mark and limited selected product emphasis; blue |
| `color.<theme>.accent-soft` | `--accent-soft` | Background for accent labels |
| `color.<theme>.on-accent` | `--on-accent` | Text on filled accent |
| `color.<theme>.focus` | `--focus` | Keyboard focus |
| `color.<theme>.success|warning|danger|info` | Same prefixed by `--` | Status foreground |
| `color.<theme>.<status>-soft` | `--<status>-soft` | Status background |
| `color.<theme>.chart-*` | `--chart-*` | Actual blue, predicted teal, capacity neutral, threshold amber, low-contrast grid |
| `color.<theme>.button-bg|button-text` | `--button-bg|button-text` | Neutral primary action |
| `space.6` | `--space-6: 24px` | Scale slot, not literal multiplier syntax |
| `font-size.body` | `--font-size-body: .875rem` | Body scale in rem |
| `font.sans|mono` | `--font-sans|mono` | Font fallback stack |
| `radius.control` | `--radius-control: 6px` | Button/input corner |
| `size.control` | `--size-control: 38px` | Desktop input/control height; 44px touch recommendation is size.touch |
| `duration.state` | `--duration-state: 120ms` | State transition budget |
| `z.dialog` | `--z-dialog: 40` | Layer scale |

`[data-theme="dark"]` and `[data-theme="light"]` can be set on a root container. `:root` defaults to dark for monitoring sessions. Font families and sizes remain theme-independent; all ink and surfaces switch with theme. Use `color-scheme` so native controls follow the selected theme.

## Consumer example

```css
@import url("styles/variables.css");
.metric-label { color: var(--text-secondary); }
.forecast-value { color: var(--chart-predicted); }
.control { background: var(--surface); border: 1px solid var(--border-control); }
.control:focus-visible { outline: 2px solid var(--focus); outline-offset: 4px; }
```

The paths above are relative to a consumer's chosen asset root; adjust imports deliberately. The standalone HTML embeds all values and fonts, so it does not require these imports to run. In a Streamlit host, inject the variables once into the page root and scope custom styles to an owned wrapper. Do not target generated Emotion class names.

## Change policy

1. Change JSON first, then the equivalent CSS entry. Preserve the semantic name unless its role changes.
2. Test every supported foreground/background pairing and control boundary in **both** themes. Soft status surfaces have prescribed foregrounds; they are not interchangeable fills.
3. Rebuild `index.html` with `tools/build-standalone.py` and run `tools/validate.py`.
4. Inspect Overview and showcase at 1448, 1024, 768, 390 and 320 CSS pixels, plus text resize/zoom and keyboard navigation. Update visual evidence if changed.
5. Bump patch for safe value corrections, minor for additive tokens, major for renames/removals. Record migration instructions before removing a semantic name.

Borders for decoration may be below 3:1. Interactive boundaries use `border-control`. Chart gridlines are deliberately low contrast because labels and data strokes carry the information. No code should use a decorative border color as the only indication of an interactive control.

## v1.1 migration

Replace lime accent/forecast values with the paired blue/teal palette. Sidebar is 238px. Breakpoints are compact 640, navigation 900 and wide 1120px; narrow behavior uses max-width 640/899/1119 in the reference. Named spacing page 26px and gutter 18px reproduce the image. Control is 38px; touch recommendation is 44px. Section/title/metric sizes are 17/30/25px at a 16px root. Dimension/duration, font stacks, weight and z groups all have equivalent CSS variables.
