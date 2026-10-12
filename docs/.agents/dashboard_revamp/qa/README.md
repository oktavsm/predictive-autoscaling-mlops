# Validation scope

Reports here apply to v1.1.0 only. The earlier v1.0 audit was insufficient for visual fidelity and is not reused.

- `structural-validation.json`: token/CSS, safe SVG, fixture alignment, anchors/offline embedding and reference integrity.
- `contrast.json`: declared foreground/background pairings in both themes.
- `browser-validation.json`: actual Chromium behavior, viewport overflow, modal/menu/forms/exports/state coverage.
- `preservation.json`: supplied PNG unchanged; tracked working-tree state/diff unchanged from the pre-revision baseline.
- `browser-check.cjs`: reproducible browser test source. Requires installed Playwright and Chromium. Use `PLAYWRIGHT_MODULE` to select an existing Playwright module if it is not on Node's module search path.

Run from the kit folder:
```sh
python3 tools/build-standalone.py
python3 tools/validate.py
node qa/browser-check.cjs
```

Do not infer production integration, statistical validity, screen-reader certification or a perfect visual match from these reports. Screenshots under previews/ and the post-build audit document the visual comparison and deliberate semantic corrections.
