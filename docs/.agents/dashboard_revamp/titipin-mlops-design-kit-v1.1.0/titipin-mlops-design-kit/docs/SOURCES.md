# Sources, reconstruction and evidence boundaries

Inspected 12 October 2026. The current local checkout and source were inspected read-only. At the user’s subsequent request, this kit was written only into docs/.agents/dashboard_revamp. Application code, tracked working-tree changes and deployments were preserved.

## Conversation

Referenced ChatGPT conversation: “Referensi desain dashboard”, ID `6accce0d-8ae0-83ec-9a65-795bb39134f3`. The available history confirms the chosen Vercel-minimal and Better Stack-observability direction, Overview-first focus, a complete design kit, and custom SVG assets for agent reference.

The earlier delivery lacked the actual image and reconstructed the direction. The user rejected that result as visually generic and supplied the original Overview PNG during this revision. The PNG now governs composition, density and palette. The v1.0 structural/color audit did not establish visual fidelity and is not reused as approval.

## Supplied visual authority

- File: `dashboard_mockup.png`, preserved byte-for-byte.
- SHA-256: `b3b36ebf3a86989f8e365e0b1b0f67c15841532bbde1f3dc15484e286bdc0a18`.
- Original dimensions: 1448 × 1086.
- Retained: charcoal/blue/teal tone, 238px sidebar, four top cards, left forecast/scaling, right health/cluster/events, bottom decision/SLO.
- Deliberate corrections: synthetic/demo provenance, consistent event/replica arithmetic, pending vs applied separation, labeled separate forecast time scale, no unsupported confidence band, no generic AI sparkle, original logo proposal rather than a traced reference symbol.
- Pixel-identical reconstruction is not claimed. Rendered previews and the v1.1 audit record the actual comparison.

## Project source snapshot

Repository: [oktavsm/predictive-autoscaling-mlops](https://github.com/oktavsm/predictive-autoscaling-mlops).

Local HEAD matches the previously inspected `main` snapshot, commit **`2c375f34b7867a99afdc4c9859c284f5dfa4c7e3`**, committed 9 October 2026. Links below pin the inspected revision. File presence and source behavior are evidence of code, not evidence that a deployment is healthy.

| Source | What it supports |
|---|---|
| [Dashboard app](https://github.com/oktavsm/predictive-autoscaling-mlops/blob/2c375f34b7867a99afdc4c9859c284f5dfa4c7e3/src/dashboard/app.py) | Streamlit UI, environment URLs (lines 22–32), existing tab structure (380–391), API consumers and fallback rendering |
| [Inference service](https://github.com/oktavsm/predictive-autoscaling-mlops/blob/2c375f34b7867a99afdc4c9859c284f5dfa4c7e3/src/inference/service.py) | Actual response fields, GET resources and write/compute endpoints |
| [Scaler](https://github.com/oktavsm/predictive-autoscaling-mlops/blob/2c375f34b7867a99afdc4c9859c284f5dfa4c7e3/src/scaling/predictive_scaler.py) | Kubernetes writes belong to scaler; dry-run flag exists; defaults and bounds are runtime-configurable |
| [Drift detector](https://github.com/oktavsm/predictive-autoscaling-mlops/blob/2c375f34b7867a99afdc4c9859c284f5dfa4c7e3/src/monitoring/drift_detector.py) | Drift definitions and threshold context |
| [Dashboard Dockerfile](https://github.com/oktavsm/predictive-autoscaling-mlops/blob/2c375f34b7867a99afdc4c9859c284f5dfa4c7e3/docker/Dockerfile.dashboard) | Streamlit process on 8501; current image copies `src/dashboard/` only |
| [Compose services](https://github.com/oktavsm/predictive-autoscaling-mlops/blob/2c375f34b7867a99afdc4c9859c284f5dfa4c7e3/docker-compose.yaml) | Existing service and environment arrangement |
| [Champion metadata](https://github.com/oktavsm/predictive-autoscaling-mlops/blob/2c375f34b7867a99afdc4c9859c284f5dfa4c7e3/models/champion_model_metadata.json) | Historical stored run/horizon and validation metrics, not authoritative live version |
| [Registry manifest](https://github.com/oktavsm/predictive-autoscaling-mlops/blob/2c375f34b7867a99afdc4c9859c284f5dfa4c7e3/models/model_registry_manifest.yaml) | Stored model/policy metadata; not a runtime readiness guarantee |
| [Existing dashboard documentation](https://github.com/oktavsm/predictive-autoscaling-mlops/blob/2c375f34b7867a99afdc4c9859c284f5dfa4c7e3/docs/DOKUMENTASI_LENGKAP_STREAMLIT_DASHBOARD.md) | Prior navigation and operational context |

## Design and accessibility references

- [Vercel Geist](https://vercel.com/geist/introduction): reference for restrained hierarchy, typography and component consistency. No Vercel brand symbols or component source were copied.
- [Better Stack log management](https://betterstack.com/log-management): reference for operational context, time-scoped evidence and readable event detail. No Better Stack identity assets were copied.
- [WCAG 2.2 quick reference](https://www.w3.org/WAI/WCAG22/quickref/): contrast, reflow, keyboard, focus, semantics and status requirements. This kit is not an accessibility certification.
- [Geist font source](https://github.com/vercel/geist-font): bundled variable font binaries and upstream OFL, retrieved 12 October 2026. Per-file SHA-256 values are in the package manifest.

## Known source limitations that the UI must respect

1. **Fallback health and versions:** `app.py` falls back to version/algorithm values when calls fail. `service.py` also contains fallback model-version values. A non-empty string alone is not evidence of a loaded model.
2. **Seeded audit metadata:** the ingestion store initializes record counts and a pending-sync identifier. Render pending/seeded fields with explicit provenance; do not show a green “ingested” state based on these alone.
3. **Drift source:** `/monitoring/drift` constructs a random reference distribution in source and falls back to a one-element live array when decision samples are insufficient. Its output is not automatically a validated production baseline or statistically sufficient drift test.
4. **Demo orchestration:** autonomous scenario stages include preset PSI/MAE/latency descriptions. Those descriptions cannot be promoted to measured outcomes without independent evidence.
5. **Limited history:** decisions are an in-memory ring buffer (60 maximum); `/telemetry/live-sample` returns five rows. A time selector cannot truthfully promise persisted 1h/24h history from these resources.
6. **Inconsistent narrative constants:** stored manifest descriptions and UI explanatory copy may differ from structured metric values and runtime policy. Prefer verified runtime fields with timestamps; otherwise label unavailable. Do not resolve conflicts by choosing the more flattering number.
7. **No live inspection:** this delivery did not query a production status endpoint, operate a cluster, benchmark a model, inspect credentials, or test deployed authentication.

Older project memory was used only to locate context and preserve the operational distinction between prediction, observed telemetry and applied scaling. All current architecture and endpoint claims in this kit were rechecked against the pinned source above.
