# Architecture and Project Decisions

> Decision log for the **Predictive Autoscaling MLOps** project.
>
> This document records decisions that have already been made, decisions that are provisional, and decisions that intentionally remain open. It should be updated whenever implementation evidence changes the architecture.

---

## 1. Decision Status Convention

Each decision uses one of the following states:

| Status | Meaning |
|---|---|
| **Accepted** | Current project decision and should be treated as the default. |
| **Provisional** | Current implementation choice, but may be revised after measurement or integration work. |
| **Open** | Intentionally not finalized yet. |
| **Superseded** | Replaced by a newer decision. |
| **Conflict / Review Required** | Current documents or implementations are inconsistent and must be reconciled before final experiments. |

The project should clearly distinguish:

- architectural decisions;
- implementation assumptions;
- experimental parameters;
- measured results.

Experimental values must not be promoted into permanent architecture decisions without evidence.

---

# 2. Project-Level Decisions

## ADR-001 — Use Existing Titip.In Application as Experimental Workload

**Status:** Accepted

The project uses the existing Jastip and Preloved application as the workload source instead of creating a dedicated benchmark application.

Application components:

```text
Web Client      : React
Android Client  : Kotlin + Jetpack Compose
Backend         : PHP Laravel
```

The existing clients and backend remain in their own repositories.

The `predictive-autoscaling-mlops` repository is responsible for:

- Kubernetes experiment configuration;
- monitoring;
- data ingestion;
- dataset processing/versioning;
- model training;
- model serving;
- scaling policy;
- retraining;
- MLOps CI/CD;
- experiment definitions;
- project documentation.

### Rationale

Using the existing application keeps the project focused on MLOps and predictive autoscaling instead of rebuilding an application only for experimentation.

---

## ADR-002 — Laravel Backend Is the Primary Scaling Target

**Status:** Accepted

The Laravel backend is the primary service whose replica count will be adjusted.

The project focuses on:

```text
Predictive Pod / Replica Autoscaling
```

and explicitly does **not** focus on:

```text
VM autoscaling
cluster/node autoscaling
database autoscaling
```

Frontend applications do not need to run inside the experimental Kubernetes cluster.

### Consequence

The final predictive-vs-reactive experiment must operate on Laravel backend replicas running as Kubernetes workloads.

---

## ADR-003 — Predictive Autoscaling Must Be Compared With Reactive Autoscaling

**Status:** Accepted

The project does not assume predictive autoscaling is better.

Final experiments compare:

```text
Same Application
Same Infrastructure
Same Workload Scenario
Same Resource Configuration
          │
    ┌─────┴─────┐
    ↓           ↓
Reactive     Predictive
Autoscaling  Autoscaling
    │           │
    └─────┬─────┘
          ↓
      Evaluation
```

Evaluation may include:

- response latency;
- p95/p99 latency;
- error rate;
- CPU utilization;
- memory utilization;
- replica count;
- scaling responsiveness;
- overload/SLO violations;
- resource waste.

---

# 3. Infrastructure Decisions

## ADR-004 — Use a Three-Node K3s Cluster

**Status:** Accepted

The current physical/VM topology is:

| Node | Role | Address / Access | CPU | RAM | Storage |
|---|---|---|---:|---:|---:|
| VM-01 | Control Plane | `proxy.bccdev.id:11049`, user `dev` | 2 cores | 4 GB | 20 GB |
| VM-02 | Worker 1 | `15.232.116.101`, user `ubuntu` | 2 cores | 2 GB | 20 GB |
| VM-03 | Worker 2 | `15.232.71.54`, user `ubuntu` | 2 cores | 2 GB | 20 GB |

SSH authentication uses public-key authentication.

### Current Cluster Roles

```text
VM-01
├── K3s server / control plane
├── Prometheus
├── Grafana
└── Caddy

VM-02
└── K3s agent / worker

VM-03
└── K3s agent / worker
```

### Rationale

K3s is chosen because the infrastructure is relatively small and resource-constrained while the project still requires Kubernetes scheduling, metrics, and replica autoscaling behavior.

---

## ADR-005 — Keep Application Workloads Off the Control Plane

**Status:** Accepted

The control-plane node is tainted to prevent normal backend workloads from being scheduled there.

Worker nodes are explicitly labeled.

Current intended configuration:

```text
Control Plane
→ orchestration + monitoring

Worker 1 / Worker 2
→ Laravel backend replicas
```

### Rationale

This isolates the experimental workload from control-plane resource usage and makes worker-level measurements more meaningful.

---

