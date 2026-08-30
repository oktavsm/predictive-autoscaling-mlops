# Project Roadmap

## 1. Roadmap Philosophy

Build the system from the bottom up.

Do not start by implementing the complete MLOps stack. Each layer should
be validated before the next layer is introduced.

``` text
Existing Application
        ↓
Containerization
        ↓
Kubernetes
        ↓
Monitoring
        ↓
Data Collection
        ↓
EDA
        ↓
Baseline ML
        ↓
MLOps Tooling
        ↓
Inference API
        ↓
Predictive Scaling
        ↓
Continuous Training
        ↓
Experiments
```

The priority is **working infrastructure and trustworthy data before
sophisticated ML**.

------------------------------------------------------------------------

## 2. Phase 0 --- Inspect Existing Application

### Goal

Understand the existing application before integrating it with the MLOps
environment.

### Tasks

-   Identify backend entry points.
-   Identify API endpoints.
-   Identify database dependencies.
-   Identify environment variables.
-   Identify ports.
-   Identify external services.
-   Document the current CI/CD flow.
-   Determine Dockerization requirements.

### Output

`docs/EXISTING_APP.md` or equivalent documentation describing how the
existing application works.

------------------------------------------------------------------------

## 3. Phase 1 --- Prepare Laboratory VMs

### Goal

Prepare the three-node experimental environment.

### Target

  Node    Resource
  ------- -------------------------------
  VM-01   2 vCPU / 4 GB RAM / 30--50 GB
  VM-02   1 vCPU / 1 GB RAM / 12 GB
  VM-03   1 vCPU / 1 GB RAM / 12 GB

### Tasks

-   Obtain VM allocations.
-   Configure SSH.
-   Configure hostnames.
-   Configure networking.
-   Update operating system.
-   Prepare container runtime.
-   Document node addresses and roles securely.

### Output

Three reachable and documented VMs.

------------------------------------------------------------------------

## 4. Phase 2 --- Build Kubernetes Cluster

### Goal

Create a working Kubernetes cluster.

### Tasks

-   Initialize control plane.
-   Join worker nodes.
-   Configure cluster networking.
-   Configure worker scheduling.
-   Verify node health.
-   Deploy a simple test workload.

### Success condition

``` text
VM-01   Ready
VM-02   Ready
VM-03   Ready
```

### Output

Working three-node Kubernetes cluster.

------------------------------------------------------------------------

## 5. Phase 3 --- Containerize and Deploy Backend

### Goal

Run the existing Laravel backend in Kubernetes.

### Tasks

-   Build Docker image.
-   Configure environment.
-   Define Deployment.
-   Define Service.
-   Configure health checks.
-   Connect to the existing database.
-   Verify API functionality.

### Important

Do not modify the existing application's CI/CD unless required.

### Output

Laravel backend running reliably in Kubernetes.

------------------------------------------------------------------------

## 6. Phase 4 --- Monitoring

### Goal

Observe the application and infrastructure.

### Tasks

-   Install Prometheus.
-   Install Grafana.
-   Collect node metrics.
-   Collect pod metrics.
-   Add application metrics if available.
-   Build initial dashboard.

### Initial dashboard

``` text
Request Rate
CPU
Memory
Latency
Error Rate
Replica Count
```

### Output

Live Grafana dashboard.

------------------------------------------------------------------------

## 7. Phase 5 --- Workload Generation

### Goal

Create repeatable workload scenarios.

### Tasks

-   Select load-testing tool.
-   Identify representative API endpoints.
-   Define request mix.
-   Create scenario scripts.
-   Validate that scenarios produce measurable changes.

### Scenarios

-   steady;
-   gradual increase;
-   spike;
-   periodic;
-   bursty.

### Output

Versioned workload scenario definitions.

------------------------------------------------------------------------

## 8. Phase 6 --- Dynamic Data Ingestion

### Goal

Convert Prometheus metrics into a usable dataset.

### Tasks

-   Define metrics.
-   Determine sampling interval.
-   Implement Prometheus API queries.
-   Store timestamps.
-   Handle missing values.
-   Handle duplicates.
-   Validate ranges.
-   Save collection metadata.

### Output

First real workload dataset.

------------------------------------------------------------------------

## 9. Phase 7 --- Exploratory Data Analysis

### Goal

Understand the collected data before choosing the ML target.

