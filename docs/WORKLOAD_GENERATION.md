# Controlled Workload Generation

## 1. Purpose

This document defines how controlled workload is generated for the **Predictive Autoscaling MLOps** project.

The project uses an existing Jastip/Preloved application as the system under test. The Laravel backend runs inside Kubernetes and receives traffic from either the real clients or an external load generator.

The important methodological distinction is:

> **The project generates controlled workload, not fabricated Machine Learning data.**

The workload generator sends real HTTP requests to the Laravel backend. The backend and Kubernetes environment then produce real operational behavior such as request rate, CPU utilization, memory utilization, latency, error rate, and replica changes. Prometheus records those metrics and the MLOps pipeline later converts them into the Machine Learning dataset.

```text
k6
 ↓
Real HTTP Requests
 ↓
Laravel Backend
 ↓
Kubernetes Pods
 ↓
Real Operational Metrics
 ↓
Prometheus
 ↓
Prometheus API
 ↓
Time-Series Dataset
```

The dataset is therefore observed from the running system rather than manually synthesized as CSV values.

---

## 2. Why Controlled Workload Is Used

Natural traffic from the React and Android clients may still be used, but it is not sufficient for a reproducible experiment.

Controlled workload is required so the project can:

- repeat the same workload pattern;
- compare reactive and predictive autoscaling fairly;
- expose the backend to measurable resource pressure;
- generate dynamic time-series data continuously;
- create several workload regimes;
- deliberately introduce distribution changes for data-drift experiments;
- version the workload definition in Git.

Controlled workload scenarios are **experimental inputs**, not claims about real user behavior.

---

## 3. Selected Tool: Grafana k6

The initial load-testing tool is **Grafana k6**.

### Why k6

k6 is selected because it provides:

- workload-as-code using JavaScript;
- version-controlled scenario definitions;
- arrival-rate based traffic generation;
- ramping and staged workloads;
- request tagging;
- thresholds and runtime metrics;
- simple environment-variable parameterization;
- good compatibility with CI/CD workflows;
- lightweight execution outside the Kubernetes cluster.

Apache JMeter and Locust remain valid alternatives, but k6 is the default unless later project constraints justify changing the tool.

---

## 4. Load Generator Placement

The load generator should run **outside the Kubernetes worker nodes** whenever possible.

```text
External VM / Load Generator
          ↓
Application Endpoint
          ↓
Ingress / Service
          ↓
Laravel Pods
```

This prevents k6 from consuming CPU and memory on the same nodes whose resource behavior is being measured.

A separate AWS EC2 instance can be used as an external load-generator host during controlled experiments.

---

## 5. Recommended Repository Structure

The current repository already separates infrastructure, pipelines, source code, notebooks, and configuration. Workload definitions should therefore use a dedicated top-level directory.

```text
predictive-autoscaling-mlops/
├── workloads/
│   └── k6/
│       ├── README.md
│       ├── common/
│       │   ├── config.js
│       │   ├── auth.js
│       │   └── endpoints.js
│       ├── scenarios/
│       │   ├── calibration.js
│       │   ├── steady.js
│       │   ├── gradual.js
│       │   ├── spike.js
│       │   ├── periodic.js
│       │   ├── bursty.js
│       │   ├── drift-intensity.js
│       │   └── drift-composition.js
│       └── data/
│           └── .gitkeep
├── configs/
├── pipelines/
├── src/
└── docs/
```

The actual JavaScript files should only be implemented after the Laravel API endpoints, authentication mechanism, and required test data are inspected.

---

## 6. Configuration

Scenario files should not hard-code deployment-specific addresses or credentials.

Candidate runtime variables:

```text
BASE_URL
AUTH_TOKEN
TEST_USER_EMAIL
TEST_USER_PASSWORD
RUN_ID
SCENARIO_NAME
```

Example:

```bash
BASE_URL=https://mlops.example.id \
RUN_ID=calibration-001 \
k6 run workloads/k6/scenarios/calibration.js
```

Credentials and tokens must never be committed to Git.

---

## 7. Endpoint Selection