## ADR-006 — Disable Bundled Traefik and Use Caddy for External Reverse Proxy

**Status:** Provisional

K3s is installed with:

```text
--disable traefik
```

Caddy runs on VM-01 and is currently responsible for public HTTPS reverse proxying.

Current domains:

```text
api.titipin.me
grafana.titipin.me
```

Cloudflare manages DNS for `titipin.me`.

### Current Intended Domain Layout

```text
titipin.me
└── frontend

api.titipin.me
└── Laravel API

grafana.titipin.me
└── Grafana
```

### Why Provisional

The final Caddy upstream for `api.titipin.me` depends on how the Kubernetes Laravel Service is exposed.

The current setup guide points Caddy to:

```text
localhost:8083
```

which corresponds to the temporary Docker Compose deployment, not the final Kubernetes scaling target.

This must be updated when the Laravel backend is deployed as Kubernetes pods.

---

## ADR-007 — Use Existing GHCR Application Images

**Status:** Accepted

Existing backend images from:

```text
ghcr.io/titip-in/
```

should be reused where possible instead of rebuilding equivalent application images inside this repository.

### Rationale

The existing application's build/release lifecycle remains independent from the MLOps repository.

The MLOps project should consume a known application image version and record its tag/digest for experiment reproducibility.

---

# 4. Monitoring and Data Decisions

## ADR-008 — Prometheus Is the Primary Operational Metrics Source

**Status:** Accepted

Prometheus is the central metrics store.

Primary data path:

```text
Application / Kubernetes
          ↓
      Prometheus
          ↓
   Prometheus HTTP API
          ↓
      Data Ingestion
          ↓
Validated Time-Series Dataset
```

Prometheus API data, rather than manually fabricated values, becomes the source of the Machine Learning dataset.

---

## ADR-009 — Initial Prometheus Scrape Interval Is 15 Seconds

**Status:** Provisional

The current Prometheus configuration uses:

```yaml
scrape_interval: 15s
evaluation_interval: 15s
```

### Important Distinction

The Prometheus **scrape interval** is not automatically the final Machine Learning **dataset sampling interval**.

The ML sampling interval remains open and may later be:

- equal to the scrape interval;
- aggregated to 30 seconds;
- aggregated to 60 seconds;
- another justified interval.

The final choice must come from EDA, metric noise, scaling timing, and storage considerations.

---

## ADR-010 — Initial Monitoring Stack Uses Prometheus + Grafana + Exporters

**Status:** Provisional

Current setup includes:

- Prometheus on VM-01;
- Grafana on VM-01;
- Node Exporter on all three VMs;
- cAdvisor planned on all three VMs;
- kube-state-metrics in Kubernetes.

Candidate collected information includes:

```text
Node
├── CPU
├── memory
├── disk
└── network

Container / Pod
├── CPU
├── memory
└── runtime behavior

Kubernetes
├── deployment replicas
├── pod state
└── cluster state

Application
├── request rate
├── response latency
├── error rate
└── throughput
```

### Review Note

The cAdvisor configuration in the current setup guide mounts Docker-specific paths such as:

```text
/var/lib/docker
```

while K3s normally uses containerd.

The final container-level metrics path must therefore be verified on the actual K3s workers before it is considered stable.

---

## ADR-011 — Prometheus Retention Is Initially Configured to 30 Days

**Status:** Provisional

The current systemd configuration uses:

```text
--storage.tsdb.retention.time=30d
```

### Reason for Provisional Status

VM-01 currently has only 20 GB storage and also hosts Kubernetes control-plane components, Grafana, Caddy, logs, and Prometheus.

The actual Prometheus TSDB growth must be measured.

Retention may need to be reduced or bounded by storage size before long-running experiments.

Do not assume 30 days is safe until disk usage is observed.

---

# 5. Workload Generation Decisions

## ADR-012 — Controlled Workload Is Generated Against the Real API

**Status:** Accepted

Controlled experiments send real HTTP requests to the Laravel API.

The project does **not** directly fabricate the ML dataset.

```text
Controlled Workload
      ↓
Real HTTP Requests
      ↓
Laravel
      ↓
Real System Behavior
      ↓
Prometheus Metrics
      ↓
ML Dataset
```

### Terminology

Correct framing:

> The workload is controlled/synthetic, while the operational dataset is observed from the real running system.

Avoid describing the entire dataset as manually synthesized.

---

## ADR-013 — Use Grafana k6 as the Initial Workload Generator

**Status:** Accepted

The default controlled-load tool is:

```text
Grafana k6
```

