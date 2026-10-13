# Operational workspace cleanup release

13 October 2026 WIB. Live: https://mlops.titipin.me. This follow-up replaces the initial Overview-only release with cleaned operational views and verified control wiring. The user authorized Docker/deployment and subsequently requested commits and control documentation. Git push was not requested.

- Image: `docker.io/oktaavsm/predictive-autoscaler-dashboard:cleanup-20261012-2346@sha256:85edafed952c6e18833f3fc983fb1caf6dbbc974220463891faec4793f3bac2d`
- ConfigMap: `mlops-dashboard-code-cleanup-20261012-2346`
- Deployment revision: 23
- Verified pod: `mlops-dashboard-545b7d4c4d-jfvlx` on worker-2, Ready 1/1 with zero restarts at inspection.
- Source identity: six deployed file hashes match the checkout; see `release.json`. Source and this evidence are included in the accompanying cleanup commit, based on `f292ae0`.

The image contains the existing pinned dependencies, modules, theme, local fonts and kit assets. No production dependency changed. Image and versioned ConfigMap references changed in one strategic patch; the repository manifest passed Kubernetes server dry-run. The old ConfigMap and image remain available for rollback. Streamlit usage telemetry remains disabled.

## Verification and limits

- 53 dashboard Python tests passed, including every supported action, presets, local policy/calculator inputs, API failure cases and daemon/route contract checks.
- 189 operational mock-browser assertions and 63 Overview mock-browser assertions passed. Operational coverage includes dark/light themes at 1448/390/320px, kit glyphs, caption contrast opacity, profile requests, request errors, keyboard activation and polling enabled/disabled. The Overview suite also checks CSV content and inspectors.
- All 24 runtime SVG glyph files match the supplied kit byte-for-byte. Native HTML sanitization strips inline SVG, so the dashboard uses local SVG data images with semantic colors and decorative accessibility attributes beside text labels.
- An isolated image container with a 512 MiB limit and no network rendered all nine workspaces from eight captured API read responses. An automatic-POST rejection spy was never called.
- 35 read-only public-browser assertions passed after rollout: Overview and all eight operational views render without exceptions; glyph images load; no decorative emoji remains in operational copy; theme/mobile checks pass; drift is visibly disabled; no browser JavaScript errors or mutating browser HTTP requests were observed. Browser observation alone cannot inspect server-side HTTP calls; the image spy and button tests verify that boundary separately.
- Six runtime hashes matched app, adapter, Overview, CSS, theme and pipeline glyph. Public service destinations/OpenAPI returned HTTP 200 when checked. The installed daemon's six state definitions matched repository definitions.
- Repository-wide Ruff lint/format and `git diff --check` passed. Evidence: `../../validation/verification.json`, `controls.json`, `overview.json`, and `public-reads.json`.

Post-rollout health sampling recorded 89 HTTP 200 responses and one failed request out of 90. The failed request recovered on the next sample; its cause was not established. These recorded timestamps do **not** cover the pod transition, so they cannot establish availability during rollout. The first remote rollout watch remained open despite the deployment already reaching revision 23 with one updated/ready/available replica and zero terminating replicas. A fresh `kubectl rollout status --timeout=30s` returned success; only the original local watch was terminated.

No production prediction, traffic switch, retraining, model reload or scaling mutation was submitted. Action tests used local mocks. Source/daemon inspection establishes compatibility, not real execution of a requested traffic profile or verified retraining. Manual retraining, drift injection and lifecycle start/stop remain unavailable with visible explanations. Full inventory and backend follow-ups: [FUNCTIONALITY.md](../../FUNCTIONALITY.md).

Point-in-time production UI evidence:

- [Injector, light desktop](production-injector-light-desktop.png)
- [Injector, light mobile](production-injector-light-mobile.png)
- [Browser results](browser-smoke.json)

Synthetic QA previews remain separately labeled in `../../validation/`; they are not production measurements.

## Rollback

`rollback.json` restores the previous revision's image digest and matching `mlops-dashboard-code-revamp-20261012-1642` ConfigMap. The file is durable in Git; no rollback was needed or executed.

```sh
scp docs/dashboard-revamp/deployment/cleanup-2026-10-13/rollback.json cp:/tmp/dashboard-cleanup-rollback.json
ssh cp 'kubectl -n mlops patch deployment mlops-dashboard --type=strategic --patch-file=/tmp/dashboard-cleanup-rollback.json && kubectl -n mlops rollout status deployment/mlops-dashboard --timeout=180s'
```

Temporary snapshots, smoke/build/push logs and the initial rollback template are in `/tmp/mlops-dashboard-cleanup-20261013` locally; deployment snapshots and patches also exist in the same directory on `cp`. Temporary files can be cleared. Use the committed rollback JSON and retain the referenced ConfigMap/image for a later rollback.
