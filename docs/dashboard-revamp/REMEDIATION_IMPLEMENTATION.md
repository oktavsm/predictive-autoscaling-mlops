# Dashboard remediation implementation

13 October 2026 WIB. Scope: [remediation blueprint](REMEDIATION_PLAN_CODEX.md), supplied design kit, inference API, CT pipeline, storage, daemon, deployment and verification. Work is on `feat/dashboard-remediation`.

## Delivered behavior

The [control inventory](FUNCTIONALITY.md) describes all nine workspaces. Drift injection, manual retraining and explicit lifecycle start/stop are enabled. Progress follows the owned Kubernetes Job and real results. Dashboard navigation and polling remain read-only. The supplied theme, tokens, Geist fonts and SVG assets are retained.

Backend history begins with actual observations. Five-feature PSI uses the configured CSV reference and controller measurements, including a rolling mean of observed RPS. Live SLO cards, mean-replica FinOps estimates, node readiness, pod placement, model aliases, dataset metadata and CAS verification use backend sources. The 65 VU comparison comes from the blueprint and is explicitly identified as a reference; no new benchmark result is claimed.

Retraining ingests live Prometheus data, preprocesses it, uploads named datasets and CAS objects, trains four candidates, and compares the best candidate with the current champion on the same chronological holdout. A worse candidate remains challenger. The registered version must load successfully before either alias changes. Serving completion additionally requires a successful termination result and the exact reported champion loaded into inference.

## Storage fixes discovered during live validation

The old registry champion v40 pointed at a local artifact absent from inference. The startup fallback actually served a different available local model. Its exact artifact was preserved in MinIO and registered as **v41**, tagged `RECOVERED_SERVING_BASELINE`; the unavailable v40 alias is preserved as `legacy-champion`. This is recovery provenance, not an evaluation claim.

The old MLflow server also used an ephemeral SQLite database. Its active database was backed up before migration and copied to `mlops-mlflow-state`, a 5 GiB local-path PVC. Direct single-process Uvicorn is retained because the MLflow CLI parent plus server exceeded the old container memory limit. Explicit `_MLFLOW_SERVER_FILE_STORE` and artifact variables configure the pinned MLflow runtime; a readiness probe checks its HTTP health. A restart retained registry version 41.

