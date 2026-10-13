# Dashboard controls and known limitations

13 October 2026 WIB. Follow-up to commit `f292ae0`. Scope: dashboard presentation, control wiring, failure handling and documentation. The inference service, scaler and traffic daemon were inspected; their business logic was not changed.

## Control inventory

| Workspace | Control | Behavior and verification |
|---|---|---|
| All | Workspace radio | Opens each of the nine workspaces. Navigation produces no operational POST. AppTest and browser coverage. |
| Read panels | Auto-refresh / Read interval | Polls Overview, Injector, Registry, Audit and HPA source panels at the selected 5/10/15/30 seconds. Turning it off disables interval selection. Manual/calculator workspaces disable these controls and state why. Refresh never submits an action. |
| All | Refresh now | Reruns the selected workspace, preserving applicable session inputs. API reads use bounded timeouts; failures are visible. |
| All | Light / Dark app menu | Native theme selection, then Refresh now applies owned tokens, charts and glyph colors. Both themes checked. This two-step limitation remains. |
| All | Connected services | Configured Grafana, MLflow, MinIO, inference docs and target API links. Public destinations returned HTTP 200 during the check; no login or business action was submitted. |
| Overview | Observation inspector / CSV export | Opens normalized observations; CSV preserves issue/target UTC timestamps, units, synthetic flag and exact 60-second horizon. Empty data has no successful export. Existing browser suite checks download contents. |
| Overview | Model / operation inspectors | Opens source metadata and separate scaling-action records. No writes. |
| Scaling Simulator | Four presets | Updates all four keyed telemetry sliders, including after a manual slider change. Preset labels match submitted values. |
| Scaling Simulator | Telemetry sliders | Current values go to `POST /predict` on Compute only. UTC hour/minute included; lag/rolling fields omitted so the service supplies its defaults. |
| Scaling Simulator | Local policy inputs | Recalculates a separate local preview with capacity and min/max bounds. Does not alter the API recommendation or live controller policy. Missing runtime policy uses visibly disclosed preview defaults. |
| Scaling Simulator | Compute forecast | Validates API success, a finite nonnegative forecast, and positive integer recommendation. HTTP errors, timeout, malformed/partial JSON, NaN, fractional replicas and rejected status show errors and clear the old result. Changed inputs label the last submitted result. Updates inference counters/gauges server-side; does not append to the decision buffer or patch Kubernetes. |
| Workload Injector | Five enabled profile buttons | Sends exactly one `/workload/trigger` POST per explicit click with a daemon-supported state. Requires API-reported daemon connection. Validates acknowledgement status and matching state; accepts HTTP 2xx acknowledgements. Shows request accepted separately from heartbeat-reported execution. Errors clear prior feedback. Keyboard activation checked. |
| Workload Injector | Drift anomaly | Disabled with a visible explanation; see unresolved backend issue below. |
| Workload Injector | Generator / coordinator panels | GET `/workload/status` and `/monitoring/autonomous-status`. Shows observed state separately from pending override, missing data as unknown, and source failures explicitly. Timeline exposes timestamp/stage/status, without decorative emoji or unverifiable narrative outcomes. |
| Drift & Retraining | Evaluate telemetry drift | GET `/monitoring/drift` only on click; invalid/failed reads clear old output. Below three samples the API substitutes demo inputs, so no live verdict is displayed. PSI reference is generated demo/reference data, not verified training provenance. |
| Drift & Retraining | Trigger retraining | Disabled with a visible reason; current backend cannot verify completion/promotion. |
| Model Registry | Metadata / telemetry expanders | Opens API-reported model metadata and records. No fabricated challenger, score, count, filename or inference latency. Configured MLflow link opens the registry. |
| HPA vs Predictive | Grafana source link | Opens configured Grafana. Fixed benchmark numbers removed; no benchmark is claimed without traceable run artifacts. API records remain inspectable. |
| Telemetry Audit | Data tables | Shows source-reported ingestion, retraining, decisions and actions, with source/provenance warnings. No UI-generated successful ingestion/retraining fallback. Native table sorting/search/download controls remain Streamlit features. |
| FinOps & Carbon | Period / CPU price / exchange rate / replica assumptions | Recomputes estimated cost and carbon for static, HPA and predictive assumptions. Negative price/allocation and invalid exchange rate blocked by native bounds. Period doubling and zero predictive allocation tested. Values are estimates, never cloud billing, observed efficiency or certified emissions. |
| Cluster Architecture | Topology text | Static handoff topology, clearly labeled as configured architecture. No live inventory/node-health claim. |

Streamlit's chart toolbar, native table tools, sidebar collapse and app settings remain framework controls. The bounded QA covers application-owned controls, CSV, sampled keyboard paths, layout and theme behavior; it is not an exhaustive test of every framework menu or browser.

## Injector profile contract

The installed `/home/dev/titipin-traffic-generator/traffic_daemon.py` on `cp-bcc` was read over SSH and its six state definitions matched the repository. UI VU/duration ranges come from those definitions, not predicted RPS or scaling outcomes.