### Rationale

k6 supports:

- workload-as-code;
- Git versioning;
- arrival-rate scenarios;
- staged traffic;
- request tagging;
- environment-variable configuration;
- CI/CD integration.

JMeter and Locust remain possible alternatives if a later requirement justifies them.

---

## ADR-014 — Use Multiple Controlled Workload Shapes

**Status:** Accepted

The core scenarios are:

```text
calibration
steady
gradual increase
spike
periodic
bursty
```

Final RPS values and durations are **not** decided yet.

### Calibration First

Before final scenario parameters are chosen, the backend must be profiled to identify:

```text
low load
medium load
high load
near saturation
```

Workload values must be derived from the real infrastructure rather than arbitrary numbers.

---

## ADR-015 — Data Drift Is Produced by Changing Workload Regimes

**Status:** Accepted

Data drift will not be created by manually modifying collected metrics.

Instead:

```text
Change Workload Regime
        ↓
Real Backend Behavior Changes
        ↓
New Prometheus Observations
        ↓
Distribution Comparison
        ↓
Drift / No Drift
```

Two planned drift categories are:

### Intensity Drift

Example:

```text
lower workload distribution
→ higher workload distribution
```

### Workload-Composition Drift

Example:

```text
mostly lightweight reads
→ larger proportion of search / heavier operations
```

A changed workload does not automatically count as drift. The resulting observed distributions must be compared.

---

# 6. Machine Learning Decisions

## ADR-016 — Use Supervised Time-Series Forecasting / Regression

**Status:** Accepted

The initial ML task is:

```text
Time-Series Forecasting / Regression
```

not Reinforcement Learning.

### Rationale

The course project focuses on MLOps lifecycle engineering rather than designing a new control algorithm.

Forecasting provides a clean separation between:

```text
Prediction
and
Scaling Decision
```

---

## ADR-017 — Reinforcement Learning Is Out of Initial Scope

**Status:** Accepted

RL is not used for the first implementation.

It may be considered future work after the forecasting-based system works.

Reasons include:

- reward-function complexity;
- exploration risk;
- much larger experimental requirements;
- harder reproducibility;
- difficulty isolating model vs policy failure;
- scope drift away from MLOps.

---

## ADR-018 — Future Request Rate Is the Initial Target Hypothesis

**Status:** Provisional

The current preferred hypothesis is:

```text
future request rate
```

because request rate represents incoming workload more directly than CPU utilization.

However, the final target is still decided only after real data and EDA.

Other candidates remain:

- future CPU utilization;
- future workload/resource demand.

---

## ADR-019 — Baseline Models Must Be Evaluated Before Complex Models

**Status:** Accepted

Initial model progression:

```text
Persistence / Last Value
        ↓
Moving Average
        ↓
Linear Regression
        ↓
XGBoost Regressor
        ↓
Optional More Complex Model
```

### Rationale

A complex model is only justified if it provides measurable improvement over simple baselines.

---

## ADR-020 — XGBoost Is the Primary Nonlinear Model Candidate

**Status:** Provisional

The current main candidate is:

```text
XGBoost Regressor
```

using lag and rolling features.

Candidate features may include:

```text
request_rate_t
request_rate_t-1
request_rate_t-2
rolling_mean_request
rolling_std_request
cpu_t
memory_t
latency_t
replica_count_t
```

The final feature set must come from EDA.

---

## ADR-021 — Use Chronological Splitting for Time-Series Evaluation

**Status:** Accepted

Training data must not be randomly shuffled across time.

Preferred conceptual split:

```text
Past                              Future
│------------------------------------│
Training       Validation        Test
```

Walk-forward validation may later be used when useful.

### Rationale

Random splitting can leak future temporal information into the training set.

---

## ADR-022 — Model Metrics Are MAE, RMSE, and MAPE

**Status:** Accepted

Primary regression metrics:

- MAE;
- RMSE;
- MAPE.

MAPE must be interpreted carefully if the prediction target can be zero or near zero.

Model selection should also consider operational usefulness, not only a single prediction metric.

---

# 7. MLOps Lifecycle Decisions

## ADR-023 — Use DVC for Dataset Versioning

**Status:** Accepted

Datasets should be versioned and traceable.

Each relevant dataset version should be linked to:

- collection period;
- workload run/scenario;
- preprocessing version;
- source code version;
- training run.

The final DVC remote/storage backend remains open.

---

## ADR-024 — Use MLflow for Experiment Tracking and Model Registry

**Status:** Accepted

MLflow is planned to track:

