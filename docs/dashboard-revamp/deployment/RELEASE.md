# Dashboard revamp release

13 October 2026 WIB. The user explicitly authorized Docker activation and deployment. URL: https://mlops.titipin.me.

- Image: `docker.io/oktaavsm/predictive-autoscaler-dashboard:revamp-20261012-1642`
- Pinned digest: `sha256:60e9adc2d32eeefc058e35f7cecc0c6344907d1e405cc89f4a480804a179681e`
- ConfigMap: `mlops-dashboard-code-revamp-20261012-1642`, generated from this working tree's `src/dashboard/app.py`.
- Final deployment revision: 22. Pod `mlops-dashboard-5486fc5fcb-cqf4c` on worker-1 was Ready 1/1 with zero restarts.
- Source is an uncommitted working tree. No Git commit or Git push was performed. Docker registry push completed successfully.

## Verification

The image contains Streamlit 1.65.0, Altair 6.3.0 and pandas 2.3.3. An isolated container with a 512 MiB memory limit rendered Overview and all eight operational workspaces against controlled responses. A POST rejection spy remained untouched. A separate container passed the Docker healthcheck. These temporary containers were removed after verification; the Docker daemon remains active.

The production API returned 200 for all five Overview read resources. The new adapter accepted 60 production decisions and rejected zero; model v40 was ready, and runtime policy reported 10 req/s per pod with replica bounds 1–6. This checks API compatibility and presentation, not forecast accuracy or autoscaler effectiveness.

The image and ConfigMap references changed together in the first rollout. A second rollout set `STREAMLIT_BROWSER_GATHER_USAGE_STATS=false`, disabling the framework's default external usage telemetry. Across both updates, 99 of 100 sampled public health reads returned HTTP 200. One sample returned HTTP 502 at `2026-10-12T17:15:55Z` during the second transition; the next sample returned 200. The cause was not established, and brief proxy errors remain a rollout risk. These samples do not establish uninterrupted availability or the exact duration of the interruption.

Nine public-browser checks passed at `2026-10-12T17:16:46Z` / `13 October 00:16:46 WIB`: application title, nine workspace options, four metrics, no Streamlit exception, chart count matching source state, Light theme after Refresh now, 390px layout without horizontal page overflow, no browser page errors, and no POST/PUT/PATCH/DELETE requests. Browser HTTP observation does not capture server-side API calls; the adapter and container spy separately check that boundary. No workload, retraining, model-reload or scaling mutation was exercised.

Five deployed file hashes matched the working tree: app, adapter, Overview, CSS and theme configuration. The repository deployment manifest also passed `kubectl apply --dry-run=server`. See [release.json](release.json) and [browser-smoke.json](browser-smoke.json).

Production screenshots are point-in-time UI evidence, separate from the synthetic previews in `../previews/`:

- [Dark desktop](production-dark-desktop.png)
- [Light desktop](production-light-desktop.png)
- [Light mobile](production-light-mobile.png)

## Rollback

The previous `mlops-dashboard-code` ConfigMap remains in the cluster. The previous image digest is `sha256:c1d69b29df48587ab2479e71f359ce09106e15bdec343944655fb3032a734282` in the same repository. The release did not overwrite `latest`.

Deployment and ConfigMap snapshots, logs, and a rollback patch exist in `/tmp/mlops-dashboard-release-20261012` locally and on `cp` (the server copy contains the snapshots and rollback patch). The rollback patch restores the previous pod template and pins its previous image digest:

```sh
ssh cp 'kubectl -n mlops patch deployment mlops-dashboard --type=merge --patch-file=/tmp/mlops-dashboard-release-20261012/rollback-patch.json && kubectl -n mlops rollout status deployment/mlops-dashboard --timeout=180s'
```

This rollback command was prepared but not executed. `/tmp` backups may be cleared; retain a durable copy before later releases. Existing hardcoded fields in preserved operational workspaces and the theme-plus-refresh behavior remain documented in `anti-slop/audit-001-2026-10-12.md`.