New training uses `predictive-autoscaling-live` with S3 artifacts at `s3://mlops-dvc/mlflow/live`. Credentials come from `mlops-object-storage` Secret. The sync helper no longer supplies default credentials. Required-checksum SDK configuration avoids a `MissingContentLength` rejection on the existing MinIO endpoint; the setting is described in the [AWS SDK data-integrity documentation](https://docs.aws.amazon.com/sdkref/latest/guide/feature-dataintegrity.html).

MLflow 3 logs models independently of the run's `artifacts/model` directory. Registration now uses the loaded candidate's actual artifact URI and verifies delivery through the new registry version before promoting it. Earlier v42 had passed numerical evaluation but had an invalid legacy registration source; it is retained with `artifact_delivery=FAILED_LEGACY_RUNS_URI`. The serving alias was restored to verified v41 before the corrected job ran.

## Deployed release

| Component | Release |
|---|---|
| Dashboard image | `remediation-20261013-0126@sha256:94c6a94cb639fcebc0f7f77b0a06130c16db601d26d9a6d1b760dfe1771965d0` |
| Dashboard code ConfigMap | `mlops-dashboard-code-remediation-20261013-0126` |
| Inference code ConfigMap | `mlops-inference-code-remediation-20261013-0308` |
| CT code ConfigMap | `mlops-ct-code-remediation-20261013-0308` |
| Inference / CT / MLflow base image | `predictive-autoscaler@sha256:830ad467010fdf4bd4139a6be11ccc2087d8642ae655f21fe706c9e603d32588` |
| Daemon | Updated `traffic_daemon.py` and `k6_scenario.js`, restarted existing `titipin-traffic-generator` unit |

The inference pod mounts `mlops-training-data` as its reference CSV. RBAC now permits node inventory and creating, reading and deleting owned training Jobs. Code ConfigMaps are immutable and versioned. Source manifests match the pinned deployment. No public IPs or secret values are included here.

## Reproduce a release

Provision `mlops-object-storage` from private credentials, preserve the MLflow database before its first PVC migration, and retain `mlops-training-data`. Create the versioned ConfigMaps before applying workloads:

```bash
kubectl create configmap mlops-inference-code-remediation-20261013-0308 -n mlops \
  --from-file=src/inference/service.py --from-file=src/scaling/predictive_scaler.py \
  --from-file=src/data/minio_sync.py
kubectl create configmap mlops-ct-code-remediation-20261013-0308 -n mlops \
  --from-file=src/pipeline/continuous_training.py --from-file=src/monitoring/drift_detector.py \
  --from-file=src/models/train.py --from-file=src/models/register_model.py \
  --from-file=src/data/minio_sync.py --from-file=src/ingest_data.py \
  --from-file=src/preprocess.py
kubectl create configmap mlops-dashboard-code-remediation-20261013-0126 -n mlops \
  --from-file=src/dashboard/app.py
for cm in mlops-inference-code-remediation-20261013-0308 \
          mlops-ct-code-remediation-20261013-0308 \
          mlops-dashboard-code-remediation-20261013-0126; do
  kubectl patch configmap "$cm" -n mlops --type=merge -p '{"immutable":true}'
done
kubectl apply -k infrastructure/kubernetes/mlops
kubectl rollout status deployment/mlops-inference -n mlops --timeout=120s
kubectl rollout status deployment/mlops-dashboard -n mlops --timeout=120s
kubectl rollout status deployment/mlops-mlflow -n mlops --timeout=120s
```

Use a new ConfigMap name and update the manifest when source changes. The matching dashboard image contains assets and shared modules. Do not overwrite a live release ConfigMap. Verify registry/serving version equality, heartbeat, live observations and successful job termination after deployment; pod readiness alone does not prove model delivery.

## Verification and recovery

Automated tests cover controls, read-only polling, errors, stale data, finite outputs, job acceptance versus completion, concurrent operations, cancellation, five-feature drift, reload retention, shared holdout gates, registry delivery before alias changes and MinIO metadata/CAS. Browser suites cover both themes, 1448/390/320 px layouts, keyboard controls and refresh behavior. Evidence is stored under [validation](validation/).

Verified results are recorded in [remediation-live.json](validation/remediation-live.json):

- Full pytest suite: **105 passed**, with two existing dependency deprecation warnings. Dataset smoke tests: **8 passed** with warnings treated as errors. Ruff: **All checks passed!**
- Browser checks: **194** control/layout assertions, **63** Overview assertions and **35** production read-only assertions. Production browser errors and operational writes: **zero**.
- Real Job `drift-retrain-a84a6e70e3b7`: terminal `Complete=True`, 03:09:17–03:10:24 UTC, successful container termination result. Champion **v41 → v43**, shared 901-row holdout MAE **10.6855 → 3.1507 RPS**, exact v43 loaded and hot reload confirmed. This comparison uses the recovered serving baseline v41.
- Real lifecycle start: daemon acknowledged `DRIFT_ANOMALY`, Job `drift-retrain-384bc3d7eea0` was created. Stop removed that owned Job, confirmed `STOPPED`, restored `STEADY_NORMAL` heartbeat and retained serving v43.
- Live cluster: control plane and both workers Ready. Controller observations, five PSI features, actual dataset row count and matching CAS object were available.
- All deployed immutable code ConfigMaps were compared byte for byte with the current source. Source equality evidence is included in the live report.

The [UI audit](anti-slop/audit-003-2026-10-13.md) records the post-implementation review. Historical unsuccessful jobs were used to find and repair storage/delivery failures; they are not success evidence.

Rollback snapshots were saved privately before inference, CronJob, dashboard and MLflow changes. Kubernetes deployment revisions retain previous image/ConfigMap pairs. Roll back paired source/image releases together; retain the PVC, Secret and new MinIO artifacts. An old registry alias with an unavailable artifact is not a valid model rollback target. Use a version whose artifact has loaded successfully.

The lifecycle and recent-decision buffer remain process-local; keep one inference replica. PVC local-path storage still needs an external backup for node loss. Runtime dependency installation requires package-index access. FinOps/carbon are estimates, and the benchmark reference is not a new measurement. No Git push or new 65 VU benchmark was performed.