- parameters;
- metrics;
- artifacts;
- dataset/model references;
- candidate model versions.

Candidate models must be evaluated before promotion.

---

## ADR-025 — Serve the Production Model Through FastAPI

**Status:** Accepted

The selected production model will be exposed through a lightweight inference API.

Concept:

```text
Recent Features
      ↓
FastAPI
      ↓
Production Model
      ↓
Forecast
```

The final request/response schema remains open until the target and feature contract are finalized.

---

## ADR-026 — Keep Forecasting and Scaling Policy Separate

**Status:** Accepted

The model predicts future workload/resource conditions.

A separate scaling policy translates the prediction to a replica recommendation.

```text
Model
 ↓
Prediction
 ↓
Scaling Policy
 ↓
Recommended Replicas
 ↓
Kubernetes
```

This enables independent debugging and evaluation.

---

## ADR-027 — Use Scheduled and Condition-Based Continuous Training Triggers

**Status:** Accepted

Continuous Training should support:

### Scheduled checks

Check periodically whether sufficient new validated data has accumulated.

### Condition-based checks

Consider retraining when:

- data distribution changes;
- prediction error increases;
- production model performance degrades.

Retraining does not automatically mean promotion.

---

## ADR-028 — Candidate Model Must Pass Evaluation Before Promotion

**Status:** Accepted

```text
Retraining
   ↓
Candidate
   ↓
Evaluation
   ├── Pass → Promote
   └── Fail → Keep Existing Production Model
```

The currently working production model must remain available when retraining produces a worse candidate.

---

# 8. Repository Organization Decisions

## ADR-029 — Reuse the Existing Source and Pipeline Directory Separation

**Status:** Accepted

Current repository structure already contains:

```text
src/
├── data/
├── features/
├── models/
├── inference/
└── scaling/

pipelines/
├── ingestion/
├── training/
└── retraining/
```

Intended responsibility:

```text
src/
→ reusable implementation

pipelines/
→ orchestration / executable pipeline entry points
```

Avoid duplicating the same logic in both locations.

---

## ADR-030 — Add a Dedicated Workload Directory

**Status:** Accepted

Controlled workload scripts should use:

```text
workloads/
└── k6/
    ├── common/
    └── scenarios/
```

instead of being mixed into ML pipeline code.

This keeps experimental input definitions independently versionable.

---

# 9. Open Decisions

The following must remain open until evidence is available.

| Decision | Status | Decision Gate |
|---|---|---|
| Exact ML prediction target | Open | After initial dataset + EDA |
| ML sampling interval | Open | After data-quality analysis + EDA |
| Prediction horizon | Open | After EDA + measuring scaling lead time |
| Final feature set | Open | After EDA |
| Final production model | Open | After baseline comparison |
| Hyperparameters | Open | During model experiments |
| Drift detection algorithm | Open | After reference/recent distributions exist |
| Drift threshold | Open | After drift experiments |
| Retraining data window | Open | After dataset growth is observed |
| Scaling formula/policy | Open | After capacity calibration |
| Min/max replicas | Open | After worker/pod profiling |
| Cooldown/hysteresis | Open | After scaling experiments |
| Final FastAPI schema | Open | After target/features finalized |
| DVC remote | Open | Before dataset growth requires external storage |
| MLflow artifact storage | Open | Before production model registry deployment |
| Final Prometheus retention | Open | After measuring TSDB disk growth |
| Final load-generator host | Open | Before controlled experiments |
| Exact k6 RPS and durations | Open | After workload calibration |
| Final endpoint mix | Open | After inspecting real backend endpoints |

---

# 10. Current Documentation Conflict Requiring Resolution

## ADR-031 — Laravel Docker Compose Deployment on Control Plane vs Kubernetes Scaling Target

**Status:** Conflict / Review Required

The current `SETUP_GUIDE.md` deploys the complete Titip.In backend stack using Docker Compose directly on VM-01:

```text
VM-01
└── docker compose
    ├── Nginx
    ├── PHP-FPM
    ├── worker
    ├── scheduler
    ├── PostgreSQL
    ├── Redis
    └── MinIO
```

Caddy currently proxies:

```text
api.titipin.me → localhost:8083
```

However, the core project architecture requires:

```text
Laravel Backend
      ↓
Kubernetes Deployment
      ↓
Worker 1 / Worker 2
      ↓
Replica Autoscaling
```

These two states cannot both represent the final autoscaling experiment.

### Required Resolution

The Docker Compose deployment may be used as:

- a temporary bootstrap deployment;
- an application validation environment;
- a reference for environment variables and dependencies.

