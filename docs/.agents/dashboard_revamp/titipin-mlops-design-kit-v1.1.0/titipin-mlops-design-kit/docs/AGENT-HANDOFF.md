# Agent handoff: Titipin MLOps Overview

**Read this first.** Design kit v1.1.0; local HEAD and source inspected at `2c375f34b7867a99afdc4c9859c284f5dfa4c7e3` on 12 October 2026. The kit was placed in docs/.agents/dashboard_revamp at the user’s request. Application edits and deployment remain outside this delivery. A future implementation task must supply its own authorization and scope.

## Objective and order of authority

Implement Overview so an operator can determine whether the next-minute workload will exceed current capacity, understand the replica recommendation, and inspect evidence without triggering a cluster operation.

1. Current user requirements and repository instructions govern scope.
2. The supplied `dashboard_mockup.png` governs visual composition. `docs/DESIGN-SYSTEM.md` defines deliberate semantic corrections, responsive behavior, accessibility and states. Do not restore the rejected lime palette or rearrange the reference panel hierarchy.
3. `tokens/tokens.json` defines token values; `styles/variables.css` is the equivalent CSS mapping.
4. `index.html` is a visual and interaction reference, including light/mobile variants. It is not an API specification or runtime implementation.
5. `data/synthetic-telemetry.json` is an explicitly synthetic UI view model. Never use it as a service response contract or silently fall back to it in production.

All sample telemetry, IDs, policy thresholds and timestamps in this kit are synthetic. Keep demo mode visibly labeled and isolated from measured data. Never convert a demo state into a “live” status by removing the label.

## Existing project: preserve the architecture

| Concern | Verified location | Implementation guidance |
|---|---|---|
| UI | `src/dashboard/app.py` | Streamlit, `st.set_page_config(layout="wide")`; implement here unless the user separately approves a migration |
| Model/API | `src/inference/service.py` | FastAPI owns prediction and decision evaluation |
| Scaler | `src/scaling/predictive_scaler.py` | Owns operational loop and Kubernetes patching; UI must not duplicate it |
| Drift | `src/monitoring/drift_detector.py`, service drift endpoint | Keep source/window/baseline and sufficiency visible |
| Historical registry | `models/champion_model_metadata.json`, `models/model_registry_manifest.yaml` | Stored metadata is historical, not proof of current live model |
| UI container | `docker/Dockerfile.dashboard` | Copies only `src/dashboard/`; any future static assets must be included explicitly |
| Service configuration | `docker-compose.yaml`, dashboard environment reads | Preserve configured URLs and trust boundaries |

Existing UI tabs: Telemetry Audit, Scaling Simulator, Workload Injector, FinOps & Carbon, Drift & Retraining, HPA vs Predictive, Model Registry, Cluster Architecture. Overview is a proposed read-only summary; retain existing workflows unless a future task explicitly changes them. The mockup's anchor navigation is a reference to its real local sections, not a claim that new routes already exist.

Do not introduce Next.js, React, Tailwind, a new icon package or an external chart CDN merely to match the HTML. Streamlit native controls, supported theme settings and an owned HTML/chart region are the first implementation path. Avoid brittle CSS against generated class hashes or deep Streamlit internals. Use unique wrapper selectors and verify the installed Streamlit version before relying on APIs. HTML embedded in an iframe has its own CSS scope; inject fonts/tokens there as well.

## Verified endpoint and field map

Paths below are implemented in the inspected source. They have not been called against production during this task. Preserve timeouts and partial failure handling. Some GET handlers synchronize local stores internally, so GET does not imply a perfectly pure implementation.