### Questions

-   Which metric represents workload most reliably?
-   Which metrics correlate with workload?
-   Are there periodic patterns?
-   How noisy is the data?
-   Are there outliers?
-   How long is a useful prediction horizon?
-   Which workload scenarios differ most strongly?

### Output

EDA notebook/report.

### Decision gate

Only after this phase should the following be finalized: - prediction
target; - feature set; - sampling interval; - prediction horizon.

------------------------------------------------------------------------

## 10. Phase 8 --- Baseline Forecasting Model

### Goal

Establish a simple benchmark.

### Candidate baselines

-   naive/last-value forecast;
-   moving average;
-   simple regression.

### Metrics

-   MAE;
-   RMSE;
-   MAPE.

### Output

Baseline model and evaluation report.

------------------------------------------------------------------------

## 11. Phase 9 --- Dataset Versioning and Experiment Tracking

### Goal

Make ML experiments reproducible.

### DVC

Track dataset versions.

### MLflow

Track: - parameters; - metrics; - artifacts; - model versions.

### Output

Reproducible model-training workflow.

------------------------------------------------------------------------

## 12. Phase 10 --- Model Serving

### Goal

Expose the selected production candidate through an API.

### Tasks

-   Implement FastAPI service.
-   Load model from registry/artifact store.
-   Define `/predict`.
-   Validate input.
-   Return prediction and model version.
-   Add health endpoint.
-   Containerize inference service.

### Output

Working inference API.

------------------------------------------------------------------------

## 13. Phase 11 --- Scaling Policy Prototype

### Goal

Translate predictions into scaling recommendations.

Keep the model and scaling policy separate.

``` text
Prediction
    ↓
Scaling Policy
    ↓
Recommended Replica Count
```

### Tasks

-   Define initial scaling rules.
-   Add safety bounds.
-   Add minimum replicas.
-   Add maximum replicas.
-   Add cooldown behavior.
-   Log every scaling decision.

### Output

Observable scaling recommendation system.

------------------------------------------------------------------------

## 14. Phase 12 --- Kubernetes Integration

### Goal

Allow the scaling recommendation to influence Kubernetes.

### Tasks

-   Select integration mechanism.
-   Implement controlled replica updates.
-   Add safety checks.
-   Verify scaling behavior.
-   Test scale-up.
-   Test scale-down.
-   Verify failure behavior.

### Output

Predictive scaling prototype operating on the backend.

------------------------------------------------------------------------

## 15. Phase 13 --- ML Monitoring

### Goal

Monitor model behavior in addition to infrastructure.

### Monitor

-   prediction error;
-   feature distribution;
-   prediction distribution;
-   drift indicators;
-   model version;
-   training timestamp.

### Output

ML monitoring dashboard/metrics.

------------------------------------------------------------------------

## 16. Phase 14 --- Continuous Training

### Goal

Close the MLOps loop.

### Pipeline

``` text
New Production Data
        ↓
Validation
        ↓
Dataset Update
        ↓
Drift / Performance Check
        ↓
Trigger
        ↓
Retraining
        ↓
Candidate Model
        ↓
Evaluation
        ↓
Promotion / Rejection
```

### Trigger types

1.  Scheduled.
2.  Data drift.
3.  Performance degradation.

### Output

Automated or semi-automated retraining pipeline with model promotion.

------------------------------------------------------------------------

## 17. Phase 15 --- CI/CD

CI/CD should be introduced incrementally rather than before the
application works.

### CI

Run on push/pull request: - lint; - unit tests; - pipeline tests; - API
tests; - build validation.

### CD

After successful CI: - build container; - publish artifact/image; -
deploy to laboratory Kubernetes; - run smoke test.

### Output

Reproducible MLOps deployment workflow.

------------------------------------------------------------------------

## 18. Phase 16 --- Predictive vs Reactive Experiment

### Goal

Determine whether predictive information provides measurable operational
benefits.

### Compare

**Baseline** Reactive autoscaling.

**Treatment** Predictive autoscaling.

### Keep constant

-   application version;
-   infrastructure;
-   workload scenario;
-   resource limits;
-   experiment duration.

### Measure

-   response latency;
-   scaling responsiveness;
-   CPU utilization;
-   memory utilization;
-   replica count;
-   overload/SLO violations;
-   resource waste.

