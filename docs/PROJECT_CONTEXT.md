# Project Context

## 1. Project Identity

**Project:** Predictive Autoscaling MLOps\
**Domain:** MLOps, Cloud Computing, Cloud-Native Infrastructure,
Kubernetes\
**Primary workload:** Existing Jastip and Preloved semi-e-commerce
application\
**Primary scaling target:** Laravel backend\
**ML task:** Time-series forecasting / regression

### Project objective

Build a production-oriented MLOps system that uses Machine Learning to
forecast application workload or resource demand and supports proactive
autoscaling of a containerized backend.

The project is primarily an **MLOps and infrastructure engineering
project**, not an ML algorithm research project. The focus is on how a
model is collected, trained, versioned, deployed, monitored, and
continuously updated in a real application environment.

------------------------------------------------------------------------

## 2. Existing Application

The experimental workload is an existing semi-e-commerce application for
Jastip and preloved goods.

Users can perform activities such as: - searching listings; - viewing
listing details; - creating listings; - searching offers; - creating
offers; - other supported application activities.

The application consists of:

  Component        Technology
  ---------------- -------------------------------
  Web client       React
  Android client   Kotlin + Jetpack Compose
  Backend          PHP Laravel
  Database         Existing application database

The web and Android applications consume the same Laravel backend.

### Important architectural decision

The existing application remains in its own repositories.

This MLOps repository is responsible for: - ML/data pipelines; -
inference; - MLOps tooling; - monitoring configuration; - Kubernetes
deployment configuration related to the experiment; - CI/CD for the
MLOps components; - experiment code and documentation.

The existing application's CI/CD pipelines should not be unnecessarily
replaced or duplicated.

------------------------------------------------------------------------

## 3. Workload Model

The frontend applications do not need to run inside the experimental
Kubernetes cluster.

For controlled experiments, requests can be generated directly against
the Laravel API.

``` text
React Web ───────┐
                 ├──> Laravel API
Android App ─────┘

Controlled Load Generator ──> Laravel API
```

The direct API approach makes workload experiments reproducible because
request rate, concurrency, duration, and endpoint mix can be controlled.

Real Web/Android activity can still be used for qualitative validation.

------------------------------------------------------------------------

## 4. Core Problem

Traditional reactive autoscaling generally reacts after a resource or
workload threshold has already been reached.

``` text
Workload increases
      ↓
Resource utilization increases
      ↓
Threshold reached
      ↓
Scale
```

This may introduce a delay between workload growth and capacity
adjustment.

The proposed approach uses forecasting:

``` text
Historical + Current Metrics
            ↓
       ML Forecasting
            ↓
     Predicted Workload
            ↓
       Scaling Policy
            ↓
      Proactive Scaling
```

The project investigates whether predictive information can improve
scaling responsiveness and resource efficiency.

The project must not assume that predictive autoscaling is better. That
conclusion must come from experiments.

------------------------------------------------------------------------

## 5. Machine Learning Task

The current task is **time-series forecasting / regression**.

The model will use historical and current operational metrics to predict
future workload or resource demand.

Candidate features: - request rate; - CPU utilization; - memory
utilization; - response latency; - replica count; - network metrics when
useful; - timestamp-derived features when justified.

Candidate prediction targets: - future request rate; - future CPU
utilization; - future workload/resource demand.

### Important open decision

The final target, feature set, prediction horizon, sampling interval,
and model must be selected after real data is collected and analyzed.

Do not hard-code CPU forecasting as the final project target before EDA.

------------------------------------------------------------------------

## 6. Dynamic Data

The dataset is generated from a live application environment rather than
a static public dataset.

The primary data path is:

``` text
Application Workload
        ↓
Kubernetes
        ↓
Prometheus
        ↓
Prometheus API
        ↓
Data Ingestion
        ↓
Validated Time-Series Dataset
```

The dataset continuously grows as new observations are collected.

Initial candidate metrics: - request rate; - CPU utilization; - memory
utilization; - response latency; - replica count; - network activity.

The exact collection interval is an open technical decision and should
be selected based on workload dynamics and storage/query cost.

------------------------------------------------------------------------

## 7. Workload Scenarios

Controlled scenarios are used to produce reproducible data.

### Steady

Relatively stable request rate.

### Gradual Increase

Request rate increases progressively.

### Spike

Request rate suddenly increases.

### Periodic

Workload follows a repeating pattern.

### Bursty

Short, irregular workload bursts occur.

The scenarios are not intended to pretend to be natural user behavior.
Their purpose is to deliberately expose the system to different
operating conditions and make experiments repeatable.

------------------------------------------------------------------------

## 8. Data Drift

Potential drift sources: - increased traffic; - changed request
patterns; - new application behavior; - changes in resource
configuration; - time-dependent usage patterns; - previously unseen
workload patterns.

Example:

``` text
Training distribution
20–80 req/s
       ↓
Later workload
50–200 req/s
       ↓
Potential distribution shift
```

Drift is important because a forecasting model trained on one workload
distribution may become less accurate under a different distribution.

The project will monitor both data characteristics and recent prediction
performance.

------------------------------------------------------------------------

## 9. Continuous Training Strategy

Continuous Training uses two complementary trigger types.

### Scheduled trigger

Periodically check whether enough new validated data has accumulated for
retraining.

### Condition-based trigger

Consider retraining when: - data drift exceeds a defined threshold; -
recent prediction error increases; - model performance degrades.

Retraining should not happen for every new sample.

The intended lifecycle is:

