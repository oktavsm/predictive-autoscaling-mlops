# Dashboard revamp implementation

User guide: [Panduan Lengkap Dashboard](../DASHBOARD_GUIDE.md), the current inventory of all nine workspaces, sections, cards, charts, tables, inputs and buttons, including their purpose, side effects, authentication and data limits.

Current operations release: [improvements A–E](OPERATIONS_HARDENING.md), covering actual pod usage, persistent history, authenticated write controls, inventory cache and terminal timing. Write controls now require **Operator access** unlock; readers can inspect all workspaces without a token.

Latest cluster work: [dashboard/API audit and interactive Cluster Explorer](DASHBOARD_AUDIT_CLUSTER_EXPLORER.md). Includes observed node/pod/service detail, three selectable system flows, hover explanations, priorities with acceptance criteria, and the multi-file ConfigMap release procedure. Local validation uses `.venv`; container packaging belongs to cloud CI, with no local Docker build.

Implemented 12 October 2026 against the v1.1.0 kit in `docs/.agents/dashboard_revamp`; deployed 13 October 2026 WIB after the user authorized Docker activation and deployment. Live: https://mlops.titipin.me. See `deployment/RELEASE.md` for image, runtime verification and rollback.

The Overview answers three questions: what was observed, what workload is forecast at +60s, and what replica recommendation was recorded. Its two main charts remain above the summary; model, cluster and action evidence occupy the support column. Charcoal/blue/teal, Geist, 10px panel corners and restrained spacing follow the supplied kit. Design dials: ENERGY 1 / RHYTHM 2 / MOTION 1.

The 13 October operational cleanup is also deployed. It removes emoji/fabricated UI outcomes, fixes supported injector states and error feedback, and documents disabled capabilities. Validation: 53 Python tests, 189 operational plus 63 Overview mock-browser assertions, and 35 read-only production assertions. See [control inventory and limitations](FUNCTIONALITY.md), [Codex Remediation Plan (Active)](REMEDIATION_PLAN_CODEX.md), [cleanup release](deployment/cleanup-2026-10-13/RELEASE.md), and [audit 002](../../anti-slop/audit-002-2026-10-13.md).

## Changes

- Sidebar workspace selection preserves all eight operational workspaces plus Overview and renders only the selected workspace. Their action handlers remain explicit button actions. The early 13 October cleanup disabled unsupported lifecycle/retraining actions; subsequent remediation restored real Job-backed controls, and A–E hardening requires operator unlock. See [current control behavior](FUNCTIONALITY.md).
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

The initial revamp changed the image digest and a versioned ConfigMap reference together, retaining the old ConfigMap for rollback. The latest user instruction prohibits local Docker builds: validate in `.venv`, leave image packaging to cloud CI, and hot-deploy code through ConfigMaps. Cluster Explorer keeps the compatible image and mounts all five changed dashboard files individually; copying only `app.py` cannot install its new module/assets. Dependency changes still require cloud packaging and compatibility validation. See the [current multi-file release procedure](DASHBOARD_AUDIT_CLUSTER_EXPLORER.md#operasional-rilis).

Historical audits record earlier releases and disabled controls. The subsequent [functional remediation](REMEDIATION_IMPLEMENTATION.md) restores verified live operations, and [Cluster Explorer audit](DASHBOARD_AUDIT_CLUSTER_EXPLORER.md) records the current node census, interactive architecture and remaining API/operations work. Earlier findings must be read against their release date.
