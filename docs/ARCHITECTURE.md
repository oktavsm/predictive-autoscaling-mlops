# Architecture

## 1. Architecture Overview

The project is a cloud-native MLOps experiment built around an existing
Laravel backend.

The architecture has four major planes:

1.  **Workload plane** --- application API and workload generation.
2.  **Observability plane** --- Prometheus and Grafana.
3.  **ML/MLOps plane** --- ingestion, dataset management, training,
    MLflow, and inference.
4.  **Scaling plane** --- scaling policy and Kubernetes.

``` text
                    WORKLOAD PLANE
┌──────────────────────────────────────────────┐
│ React Web / Android / Load Generator         │
└──────────────────────┬───────────────────────┘
                       ↓
              ┌─────────────────┐
              │ Laravel Backend │
              │   Kubernetes    │
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              ↓                 ↓
         Worker VM 1       Worker VM 2


                 OBSERVABILITY PLANE
                       │
                       ↓
                ┌────────────┐
                │ Prometheus │
                └─────┬──────┘
                      │
              ┌───────┴───────┐
              ↓               ↓
         Prometheus API     Grafana


                     ML PLANE
              Prometheus API
                     ↓
              Data Ingestion
                     ↓
              Data Validation
                     ↓
                    DVC
                     ↓
                 Training
                     ↓
                  MLflow
                     ↓
              Model Registry
                     ↓
                Inference API


                   SCALING PLANE
                Inference API
                     ↓
                Scaling Policy
                     ↓
                  Kubernetes
                     ↓
              Backend Replicas
```

------------------------------------------------------------------------

## 2. Infrastructure Topology

The initial environment uses three laboratory VMs.

### VM-01 --- Control Plane

Responsibilities: - Kubernetes control plane; - Prometheus; - Grafana; -
lightweight MLOps services where practical; - orchestration/management
components.

Target: - 2 vCPU - 4 GB RAM - 30--50 GB storage

### VM-02 --- Worker

Responsibilities: - Laravel backend pods; - supporting application pods
where required.

Target: - 1 vCPU - 1 GB RAM - 12 GB storage

### VM-03 --- Worker

Responsibilities: - Laravel backend pods; - supporting application pods
where required.

Target: - 1 vCPU - 1 GB RAM - 12 GB storage

The worker resources are intentionally constrained for experimentation.
They must be increased if the infrastructure itself becomes the limiting
factor.

------------------------------------------------------------------------

## 3. Scheduling Policy

The backend workload should be scheduled on worker nodes rather than the
control plane.

Use Kubernetes scheduling controls where appropriate, such as: -
taints/tolerations; - node labels; - node selectors/affinity.

Do not assume that Kubernetes will automatically keep workloads away
from the control plane without configuration.

------------------------------------------------------------------------

## 4. Application Deployment

The existing application remains outside this repository.

The MLOps experiment deploys the backend workload as a containerized
service.

``` text
Client / Load Generator
          ↓
     Kubernetes Service
          ↓
    ┌─────┼─────┐
    ↓     ↓     ↓
 Backend Backend Backend
  Pod 1   Pod 2   Pod N
          ↓
       Database
```

The database is not the primary autoscaling target.

The backend replica count is the main scaling variable.

------------------------------------------------------------------------

## 5. Workload Generation

Two workload sources are supported.

### Real application traffic

Requests may originate from: - React Web; - Android application.

### Controlled traffic

A load-testing tool can send requests directly to the Laravel API.

Controlled traffic is preferred for repeatable experiments.

The load generator should define: - endpoint mix; - request rate; -
concurrency; - duration; - scenario type.

Example:

``` text
Steady
20 req/s for 10 min

Gradual
20 → 40 → 60 → 80 → 100 req/s

Spike
20 req/s → 200 req/s

Periodic
20 ↔ 100 req/s

Bursty
20 → 200 → 30 → 250 → 20 req/s
```

The exact values are experimental parameters, not fixed architecture
requirements.

------------------------------------------------------------------------

## 6. Monitoring Architecture

Prometheus is the central metrics store.

``` text
Kubernetes Nodes
      │
      ├── Node Metrics
      │
      ├── Pod Metrics
      │
      └── Application Metrics
              │
              ▼
         Prometheus
              │
       ┌──────┴──────┐
       ↓             ↓
Prometheus API    Grafana
```

The system should collect only metrics that support: - ML features; -
scaling decisions; - evaluation; - debugging.

------------------------------------------------------------------------

## 7. Data Ingestion Architecture

The first data pipeline is:

``` text
Prometheus
    ↓
Prometheus API
    ↓
Collector
    ↓
Data Validation
    ↓
Feature Construction
    ↓
Versioned Dataset
```

The collector should: - query a defined time range; - preserve
timestamps; - handle missing observations; - avoid duplicates; -
validate metric ranges; - record collection metadata.

The ingestion mechanism should be idempotent where practical.

------------------------------------------------------------------------

## 8. Dataset Versioning

DVC is planned for dataset versioning.

Conceptually:

``` text
Raw Data
   ↓
Validated Data
   ↓
Dataset v1
   ↓
Dataset v2
   ↓
Dataset v3
```

A dataset version should be traceable to: - collection period; -
source/query configuration; - preprocessing version; - relevant workload
scenario.

------------------------------------------------------------------------

## 9. ML Training Architecture