``` text
New Data
   ↓
Validation
   ↓
Dataset Update
   ↓
Drift / Performance Check
   ↓
Trigger?
   ├── No → Continue Monitoring
   └── Yes
         ↓
      Retrain
         ↓
   Candidate Model
         ↓
     Evaluation
      ├── Better/Valid → Promote
      └── Worse/Invalid → Reject
```

The production model must remain available when a candidate model fails
evaluation.

------------------------------------------------------------------------

## 10. MLOps Lifecycle

The complete lifecycle is:

``` text
Data Collection
      ↓
Data Validation
      ↓
Dataset Versioning
      ↓
Training
      ↓
Evaluation
      ↓
Model Registry
      ↓
Model Serving
      ↓
Inference
      ↓
Scaling Decision
      ↓
Monitoring
      ↓
Drift / Performance Detection
      ↓
Continuous Training
      └────────────→ Training
```

The project should maintain traceability between: - model version; -
dataset version; - source code version; - training configuration; -
evaluation metrics.

------------------------------------------------------------------------

## 11. Technology Stack

  Area                  Technology       Purpose
  --------------------- ---------------- ----------------------------
  Containerization      Docker           Package services
  Orchestration         Kubernetes       Deploy and scale backend
  Monitoring            Prometheus       Collect metrics
  Visualization         Grafana          Observe system behavior
  Dataset versioning    DVC              Version datasets
  Experiment tracking   MLflow           Track experiments
  Model registry        MLflow           Manage model versions
  Model serving         FastAPI          Expose inference endpoint
  CI/CD                 GitHub Actions   Automate test/build/deploy
  ML                    Python           Data and model development
  Infrastructure        Lab VMs          Experimental environment

Tools can be replaced when an implementation constraint justifies the
change.

------------------------------------------------------------------------

## 12. Infrastructure Boundary

The initial experiment uses three lab VMs.

  -----------------------------------------------------------------------
  Node                    Role                    Initial target
  ----------------------- ----------------------- -----------------------
  VM-01                   Control plane +         2 vCPU / 4 GB RAM /
                          monitoring/MLOps        30--50 GB

  VM-02                   Worker                  1 vCPU / 1 GB RAM / 12
                                                  GB

  VM-03                   Worker                  1 vCPU / 1 GB RAM / 12
                                                  GB
  -----------------------------------------------------------------------

The worker nodes intentionally start small to make resource pressure and
scaling behavior visible.

However, infrastructure itself must not become the dominant bottleneck.
If Kubernetes system components or the application cannot operate
reliably, worker resources should be increased.

------------------------------------------------------------------------

## 13. Development and Deployment

Development is primarily local.

GitHub is used for: - source control; - CI; - build; - deployment
automation.

The experimental environment is hosted on the laboratory VMs.

``` text
Local Development
       ↓
Git Push
       ↓
GitHub
       ↓
GitHub Actions
       ↓
Test / Build
       ↓
Deploy
       ↓
Lab VMs
       ↓
Kubernetes
```

Codespaces is an optional development environment if required by a
course activity. It is not the production or experiment runtime.

------------------------------------------------------------------------

## 14. Evaluation

### Model metrics

-   MAE
-   RMSE
-   MAPE

### System metrics

-   inference latency;
-   API response latency;
-   CPU utilization;
-   memory utilization;
-   replica count;
-   scaling decision latency;
-   error rate.

### Operational metrics

-   scaling responsiveness;
-   resource efficiency;
-   reliability;
-   overload/SLO violations;
-   over-provisioning/resource waste.

Predictive autoscaling will eventually be compared with a reactive
autoscaling baseline under comparable workload scenarios.

------------------------------------------------------------------------

## 15. Scope

### In scope

-   dynamic operational data;
-   forecasting/regression;
-   data validation;
-   dataset versioning;
-   model training;
-   experiment tracking;
-   model registry;
-   inference API;
-   Kubernetes deployment;
-   monitoring;
-   Continuous Training;
-   predictive scaling prototype;
-   predictive vs reactive experiments.

### Out of scope initially

-   novel ML algorithm research;
-   rebuilding the existing application;
-   database autoscaling;
-   VM/cluster autoscaling;
-   full production cloud infrastructure;
-   claiming predictive autoscaling superiority without experiments.

------------------------------------------------------------------------

## 16. Current Decisions

  Decision                                                Status
  ------------------------------------------------------- ---------
  Existing Jastip/Preloved app as workload                Decided
  Laravel backend as primary scaling target               Decided
  React and Android as real workload sources              Decided
  Direct API load generation for controlled experiments   Decided
  Three lab VMs                                           Decided
  Kubernetes                                              Decided
  Prometheus + Grafana                                    Decided
  Forecasting/regression task                             Decided
  Continuous Training                                     Decided
  Exact target                                            Open
  Prediction horizon                                      Open
  Sampling interval                                       Open
  Final model                                             Open
  Drift method                                            Open
  Scaling policy                                          Open

------------------------------------------------------------------------

## 17. Agent Guidance

Any AI agent working on this project should:

1.  Read this document before making architectural changes.
2.  Read `ARCHITECTURE.md` for system-level constraints.
3.  Read `ROADMAP.md` before deciding implementation order.
4.  Inspect existing code before creating duplicate components.
5.  Prefer incremental and reproducible changes.
6.  Clearly distinguish decisions, assumptions, and experimental
    results.
7.  Never fabricate metrics, model performance, or infrastructure
    behavior.
8.  Do not finalize open decisions without evidence from data or
    experiments.
9.  Keep the existing application's repositories and CI/CD independent.
10. Avoid introducing infrastructure that exceeds the needs of the
    experiment.