### Output

Experiment results and comparison report.

------------------------------------------------------------------------

## 19. Phase 17 --- Drift and Retraining Experiment

### Goal

Demonstrate that the model lifecycle responds to changed workload
characteristics.

### Example

``` text
Training
20–80 req/s
       ↓
Model v1
       ↓
Changed workload
50–200 req/s
       ↓
Drift / performance degradation
       ↓
Retraining
       ↓
Model v2
```

### Output

Evidence of: - dynamic data; - drift; - retraining trigger; - candidate
model; - model promotion/rejection.

This phase is particularly important for demonstrating the MLOps aspect
of the project.

------------------------------------------------------------------------

## 20. Phase 18 --- Final Hardening

### Tasks

-   Add health checks.
-   Add failure handling.
-   Add rollback.
-   Validate reproducibility.
-   Document deployment.
-   Document experiment configuration.
-   Clean secrets.
-   Review dashboards.
-   Review repository structure.
-   Record architecture decisions.

### Output

Final reproducible project environment.

------------------------------------------------------------------------

## 21. Suggested Repository Structure

``` text
predictive-autoscaling-mlops/
│
├── README.md
│
├── docs/
│   ├── PROJECT_CONTEXT.md
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   └── DECISIONS.md
│
├── infrastructure/
│   ├── docker/
│   ├── kubernetes/
│   └── monitoring/
│
├── pipelines/
│   ├── ingestion/
│   ├── training/
│   └── retraining/
│
├── src/
│   ├── data/
│   ├── features/
│   ├── models/
│   ├── inference/
│   └── scaling/
│
├── api/
├── tests/
├── notebooks/
├── configs/
├── scripts/
│
└── .github/
    └── workflows/
```

------------------------------------------------------------------------

## 22. AI Agent Workflow

Before implementing a task, an AI agent should:

1.  Read `README.md`.
2.  Read `docs/PROJECT_CONTEXT.md`.
3.  Read `docs/ARCHITECTURE.md`.
4.  Check the current project phase in this roadmap.
5.  Inspect existing implementation.
6.  Identify dependencies and integration points.
7.  Make the smallest reasonable change.
8.  Run relevant tests.
9.  Update documentation when architecture or decisions change.

Do not jump directly to later phases unless the earlier foundation is
already working.

------------------------------------------------------------------------

## 23. Decision Gates

The project uses explicit decision gates.

### Gate 1 --- After EDA

Finalize: - target; - features; - horizon; - sampling.

### Gate 2 --- After baseline

Decide whether more complex models are justified.

### Gate 3 --- After inference

Validate model serving independently before connecting scaling.

### Gate 4 --- After scaling prototype

Validate safe Kubernetes behavior before autonomous scaling.

### Gate 5 --- After monitoring

Define practical drift/performance triggers.

### Gate 6 --- Before final experiments

Freeze the experiment configuration.

------------------------------------------------------------------------

## 24. Course Deliverable Alignment

The project should map implementation work to the course's LK/RPS
requirements as they are assigned.

The general progression is:

``` text
LK-01
Project / architecture initiation
        ↓
Data source and dynamic-data design
        ↓
Data ingestion
        ↓
Data validation / preprocessing
        ↓
Experiment tracking / versioning
        ↓
Model training
        ↓
Model serving
        ↓
Monitoring
        ↓
Continuous Training
        ↓
Deployment / integration
```

The exact mapping of implementation tasks to individual LK numbers
should follow the latest course instructions rather than being assumed
in advance.

------------------------------------------------------------------------

## 25. Current Status

### Completed / Decided

-   Project topic selected.
-   Existing application selected as workload.
-   Laravel selected as primary scaling target.
-   Three-VM lab architecture selected.
-   Kubernetes selected.
-   Prometheus/Grafana selected.
-   Forecasting/regression selected.
-   Continuous Training selected.
-   MLOps repository separated from existing application repositories.

### Next

1.  Inspect existing application.
2.  Request/prepare three VMs.
3.  Build Kubernetes cluster.
4.  Deploy Laravel backend.
5.  Install Prometheus/Grafana.
6.  Generate first workload.
7.  Collect first dataset.

### Not Yet Final

-   prediction target;
-   prediction horizon;
-   sampling interval;
-   model;
-   drift method;
-   scaling policy;
-   inference contract.
