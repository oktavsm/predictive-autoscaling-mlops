# Synthetic fixture contract

Version 1.1.0. `synthetic-telemetry.json` is an offline UI fixture, not a production response. Every observation/event and each telemetry-bearing group is labeled synthetic. No value came from a live cluster.

- 241 observations at 15s cadence: 2026-10-12 10:10:00Z–11:10:00Z (17:10–18:10 WIB).
- Latest actual: 186 req/s; latest forecast target at 11:11:00Z: 240 req/s.
- Synthetic policy: 65 req/s/pod; bounds 1–8; ceil(240/65) = 4.
- Observed pods: 3; pending recommendation: 4. Applied synthetic events: 2→4 at 17:22, 4→6 at 17:42, 6→3 at 17:54.
- Current p95: 42ms. Model label demo-v2.4/XGBoost is fictional. PSI 0.08 is a synthetic reference result.
- HTTP 15m window: 5,000 total, 20 failed → 0.4% error, 99.6% success.
- CPU saturation: 54% of allocatable CPU; memory: 61% of allocatable memory. These do not equal request/capacity utilization.

## Time alignment

Rows store `prediction_for_plus_60s_rps` by issue timestamp. For each actual at t, compare with the prediction issued at t−60s (four cadence steps earlier). First four observations have no aligned error. The last 61 target observations cover an inclusive 15-minute range. Their absolute-error mean rounds to 0.12 req/s. Future unobserved targets never enter MAE.

The fixture intentionally provides unusually close historical predictions for a legible design example. It does not demonstrate model performance. Recent forecast errors are synthetic, seeded values, not measured validation outcomes.

The Overview draws actual history and the latest point forecast in a separately labeled +60s inset. The connector is a visual guide; it does not assert intermediate trajectory points. No forecast uncertainty is supplied.

## Reproducibility

The fixture is committed as the complete canonical JSON; building the standalone embeds it without recalculation or network I/O. Its SHA-256 is in MANIFEST.json. Any edited fixture must rerun consistency validation and update visible headline values. An ingestion event reports the same 241-row synthetic window.

The illustrative success/CPU sparkline arrays are separately marked synthetic. Success sparkline shapes are not reconstructed from aggregate HTTP counts. The latency sparkline uses the last 40 fixture latency rows; all last sparkline endpoints equal their displayed headline.

CSV export includes all 241 rows with `synthetic=true`, issue UTC, target UTC, actual and forecast req/s, observed and recommended replica counts, and p95 ms. No spreadsheet formulas or externally sourced strings are exported.