``` text
Versioned Dataset
       ↓
Preprocessing
       ↓
Feature Engineering
       ↓
Train / Validation / Test
       ↓
Model Training
       ↓
Evaluation
       ↓
MLflow Tracking
       ↓
Candidate Model
```

The model should first be compared with a simple baseline before adding
complexity.

Potential baselines: - naive/last-value forecast; - moving average; -
simple regression.

Potential ML models can be selected after EDA.

------------------------------------------------------------------------

## 10. MLflow Architecture

MLflow is responsible for: - experiment tracking; - parameter logging; -
metric logging; - model artifacts; - model registry.

Example lifecycle:

``` text
Experiment
   ↓
Run
   ↓
Metrics + Parameters + Artifact
   ↓
Candidate Model
   ↓
Model Registry
```

A production model should have an explicit version.

------------------------------------------------------------------------

## 11. Inference Architecture

The model will be exposed through an inference API.

Conceptually:

``` text
Feature Input
     ↓
Inference API
     ↓
Production Model
     ↓
Forecast
     ↓
Scaling Policy
```

Example endpoint:

``` text
POST /predict
```

The exact request/response schema remains open until the ML target and
feature set are finalized.

------------------------------------------------------------------------

## 12. Scaling Architecture

Prediction and scaling decision logic should remain separate.

``` text
             ML Model
                ↓
            Prediction
                ↓
         Scaling Policy
                ↓
       Recommended Replicas
                ↓
           Kubernetes
                ↓
        Backend Replica Set
```

This separation allows: - independent model evaluation; - safer scaling
logic; - easier debugging; - future replacement of the ML model.

The first scaling implementation should be controlled and observable
before becoming fully autonomous.

------------------------------------------------------------------------

## 13. Predictive vs Reactive Architecture

The future experiment compares two approaches under the same workload.

``` text
                 Same Workload
                       │
             ┌─────────┴─────────┐
             ↓                   ↓
       Reactive HPA       Predictive Scaling
             │                   │
             ↓                   ↓
       Scaling Result      Scaling Result
             │                   │
             └─────────┬─────────┘
                       ↓
                  Evaluation
```

Comparison dimensions: - response latency; - scaling responsiveness; -
resource utilization; - replica behavior; - overload events; - resource
waste.

------------------------------------------------------------------------

## 14. Continuous Training Architecture

``` text
Production Metrics
       ↓
Data Ingestion
       ↓
Validation
       ↓
Dataset Update
       ↓
Drift / Performance Check
       ↓
   ┌───┴────┐
   │        │
 No Trigger  Trigger
   │        │
   │        ↓
   │    Retraining
   │        ↓
   │   Candidate Model
   │        ↓
   │    Evaluation
   │        │
   │    ┌───┴───┐
   │    ↓       ↓
   │ Promote  Reject
   │    ↓       ↓
   └── Production Model
```

Retraining must not overwrite a working production model before
evaluation.

------------------------------------------------------------------------

## 15. Monitoring Requirements

### Infrastructure

Monitor: - CPU; - memory; - network; - node health; - pod health.

### Application

Monitor: - request rate; - response latency; - error rate; - throughput.

### Scaling

Monitor: - replica count; - scaling events; - scaling decision latency.

### ML

Monitor: - prediction error; - feature distribution; - prediction
distribution; - drift indicators; - model version; - last training time.

------------------------------------------------------------------------

## 16. Control Plane Resource Considerations

VM-01 is intentionally given more RAM because it may host monitoring and
MLOps services.

However, training can be resource-intensive.

If training causes resource contention: 1. move training to a worker
during non-critical periods; 2. run training externally/local/cloud; 3.
reduce model complexity; 4. increase VM resources.

Do not sacrifice Kubernetes stability merely to keep every MLOps
component on the control plane.

------------------------------------------------------------------------

## 17. Storage Considerations

The 12 GB worker storage allocation is intended as a minimal starting
point.

Avoid storing large datasets or model artifacts on worker nodes.

Prefer: - externalized model artifacts; - a dedicated persistent
volume; - object storage when available; - compact datasets for
experiments.

The storage strategy can evolve after measuring actual data growth.

------------------------------------------------------------------------

## 18. Deployment Workflow

The MLOps repository uses GitHub Actions for CI/CD.

``` text
Developer
   ↓
Git Push
   ↓
GitHub
   ↓
CI
 ├── Lint
 ├── Test
 └── Build
   ↓
Container Image
   ↓
Deployment
   ↓
Lab VM / Kubernetes
```

The exact deployment mechanism may use SSH, a deployment agent, or
another secure method available in the lab.

Secrets must never be committed to the repository.

------------------------------------------------------------------------

## 19. Architecture Principles

1.  Existing application repositories remain independent.
2.  Laravel backend is the primary scaling target.
3.  Frontends are workload sources, not required cluster components.
4.  Controlled API load generation is preferred for reproducible
    experiments.
5.  Prediction and scaling policy remain separate.
6.  Monitoring is treated as a first-class component.
7.  Dataset and model versions must be traceable.
8.  Candidate models require evaluation before promotion.
9.  Infrastructure constraints must not be confused with application
    behavior.
10. Start simple and add complexity only when experiments justify it.

------------------------------------------------------------------------

## 20. Open Architecture Decisions

The following remain intentionally open:

-   exact prediction target;
-   prediction horizon;
-   metric sampling interval;
-   final feature set;
-   final ML model;
-   drift detection method;
-   scaling policy;
-   final inference API schema;
-   final artifact storage strategy.

These decisions should be resolved from actual implementation evidence.
