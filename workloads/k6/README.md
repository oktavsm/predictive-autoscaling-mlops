# k6 Workload Scenarios

Controlled load generator for the Predictive Autoscaling MLOps project.
All scripts use the **arrival-rate executor** so req/s is the controlled variable
(not VU count), which maps directly to the Prometheus `rate()` metrics.

> **Calibration finding (2026-09-08):**
> - ~3  req/s → 1 replica (LOW)
> - ~8  req/s → HPA triggers → 2 replicas (MEDIUM)
> - ~14 req/s → 3 replicas (HIGH)
> - ~15+ req/s → 4 replicas (max, near SATURATION)

---

## Directory layout

```
workloads/k6/
├── common/
│   ├── config.js       # BASE_URL, RUN_ID, LOAD constants
│   └── endpoints.js    # endpoint definitions + weighted pickers
├── scenarios/
│   ├── steady.js           # constant load baseline
│   ├── gradual.js          # ramp 3→18 req/s over 20 min
│   ├── spike.js            # baseline → sudden spike → recovery
│   ├── periodic.js         # 3 repeating waves (key ML training scenario)
│   ├── bursty.js           # irregular bursts of varying size
│   ├── drift-intensity.js  # higher RPS window for drift experiments
│   └── drift-composition.js# same RPS, write-heavy endpoints
└── data/               # placeholder for k6 CSV output if needed
```

---

## Quick start

```bash
# Run from repo root.

# Steady at MEDIUM load, 15 minutes
BASE_URL=https://api.titipin.me \
RUN_ID=steady-001 \
~/.local/bin/k6 run workloads/k6/scenarios/steady.js

# Gradual ramp (primary dataset collection)
BASE_URL=https://api.titipin.me \
RUN_ID=gradual-001 \
~/.local/bin/k6 run workloads/k6/scenarios/gradual.js

# Spike test (key comparison scenario)
BASE_URL=https://api.titipin.me \
RUN_ID=spike-001 \
~/.local/bin/k6 run workloads/k6/scenarios/spike.js

# Periodic waves (model training scenario)
BASE_URL=https://api.titipin.me \
RUN_ID=periodic-001 \
~/.local/bin/k6 run workloads/k6/scenarios/periodic.js

# Bursty (variance / robustness dataset)
BASE_URL=https://api.titipin.me \
RUN_ID=bursty-001 \
~/.local/bin/k6 run workloads/k6/scenarios/bursty.js
```

---

## Environment variables

| Variable      | Default                   | Description                      |
|---------------|---------------------------|----------------------------------|
| `BASE_URL`    | `https://api.titipin.me`  | Target application URL           |
| `RUN_ID`      | `run-<timestamp>`         | Trace label for Prometheus/MLflow|
| `RATE`        | scenario-specific         | Override req/s (steady/drift)    |
| `DURATION`    | scenario-specific         | Override hold duration           |
| `SPIKE_RATE`  | `18`                      | Peak rate for spike scenario     |
| `PEAK_RATE`   | `14`                      | Peak rate for periodic scenario  |
| `TROUGH_RATE` | `3`                       | Trough rate for periodic scenario|

---

## Recommended data collection sequence

1. `steady.js` at LOW (3) — ~15 min — clean baseline
2. `gradual.js` — ~20 min — full ramp, captures scaling thresholds
3. `periodic.js` — ~32 min — 3 waves, primary ML training data
4. `bursty.js` — ~20 min — variance dataset
5. `spike.js` — ~15 min — comparison experiment data
6. `drift-intensity.js` — ~16 min — after model is trained
7. `drift-composition.js` — ~15 min — composition drift test

Collect at least **runs 1–5** before starting EDA.