| Overview data | Existing resource / fields | Limits and mapping |
|---|---|---|
| Model readiness | `GET /health`: `status`, `model_ready`, `model_name`, `model_alias`, `model_version`, `model_algorithm`, `model_uri`, `load_time_ms` | Both readiness and request success are needed. Fallback version strings are insufficient. No source observation timestamp is supplied; distinguish fetch time from observation time. |
| Policy | `/health`: `target_rps_per_pod`, `replica_bounds.min`, `.max` | Use runtime values, not fixture defaults. Positive capacity required; invalid policy is an error. |
| Current observation and recommendation | `GET /scaling/decisions` array: `timestamp`, `input_rps`, `input_cpu`, `input_p95_ms`, `current_replicas`, `predicted_rps_60s`, `desired_replicas`, `action`, `latency_ms` | Each row represents a decision-loop observation. Sort/validate timestamps, don't assume array order. Label observed replica source accurately; not a Kubernetes readiness census. |
| Actual applied operations | `GET /scaling/actions`: `timestamp`, `action`, `from_replicas`, `to_replicas`, `predicted_rps`, `reason`, `status` | A recorded patch is not equivalent to ready pods. No unique decision ID joins actions to recommendations; correlation is best effort, not proof. |
| Latest five evaluations | `GET /telemetry/live-sample` | Same decision-row shape, at most five rows. Not a full time-series endpoint. |
| Audit and ingestion | `GET /operations/audit`: `timestamp`, `last_ingestion`, `ingestion_history`, `retraining`, `scaling_api`, `scaling_actions` | `scaling_api.recent_decisions` ≤30; `scaling_actions.recent_actions` ≤20. Detect seeded/pending metadata. |
| Dataset metadata | audit `last_ingestion.timestamp`, `window_minutes`, `records_count`, `target_dataset`, `raw_dataset`, `md5`, `bucket`, `status` | `live_sync_pending` is not a valid lineage identifier. Timestamp strings can combine UTC/WIB human text; normalize explicitly or show unparsed metadata, never fabricate ISO timestamps. |
| Training metadata | audit `retraining.latest`, `.challenger`, `.history` | Validate actual returned keys/types before rendering. `val_mae` is validation error, not rolling online forecast error. |
| Drift | `GET /monitoring/drift`: `timestamp`, `psi_score`, `threshold`, `status`, `overall_drift_detected`, `evaluated_cycles`, `monitored_features`, `drifted_features` | Source uses synthetic reference distributions and low-sample fallback. Display “demo/reference baseline” or “insufficient evidence” unless replaced by a validated measured baseline. |
| Workload daemon status | `GET /workload/status` | This describes workload generation; it is not predictive scaler mode. Do not equate `daemon_alive` with scaler health. |
| Autonomous scenario | `GET /monitoring/autonomous-status` | Includes orchestration/demo stage state; not measured model-quality evidence. |

The service also has `POST /predict`, whose response model contains `model_name`, `model_version`, `status`, `current_workload_rps`, `predicted_workload_rps_60s`, `recommended_replicas`, `target_capacity_rps`, `scaling_action`, `inference_latency_ms`, `timestamp`. This endpoint computes a prediction and updates service counters. A read-only Overview should consume recorded decisions rather than call it on every repaint.

`POST /scale-decision` returns an autoscaling adapter object and records a decision. `POST /model/reload`, `/workload/trigger`, `/monitoring/retrain/trigger`, `/scaling/action-record` and `/operations/record-ingestion` are outside Overview refresh. Do not wire any of them to a page load, hover, theme change, state selector or refresh button.

**Do not invent `GET /status`, `/history` or `/forecast/history`.** They are not present in the inspected inference service. If richer history is needed, propose an additive read endpoint with a separate contract and tests in the future implementation task.

## Missing capability: represent it honestly

| Desired information | Current evidence gap | Required behavior |
|---|---|---|
| 15m/30m/1h historical chart | Ring buffer max 60 rows; actual retention depends on controller cadence and restarts | Show available sample range and count. Disable unsupported ranges with explanatory text; do not stretch five samples across 1h. Every kit range is a synthetic-only example. |
| Online recent forecast MAE | No verified endpoint for matched prediction-target/actual pairs | Display “Unavailable: aligned history required”. Keep validation MAE separate. |
| Scaler mode / dry run | CLI has `--dry-run`, but no dedicated read status contract | Display “Unknown / not exposed”. Require a source-provided controller status before claiming active/predictive/dry-run. |
| Kubernetes ready replicas | Decision row has `current_replicas`, not ready/desired/available census | Label observed count/source. Add a server-side, read-only deployment observation before reporting ready pods. |
| Node readiness and CPU/memory saturation | No verified ready-node census or allocatable-resource utilization contract; model input CPU is not this census | Keep these unavailable until source, denominator and observation time are defined. |
| HTTP success/error and SLO aggregates | No verified total/failed request count or approved SLO/window contract | Show unavailable; do not derive 99.6% from model readiness, PSI or validation MAE. |
| Forecast interval | No verified quantile or uncertainty interval | Do not draw a confidence band. Dashed future line is a point forecast. |
| SLO and policy ownership | Narrative constants differ across project files | Read approved runtime configuration. Until then, label target illustrative or unavailable. |
| Stable action-to-decision ID | No verified correlation key | Avoid claiming causal match from similar timestamps. Show separate decision and action records. |

## Proposed UI adapter (not an existing endpoint)

Normalize responses behind a dashboard-only adapter. Keep the HTTP client, validation and visual renderer separate. Each block should have `state` (`loading|ready|empty|error|stale|unknown`), `source`, `fetched_at`, `observed_at` (nullable), `synthetic`, `provenance_note` and `error` (safe text). Do not mix observed-at and fetched-at.

For decisions use:

```text
issued_at_utc         <- row.timestamp, validated as UTC
forecast_target_utc   <- issued_at_utc + 60s (explicit verified model horizon)
actual_rps           <- input_rps
forecast_rps         <- predicted_rps_60s
observed_replicas    <- current_replicas
recommended_replicas <- desired_replicas
p95_latency_ms       <- input_p95_ms (already ms, do NOT multiply by 1000)
```

