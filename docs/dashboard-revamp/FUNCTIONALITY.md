# Dashboard operational controls

13 October 2026 WIB. Implements [REMEDIATION_PLAN_CODEX.md](REMEDIATION_PLAN_CODEX.md). The earlier restricted UI audit is preserved in [FUNCTIONALITY_PRE_REMEDIATION.md](FUNCTIONALITY_PRE_REMEDIATION.md).

| Workspace | Current behavior |
|---|---|
| Overview | Live controller decisions, forecast horizon, workload, latency, replica recommendations and applied scaling events. Empty, stale and failed sources stay distinguishable. |
| Scaling Simulator | Explicit `/predict` request with selected telemetry. Validates finite output; failures clear old results. Preview policy does not alter cluster policy. |
| Workload Injector | All six daemon profiles enabled while heartbeat is fresh. ACK and observed execution stay separate. Explicit start/stop lifecycle routes; progress, timestamps, phase titles, owned job and verified completion metrics. |
| Drift & Retraining | Five-feature PSI against mounted reference CSV. Explicit retrain returns HTTP 202 acceptance. Status follows actual Kubernetes completion, shared holdout evaluation and loaded champion. |
| Model Registry | Champion/challenger alias cards, actual run metrics, serving version, named datasets and verified MinIO CAS lineage. |
| Telemetry Audit | Ingestion, registry history, controller decisions and executed scaling actions in formatted tables. |
| HPA vs Predictive | Six-row 65 VU reference comparison from the remediation plan, with its source identified; separate live SLO/replica/forecast cards. |
| FinOps & Carbon | Mean desired replicas from current validated decisions drives four estimate cards and cost/carbon charts. Rates, period, baseline and carbon assumptions remain explicit. No-data fallback is labeled a preview. |
| Cluster Architecture | Actual Kubernetes node readiness and pod placement, serving health and controller activity, remote generator heartbeat and configured public routes. No IP addresses exposed. |

Every read workspace supports the selected 5/10/15/30-second refresh interval. Polling and navigation do not issue writes. Light/dark theme selection applies on Refresh now, preserving the supplied kit, Geist fonts and SVG assets.

## Backend lifecycle

Start and retrain reject concurrent operations with HTTP 409. Offline drift injection is rejected. The worker copies the deployed CronJob template, waits for terminal Job conditions, reads the successful container termination result and loads the exact registry champion. A job failure, absent result, failed reload or version mismatch cannot produce success. The prior serving model remains loaded on reload failure.

Stop sets `STOPPING`, cancels only the operation's owned job with foreground deletion, and reports `STOPPED` after the job disappears. Traffic returns to `STEADY_NORMAL`. A cancellation failure stays active as `STOP_FAILED` and requires operator inspection; it cannot silently launch another training cycle. Stop cannot undo an alias promotion that already completed before cancellation.

## Storage and provenance

New training uses the `predictive-autoscaling-live` experiment with MinIO S3 artifacts. The MLflow SQLite registry uses `mlops-mlflow-state` PVC. Kubernetes Secret `mlops-object-storage` supplies S3 credentials; there are no default credentials in the sync helper. The inference pod mounts the actual baseline CSV from `mlops-training-data`. Startup may use an available local model when registry access fails; strict reload cannot relabel that fallback as a registry version.

MinIO dataset metadata records actual row counts, raw source and content hash. Audit refresh verifies the matching CAS object before claiming sync. Older objects may have unknown row counts. Metadata refresh runs off the health/status request path.

## Practical limits

The benchmark reference is not a new experiment. FinOps/carbon outputs are estimates from a recent decision window, not invoices or whole-month measurements. PSI uses the configured demo reference, so a shift from that reference alone is not proof of production model degradation. Drift traffic sends a bounded 2 KiB header; its measured effect depends on the application.

Decision buffers and lifecycle status are process-local and reset on inference restart. Keep one inference replica for this coordinator. Kubernetes Jobs, MLflow metadata and S3 artifacts persist independently. The MLflow PVC uses local-path storage on one node, so it still needs external backup for node loss. Runtime dependency installation requires package-index availability at pod startup.

See [REMEDIATION_IMPLEMENTATION.md](REMEDIATION_IMPLEMENTATION.md) for deployment, verification and recovery evidence.
