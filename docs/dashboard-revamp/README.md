# Dashboard revamp implementation

Implemented 12 October 2026 against the v1.1.0 kit in `docs/.agents/dashboard_revamp`; deployed 13 October 2026 WIB after the user authorized Docker activation and deployment. Live: https://mlops.titipin.me. See `deployment/RELEASE.md` for image, runtime verification and rollback.

The Overview answers three questions: what was observed, what workload is forecast at +60s, and what replica recommendation was recorded. Its two main charts remain above the summary; model, cluster and action evidence occupy the support column. Charcoal/blue/teal, Geist, 10px panel corners and restrained spacing follow the supplied kit. Design dials: ENERGY 1 / RHYTHM 2 / MOTION 1.

## Changes

- Sidebar workspace selection preserves all eight operational workspaces and renders only the selected workspace. Their action handlers remain explicit button actions.
- `src/dashboard/overview.py` renders owned Streamlit panel containers, native inspectors, CSV export, status states, and a responsive chart/support layout. Below 1120px panels stack; metrics use two columns on compact layouts.
- `src/dashboard/adapter.py` reads only health, decisions, actions, audit and drift resources. It validates decision units and timestamps, sorts/deduplicates observations, shifts forecast targets by exactly 60s, and rejects invalid rates and replica counts.
- The Overview uses runtime policy from health. Simulator controls are explicitly local previews and do not change Overview policy or the controller.
- Actual/recommended replicas and recorded actions remain distinct. Ready-pod census, scaler mode, aligned online error, HTTP success fraction and resource saturation are explicitly unavailable. Drift is labeled demo/reference baseline; validation MAE is stored training metadata.
- Gaps over 45s split historical chart segments. The dashed latest forecast connector is explicitly a visual guide, not intermediate model outputs or a confidence interval.
- A failed/empty source produces an explicit state, without substituting kit fixtures. Stale observations remain dated. Freshness is a UI rule, `max(3 × selected read interval, 45s)`, not a measured controller guarantee.
- Owned tokens/CSS, existing local fonts/licenses and native logo assets ship inside the dashboard image. Native widget themes use `.streamlit/config.toml`.

## Local use

The existing Python environment used Streamlit 1.65.0 and Altair 6.3.0. Docker pins these versions. Run from the repository root so Streamlit reads `.streamlit/config.toml`:

```sh
INFERENCE_API_URL=http://localhost:8000 .venv/bin/streamlit run src/dashboard/app.py
.venv/bin/pytest tests/test_dashboard_adapter.py tests/test_dashboard_ui.py -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

The UI tests skip when Streamlit is absent; install the dashboard dependencies specified in `docker/Dockerfile.dashboard` to run them. The existing runtime requirements alone do not include Streamlit.

Change Light/Dark through the native app menu, then select **Refresh now**. Streamlit's context API reports theme changes on rerun; this explicit refresh avoids adding a background theme-polling component. This two-step behavior is also stated in the sidebar.

## Validation evidence

- 21 adapter/render tests passed, including all eight existing workspaces, partial failures, empty/error/stale/synthetic states and a POST rejection spy.
- 63 headless browser assertions passed using a local mock API: 1448/1024/768/390/320px, both themes, panel reflow, two evidence charts, inspectors, CSV, service-link destination, skip-link focus, keyboard refresh, state transitions and a 320px/200% text overflow check. See `browser-validation.json` for the actual assertions.
- CSV contained all 60 mock observations, source-reported synthetic flags, distinct UTC issue/target columns and a 60-second horizon.
- Overview network checks allowed only the five GET resources. No workload, prediction, retraining or model-reload action was exercised.
- Repository-wide Ruff lint/format and `git diff --check` passed.
- 34 semantic text/status/control/chart color pairs passed their contrast thresholds in both themes; `contrast.json` records the values. This is a palette check, not certification of the full application.
- Preview PNGs show **synthetic QA telemetry**, not production observations. Streamlit uses an internally scrolling main area, so desktop/mobile captures show the viewport; the bottom capture records the lower panels separately.

This is bounded browser and source validation, not a WCAG certification or evidence of model/cluster performance. The initial 63 browser assertions used mock data. Subsequent release verification built the image, rendered Overview and all eight workspaces inside a 512 MiB container, and passed nine public-browser checks. Across two rolling updates, 99 of 100 sampled health reads returned HTTP 200; one returned 502 during the second transition and the next sample returned 200. The second update disabled Streamlit usage telemetry; the final browser check recorded no POST/PUT/PATCH/DELETE requests. See `deployment/` for this separate production evidence.

## Release boundary and audit

Releases that change modules, assets or dependencies need a new dashboard image containing both Python modules, all assets and the theme configuration. The `app.py` ConfigMap mount must match that image; the old single-file hot-deploy cannot install new modules or assets. This release changed the image digest and a versioned ConfigMap reference together, retaining the old ConfigMap for rollback. See `docs/internal/AGENT_HANDOFF_OPERATIONS.md` for this boundary.

The post-implementation audit is `anti-slop/audit-001-2026-10-12.md`. Existing operational views still contain hardcoded benchmark/retraining/fallback fields; the new Overview does not use them. Their provenance and business behavior need a separately scoped correction. No new history endpoint, node census, online-error calculation, framework migration or retry/visibility subsystem was added.