Inference input `p95_latency_seconds` is in seconds; convert to ms exactly once when rendering that field. Preserve distinct names to prevent unit confusion. `php_memory_mb` is model input; older raw datasets may contain bytes. Never reuse units based only on similar field names.

Each forecast point belongs at **issue timestamp + horizon**. Online MAE pairs that forecast with an actual observation at its target timestamp, under a documented tolerance. Exclude unobserved future targets. Deduplicate deterministic timestamps; never interpolate across gaps without a labeled method. Missing/NaN/negative invalid rates cannot render as zero or healthy.

The kit uses a labeled +60s inset with a different horizontal scale from history. Its dashed connector is a visual guide to one point, not a sampled forecast trajectory. Preserve the note and axis break or use a uniform time axis. The mini error chart plots aligned absolute errors; its summary is the 15m MAE. No confidence band or confidence score is available.

## Refresh, errors and source integrity

- Proposed polling: 15s with pause when hidden, one in-flight request per resource, short timeout (start with 2.5s), bounded exponential retry (15/30/60s) and manual retry. This is a proposed UI policy, not an observed project guarantee.
- Proposed freshness limit: `max(3 × configured cadence, 45s)` for sample-based panels. Stale status requires actual source observation time. APIs that lack that timestamp show “Fetched at …; observation age unknown”.
- Never call workloads, retraining or model reload while testing read-only Overview. Use mocked responses for state coverage.
- Retain last successful values as clearly labeled stale context when safe. Do not let partial model failure hide valid ingestion data. Do not show a successful export if no data was available.
- Production auth and allowed external URLs remain environment configuration. Never embed cluster tokens, API secrets or private infrastructure credentials in HTML/JavaScript/SVG.
- Use `INFERENCE_API_URL`, with existing compatibility fallbacks `INFERENCE_SERVICE_URL` and `INFERENCE_URL`. Preserve `PUBLIC_INFERENCE_DOCS`, `MLFLOW_URL`, `GRAFANA_URL`, `MINIO_URL`, `API_URL` rather than hardcoding public routes from the mockup.
- Server-side Streamlit requests keep internal service URLs private. Do not assume the browser can fetch a cluster-internal FastAPI URL or solve this by opening CORS to every origin.

## Suggested implementation sequence for a future authorized task

1. Inspect the current checkout, instructions, branch and uncommitted work. Compare current source with the pinned snapshot and update endpoint mapping if it changed.
2. Add owned brand assets/tokens under `src/dashboard/assets/` so the existing Dockerfile copy includes them. Keep upstream font licenses. Verify final image asset paths.
3. Create a small normalizing adapter using existing read resources, with explicit unavailable and provenance states. Add meaningful adapter tests for units, target-time shift, failed fetch, empty array and seeded metadata.
4. Add Overview without removing existing operation tabs. Use native Streamlit controls for stateful interactions; render charts from validated data. Apply theme through supported settings or scoped styles.
5. Validate read-only behavior with request interception/mocks. Add persistent time history only through a separately reviewed backend contract.
6. Run repository-prescribed checks and inspect light/dark/mobile/keyboard variants. Produce a reviewable diff and evidence. Deployment is a separate user-authorized action.

## Acceptance criteria

- [ ] Source architecture remains Streamlit + FastAPI + scaler; business logic is not moved into rendering code.
- [ ] Real Overview performs only approved read requests, no POST/write on repaint or refresh.
- [ ] Actual, forecast target time, recommended replicas and applied actions stay distinguishable.
- [ ] Forecast horizon, source, timestamp, unit, model and policy bounds are visible or explicitly unknown.
- [ ] No fallback, demo or seeded field is shown as measured live telemetry.
- [ ] No fabricated routes, model scores, DVC hashes, mode or ready-pod status.
- [ ] Dark/light semantic colors meet contrast; charts have patterns/labels and a data alternative.
- [ ] No page overflow at 320px; table scrolling stays within its named region.
- [ ] Keyboard focus, dialog Escape/return focus, form errors and stale/empty/error states work.
- [ ] Production screenshot contains no synthetic values unless explicitly in labeled demo mode.
- [ ] Validation MAE and online MAE are separately labeled with source/window/units.
- [ ] Font licenses, SVG provenance, runtime configuration and asset inclusion are preserved.

## Copyable implementation brief

> Implement the read-only Titipin MLOps Overview using this kit's design system and tokens in the existing Streamlit dashboard. First verify repository instructions and the endpoint mapping in AGENT-HANDOFF.md against the current checkout. Preserve existing tabs, environment URLs and service ownership. Use recorded decisions/audit/health sources, never POST prediction/scaling/workload/retraining during Overview refresh. Keep actual telemetry, forecast at t+60s, recommendations and applied operations distinct. Treat every kit fixture as synthetic and never use it as a silent production fallback. Show unavailable states for unsupported history, recent online error, scaler mode and ready-replica census. Match index.html visually at desktop/mobile and both themes, preserve keyboard/accessibility behavior, and provide a reviewable diff with validation evidence. Do not deploy without a separate instruction.