| UI profile | Submitted state | Configured VUs | Configured duration |
|---|---|---:|---:|
| Steady normal | `STEADY_NORMAL` | 4–8 | 20–45 min |
| Rush hour | `BURST_BUSY` | 18–28 | 10–20 min |
| Flash sale | `FLASH_ANOMALY` | 50–75 | 3–8 min |
| Cooling down | `COOLING_DOWN` | 8–14 | 5–10 min |
| Quiet night | `IDLE_SILENT` | 0–1 | 5–15 min |
| Drift anomaly, disabled | `DRIFT_ANOMALY` | 35–55 | 4–10 min |

Old `RUSH_HOUR_SURGE`, `FLASH_SALE_PEAK`, `CHAOS_SPIKE`, `DRIFT_PAYLOAD_ANOMALY` and `QUIET_NIGHT` were not recognized by the installed daemon. The first, second and fifth now map to supported states; the unsupported chaos profile was replaced with the daemon's existing cooldown profile. Drift is intentionally unavailable rather than silently invoking orchestration that contaminates evidence.

## Unavailable functions and backend follow-ups

1. **Lifecycle launch/stop: absent routes.** Neither repository FastAPI decorators nor the live OpenAPI schema expose `/monitoring/autonomous-scenario/start` or `/monitoring/autonomous-scenario/stop`. Removed their misleading buttons; the coordinator remains read-only. A real cancellation contract must define job/thread cancellation and resulting traffic state before a Stop action can be offered.
2. **Manual retraining: premature fabricated outcome.** `src/inference/service.py::trigger_event_driven_retraining` changes `model_store` version and inserts fixed MAE/ingestion/decision records before `_trigger_k8s_retraining_job()` returns. It can say `MODEL_PROMOTED_AND_HOT_RELOADED` without a verified training artifact, gate or reload. Disabled the dashboard action. Re-enable only after the trigger returns job acceptance, a separate status path verifies job completion and MLflow promotion, and the loaded model artifact is confirmed. The actual operational CronJob workflow is documented in `docs/internal/AGENT_HANDOFF_OPERATIONS.md`, section 4.D; it was not executed for this cleanup.
3. **Drift orchestration: unmarked demo records.** `trigger_workload_state(DRIFT_ANOMALY)` seeds shared decision buffers and starts `_run_autonomous_drift_sequence`; its staged records include fixed metrics and claims. Disabled drift injection in the dashboard. Real workload generation and lifecycle/demo orchestration need separate provenance before re-enabling it. Do not use the old state name as a workaround.
4. **Audit/model provenance: backend remains mixed.** The service seeds counters/history and can insert demo model/decision metadata. The UI removes its own fake fallbacks, labels source records, and warns that charts and raw metadata are API reports, not independently verified measurements. Backend data cannot be retrospectively classified reliably by this UI. Separate demonstration buffers or explicit per-record provenance is still needed.
5. **HPA benchmark: artifact missing.** Removed the fixed reaction-time, P95, success-rate and error-rate table. Restore a comparison only with paired workload runs and links to measured artifacts.
6. **FinOps: assumptions only.** No billing feed, certified carbon factor or clean observed allocation series is connected. Inputs and fixed illustrative CPU/RAM/carbon factors are disclosed. The old fake live coefficient and arbitrary efficiency percentage were removed.
7. **Theme: refresh required.** Streamlit context reports native theme changes on rerun. Select a theme, then Refresh now. No polling component was added.

These backend limitations are documented and visible; this change does not claim that unsupported functions now work. No production traffic profile, prediction, retraining, model reload or scaling mutation was submitted as a test.

## Evidence and rerun

- `tests/test_dashboard_adapter.py` and `tests/test_dashboard_ui.py`: 53 passing tests, including controlled button/API failures and contract checks against FastAPI decorators and daemon states.
- Existing Overview suite: 63 passing browser assertions on the follow-up code, including CSV content, both themes, five widths, inspectors and keyboard refresh.
- 189 operational browser assertions passed, including polling off/on/off, all five profile buttons, keyboard activation, both themes and caption opacity. Results, synthetic previews and public link checks: `validation/`. The 35 read-only production checks and deployed source hashes are in `deployment/cleanup-2026-10-13/`.
- All HTTP action cases use local mocks, including accepted request versus actual execution. Installed-daemon inspection and public GET/OpenAPI checks verify compatibility, not end-to-end workload execution.

```sh
.venv/bin/pytest tests/test_dashboard_adapter.py tests/test_dashboard_ui.py -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
# Start these in separate terminals, then run the action suite:
python3 docs/dashboard-revamp/validation/mock_api.py
INFERENCE_API_URL=http://127.0.0.1:18766 STREAMLIT_BROWSER_GATHER_USAGE_STATS=false .venv/bin/streamlit run src/dashboard/app.py --server.port=18765 --server.address=127.0.0.1 --server.headless=true
NODE_PATH=/tmp/titipin-ui-qa/node_modules node docs/dashboard-revamp/validation/controls.cjs
```

The browser script deliberately fixes loopback targets so its action suite cannot accidentally run against production. It requires Playwright and an installed Chromium; both were already available in the temporary QA environment. No production dependency was added.