Before finalizing the workload, inspect the actual Laravel backend and identify representative endpoints.

Candidate endpoint categories:

- browse listings;
- view listing detail;
- search/filter;
- browse preloved items;
- offer-related operations;
- selected write operations when safe for the experimental database.

The final endpoint list must come from the real application implementation.

Do not invent artificial endpoints only for load testing.

### 7.1 Endpoint Mix

A realistic experiment should eventually use more than one endpoint.

Illustrative example only:

```text
50% listing browse
20% listing detail
15% search/filter
10% preloved browse
 5% offer-related request
```

These values are not final.

Endpoint composition matters because two workloads with the same request rate may create different CPU, memory, database, and latency behavior.

---

## 8. Phase 0: Capacity Calibration

Final request-rate values must not be chosen arbitrarily.

The first script should be:

```text
workloads/k6/scenarios/calibration.js
```

### Objective

Find a practical workload range for the actual Laravel backend and current Kubernetes infrastructure.

### Method

Increase workload gradually while observing:

- request rate;
- CPU utilization;
- memory utilization;
- response latency;
- p95/p99 latency when available;
- error rate;
- throughput;
- replica count;
- pod restart or OOM events.

Conceptually:

```text
Very Low Load
      ↓
Low
      ↓
Medium
      ↓
High
      ↓
Near Saturation
```

Example rates such as `1 → 5 → 10 → 20 req/s` are only placeholders.

### Calibration Output

The goal is to identify approximate workload regions:

```text
LOW
application is comfortably underutilized

MEDIUM
resource use is measurable but healthy

HIGH
resource use is high but the application remains reliable

SATURATION
latency/errors/resource pressure begin to increase strongly
```

Later scenarios should be derived from these observations.

---

## 9. Core Workload Scenarios

The project uses five core workload shapes.

### 9.1 Steady

Stable workload for a defined duration.

Purpose:

- establish baseline behavior;
- verify monitoring;
- observe stable resource usage;
- evaluate forecast stability.

```text
req/s
  │
  │ ─────────────────────────
  └──────────────────────────→ time
```

### 9.2 Gradual Increase

Traffic rises progressively.

Purpose:

- study relationship between workload and resource usage;
- observe scaling thresholds;
- compare reactive and predictive response to sustained growth.

```text
req/s
  │             ______
  │          __/
  │       __/
  │    __/
  │___/
  └──────────────────────────→ time
```

### 9.3 Spike

Traffic suddenly moves from a baseline to a much higher load and later returns.

Purpose:

- evaluate reactive scaling delay;
- measure latency/error impact;
- test whether predictive scaling can prepare capacity earlier.

```text
req/s
  │          ┌───────┐
  │──────────┘       └──────────
  └────────────────────────────→ time
```

### 9.4 Periodic

Workload repeatedly rises and falls.

Purpose:

- create learnable temporal structure;
- evaluate time-series forecasting;
- test predictive scaling on recurring patterns.

```text
req/s
  │    /\      /\      /\
  │___/  \____/  \____/  \___
  └────────────────────────────→ time
```

### 9.5 Bursty

Several irregular short bursts occur with different magnitudes and durations.

Purpose:

- test forecasting robustness;
- create higher-variance observations;
- measure scaling behavior under less predictable traffic.

```text
req/s
  │       /\       /\
  │  /\  /  \  /\ /  \
  │_/  \/    \/  V    \____
  └──────────────────────────→ time
```

---

## 10. Dynamic Data

The dataset is dynamic because new observations continue to appear while the application receives workload.

```text
Run 1
 ↓
Prometheus Observations
 ↓
Dataset v1

Run 2
 ↓
New Observations
 ↓
Dataset v2

Run N
 ↓
New Observations
 ↓
Dataset vN
```

k6 does not need to create the ML dataset directly.

The ingestion pipeline will query Prometheus for a defined time range, align timestamps, validate metrics, and store/version the resulting time-series dataset.

---

## 11. Data Drift Methodology

Data drift must not be created by manually editing collected metric values.

Wrong:

```text
CPU = 40%
manually change to 80%
```