But before autoscaling data collection and final experiments, the **Laravel scaling target must run as Kubernetes pods on the worker nodes**.

A likely final separation is:

```text
Kubernetes Workers
└── Laravel stateless/scalable backend pods

External or separately managed stateful dependencies
├── PostgreSQL
├── Redis
└── MinIO
```

The exact location of those stateful dependencies still requires a deliberate deployment decision.

### Required Documentation Update

When Kubernetes backend deployment is implemented:

- update `SETUP_GUIDE.md`;
- update Caddy upstream configuration;
- add Kubernetes Deployment/Service manifests;
- document database/Redis/MinIO placement;
- verify backend pods are scheduled only on workers;
- record image tag/digest used in each experiment.

---

# 11. Additional Implementation Reviews

## ADR-032 — Monitoring Setup Must Be Validated Against K3s/containerd

**Status:** Review Required

The current guide uses cAdvisor commands that are strongly Docker-oriented.

Before relying on cAdvisor-derived container metrics for the ML dataset:

1. confirm the metrics correctly represent K3s/containerd workloads;
2. compare them with kubelet/cAdvisor metrics already exposed by Kubernetes if available;
3. avoid collecting duplicate or misleading metrics;
4. document the final PromQL source used for each feature.

Only validated metrics should enter the dataset pipeline.

---

## ADR-033 — Prometheus Raw Metrics and ML Dataset Are Separate Layers

**Status:** Accepted

Prometheus is the operational time-series source, but it is not itself the final ML table.

```text
Prometheus Metrics
       ↓
Prometheus API Query
       ↓
Timestamp Alignment
       ↓
Validation
       ↓
Aggregation / Resampling if required
       ↓
Feature Construction
       ↓
Versioned ML Dataset
```

This separation allows the project to change ML sampling and feature engineering without changing how raw metrics are collected.

---

# 12. Decision Gates

## Gate 1 — Infrastructure Ready

Requirements:

- three K3s nodes are `Ready`;
- control plane is protected from application scheduling;
- Laravel runs as Kubernetes workload on worker nodes;
- public API path works;
- Prometheus can observe application and cluster metrics.

Then proceed to workload calibration.

---

## Gate 2 — Calibration Complete

Determine:

- useful workload range;
- approximate saturation region;
- safe capacity characteristics;
- initial k6 scenario parameters.

Then collect the first real dataset.

---

## Gate 3 — EDA Complete

Finalize:

- target;
- feature set;
- sampling interval;
- prediction horizon.

---

## Gate 4 — Baselines Evaluated

Determine whether XGBoost or another more complex candidate provides justified improvement.

---

## Gate 5 — Inference Validated

Validate model serving independently before connecting it to autoscaling.

---

## Gate 6 — Scaling Policy Validated

Verify:

- scale-up;
- scale-down;
- safety bounds;
- failure behavior;
- logging.

Only then enable autonomous predictive scaling.

---

## Gate 7 — Drift Monitoring Validated

Choose practical drift/performance triggers only after real reference and recent windows exist.

---

## Gate 8 — Final Experiment Configuration Frozen

Before predictive-vs-reactive comparison, freeze:

- infrastructure;
- application image version;
- pod requests/limits;
- scaling bounds;
- workload scenarios;
- dataset/model version;
- experiment duration;
- evaluation queries.

---

# 13. Current High-Level Architecture

The intended final experiment architecture remains:

```text
External Clients / k6
         ↓
    api.titipin.me
         ↓
       Caddy
         ↓
 Kubernetes Service
         ↓
 ┌───────┴────────┐
 ↓                ↓
Worker 1       Worker 2
Laravel Pods   Laravel Pods
 └───────┬────────┘
         ↓
 Operational Metrics
         ↓
     Prometheus
         ↓
 ┌───────┴─────────┐
 ↓                 ↓
Grafana       Data Ingestion
                   ↓
             Versioned Dataset
                   ↓
                 EDA
                   ↓
               Training
                   ↓
                MLflow
                   ↓
             Production Model
                   ↓
                FastAPI
                   ↓
             Scaling Policy
                   ↓
              Kubernetes
```

---

# 14. Update Rule

Whenever a major implementation choice changes:

1. add or update an ADR in this file;
2. state the reason;
3. state whether the previous decision is superseded;
4. update `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `ROADMAP.md`, or `SETUP_GUIDE.md` when affected;
5. do not silently change project assumptions.

This file is the authoritative decision history, while the other documentation describes the current implementation and architecture.