Preferred:

```text
Change Workload Regime
        ↓
Application Receives Different Traffic
        ↓
Real Operational Metrics Change
        ↓
New Data Distribution
        ↓
Drift Evaluation
```

### 11.1 Intensity Drift

The traffic level changes.

Example concept:

```text
Training:
mostly low-to-medium request rate

Later production:
mostly medium-to-high request rate
```

Potentially affected distributions:

- request rate;
- CPU;
- latency;
- memory;
- replicas.

### 11.2 Composition Drift

The total request rate can remain similar while endpoint composition changes.

Example:

```text
Training:
mostly lightweight read requests

Later:
more search/filter/write-heavy traffic
```

Even at the same RPS, the backend may show a different CPU or latency distribution.

### 11.3 Drift Must Be Verified

A changed workload does not automatically prove drift.

The correct process is:

```text
Change Workload
      ↓
Collect New Data
      ↓
Compare Reference vs Recent Window
      ↓
Measure Distribution Difference
      ↓
Stable / Drifted
```

The final drift-detection method remains open until real data is available.

---

## 12. Suggested Experimental Sequence

```text
1. Calibration
   Determine practical load range.

2. Initial Data Collection
   Run representative scenarios.

3. Training Window
   Build dataset v1.

4. Similar Production Window
   Collect data with similar characteristics.

5. Changed Workload Window
   Introduce intensity or composition change.

6. Drift / Performance Evaluation
   Compare distributions and model error.

7. Retraining
   Train candidate model on updated data.

8. Promotion / Rejection
   Compare candidate against production model.
```

A single transient spike should not automatically be treated as persistent drift.

---

## 13. Run Metadata

Every experiment should be traceable.

Recommended metadata:

```text
run_id
scenario
scenario_version
start_timestamp
end_timestamp
application_version
container image tag
infrastructure configuration
autoscaling mode
replica configuration
pod resource requests/limits
endpoint mix
arrival-rate configuration
notes
```

Example IDs:

```text
calibration-001
steady-001
spike-003
reactive-periodic-002
predictive-periodic-002
```

---

## 14. Reactive vs Predictive Comparison

The same versioned workload should be used for both approaches.

```text
             Versioned k6 Scenario
                     │
          ┌──────────┴──────────┐
          ↓                     ↓
       Reactive              Predictive
          ↓                     ↓
      Prometheus             Prometheus
          └──────────┬──────────┘
                     ↓
                 Evaluation
```

Keep constant where possible:

- application version;
- infrastructure;
- pod resource limits;
- workload scenario;
- endpoint mix;
- experiment duration;
- test database condition.

---

## 15. Metrics Expected

### Workload

- request rate;
- request count;
- endpoint distribution.

### Application

- response latency;
- p95/p99 latency;
- HTTP error rate;
- throughput.

### Infrastructure

- CPU utilization;
- memory utilization;
- replica count;
- pod restart count;
- node/pod health.

### Scaling

- scale-up/down events;
- scaling response time;
- decision latency.

Not every collected metric must become an ML feature.

---

## 16. Decisions That Must Remain Open

Before calibration and EDA, do not lock:

- exact RPS values;
- exact scenario durations;
- final endpoint mix;
- sampling interval;
- prediction horizon;
- final feature set;
- drift threshold.

These must be justified from actual collected data.

---

## 17. Implementation Order

```text
Inspect Laravel API
      ↓
Prepare test users/data
      ↓
Install k6 externally
      ↓
Implement calibration.js
      ↓
Observe Prometheus
      ↓
Determine workload ranges
      ↓
Implement core scenarios
      ↓
Version scenarios in Git
      ↓
Collect dataset
      ↓
EDA
      ↓
Implement drift experiments
```

---

## 18. Summary

The workload-generation approach follows four principles:

1. **Generate workload, not fabricated ML data.**
2. **Observe real backend and Kubernetes behavior using Prometheus.**
3. **Calibrate workload before defining final scenario intensity.**
4. **Create drift by changing workload regimes, then verify that the observed data distribution actually changes.**
