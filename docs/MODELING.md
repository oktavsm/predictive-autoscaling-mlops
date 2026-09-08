# Machine Learning Modeling Strategy

## 1. Purpose

This document defines the initial Machine Learning strategy for the **Predictive Autoscaling MLOps** project.

The ML component is intentionally designed as a supervised **time-series forecasting/regression** problem rather than Reinforcement Learning.

The project goal is not to invent a novel autoscaling algorithm. The goal is to operationalize a forecasting model inside a complete MLOps lifecycle and evaluate whether predictive information can improve autoscaling behavior compared with a reactive baseline.

---

## 2. Core Separation of Responsibilities

The ML model and the scaling policy must remain separate.

```text
Historical / Recent Metrics
          ↓
Forecasting Model
          ↓
Prediction
          ↓
Scaling Policy
          ↓
Recommended Replicas
          ↓
Kubernetes
```

The model should predict a future workload/resource condition.

The scaling policy should translate that prediction into an operational scaling decision.

This separation improves:

- explainability;
- debugging;
- independent model evaluation;
- safety;
- future model replacement;
- fair comparison with reactive autoscaling.

---

## 3. Why Not Reinforcement Learning Initially

Reinforcement Learning could theoretically learn scaling actions directly, but it is not the preferred approach for the initial project.

RL would introduce additional research questions:

- how to define the reward function;
- how to balance latency, cost, errors, and resource waste;
- how to collect enough interactions;
- how to handle unsafe exploration;
- how to distinguish policy failure from model failure;
- how to reproduce training reliably.

That complexity would shift the project toward RL research instead of MLOps lifecycle engineering.

RL can remain a future extension after the forecasting-based pipeline is complete.

---

## 4. Initial ML Task

The initial task is:

> **Supervised time-series forecasting / regression**

Conceptually:

```text
X(t) → y(t + h)
```

Where:

- `X(t)` contains current and historical operational metrics;
- `h` is the prediction horizon;
- `y(t+h)` is the future value to predict.

The exact target, horizon, sampling interval, and feature set must remain open until actual data is collected and EDA is completed.

---

## 5. Candidate Prediction Targets

Current candidates:

1. future request rate;
2. future CPU utilization;
3. future workload/resource demand.

### Initial Hypothesis

Before EDA, **future request rate** is the preferred hypothesis because it represents workload more directly and is less coupled to the autoscaling decision itself.

Example:

```text
Request Rate
    ↓
Application Load
    ↓
CPU / Latency
    ↓
Scaling Decision
```

CPU utilization is affected by both workload and current replica count.

For example:

```text
100 req/s + 1 replica
→ high CPU

100 req/s + 4 replicas
→ lower CPU per pod
```

The incoming workload is the same, but CPU behavior changes because the system has already scaled.

Therefore, forecasting request rate can produce a cleaner separation:

```text
ML:
predict future traffic

Scaling Policy:
traffic forecast → required replicas
```

This remains a hypothesis until EDA confirms whether request rate is a suitable target.

---

## 6. Data Source

The Machine Learning dataset is derived from Prometheus operational metrics.

```text
Laravel / Kubernetes
        ↓
Prometheus
        ↓
Prometheus API
        ↓
Ingestion Pipeline
        ↓
Validated Time-Series Dataset
        ↓
Feature Engineering
        ↓
Training
```

Candidate raw metrics:

- timestamp;
- request rate;
- CPU utilization;
- memory utilization;
- response latency;
- replica count;
- HTTP error rate;
- network metrics if useful;
- endpoint/request composition when available.

Not every collected metric must become a feature.

---

## 7. Repository Mapping

The current repository already provides suitable directories.

Recommended responsibilities:

```text
src/
├── data/
│   ├── prometheus_client.py
│   ├── validation.py
│   └── dataset.py
├── features/
│   ├── lag_features.py
│   ├── rolling_features.py
│   └── preprocessing.py
├── models/
│   ├── baselines.py
│   ├── linear.py
│   ├── xgboost_model.py
│   └── evaluation.py
├── inference/
│   └── predictor.py
└── scaling/
    └── policy.py

pipelines/
├── ingestion/
│   └── run_ingestion.py
├── training/
│   └── train.py
└── retraining/
    └── retrain.py

notebooks/
├── 01_data_quality.ipynb
├── 02_eda.ipynb
└── 03_model_experiments.ipynb

configs/
├── data.yaml
├── training.yaml
└── model.yaml
```

These filenames are recommendations, not mandatory final names.

Avoid duplicating responsibilities across `src/` and `pipelines/`:

- `src/` contains reusable implementation;
- `pipelines/` contains orchestration/entry points.

---

## 8. Dataset Construction

Prometheus metrics will likely arrive as separate time-series.

The ingestion pipeline should create a timestamp-aligned dataset such as:

| timestamp | request_rate | cpu | memory | latency_p95 | replicas |
|---|---:|---:|---:|---:|---:|
| t0 | ... | ... | ... | ... | ... |
| t1 | ... | ... | ... | ... | ... |
| t2 | ... | ... | ... | ... | ... |

The pipeline should:

- preserve timestamps;
- align metric intervals;
- handle missing observations;
- avoid duplicate timestamps;
- validate ranges;
- record collection metadata;
- record workload scenario/run ID separately for traceability.

---

## 9. Sampling Interval Decision

The sampling interval must not be chosen arbitrarily.

Candidate examples:

```text
5 seconds
15 seconds
30 seconds
60 seconds
```

The appropriate value depends on:

- Prometheus scrape interval;
- how quickly the workload changes;
- autoscaling response times;
- metric noise;
- desired prediction horizon;
- available dataset size.

### Decision Gate

The final sampling interval should be selected after:

1. initial workload generation;
2. Prometheus collection;
3. EDA;
4. analysis of temporal resolution and noise.

---

## 10. Prediction Horizon Decision

The prediction horizon determines how far into the future the model forecasts.

Conceptually:

```text
Now
 │
 ├── 15s ahead
 ├── 30s ahead
 ├── 60s ahead
 └── ...
```

The horizon should be operationally useful for scaling.

Too short:

- prediction may not provide enough lead time before scaling completes.

Too long:

- prediction error may become too high.

The horizon must therefore be selected using both:

- model performance;
- observed Kubernetes scaling/pod-startup timing.

The final value remains open before EDA and infrastructure profiling.

---

## 11. Feature Engineering

For classical regression models, time-series behavior can be represented using lag and rolling features.

### 11.1 Lag Features

Example:

```text
request_rate_t
request_rate_t-1
request_rate_t-2
request_rate_t-3

cpu_t
cpu_t-1

latency_t
latency_t-1
```

### 11.2 Rolling Features

Candidate features:

```text
rolling_mean_request
rolling_std_request
rolling_max_request
rolling_mean_cpu
rolling_mean_latency
```

Possible window lengths should be derived from the selected sampling interval and workload characteristics.

### 11.3 Current System State

Candidate state features:

- replica count;
- current CPU;
- current memory;
- current latency;
- current request rate.

### 11.4 Time Features

Timestamp-derived features may be added only when justified by observed periodic structure.

Examples:

- minute index;
- hour;
- cyclic time encoding.

Do not add calendar features automatically when the controlled experiment does not contain meaningful day/hour semantics.

---

## 12. Preventing Data Leakage

Time-series data must not use random train/test splitting.

Wrong:

```text
randomly shuffle all rows
train_test_split(...)
```

This allows future observations to influence training and produces unrealistic evaluation.

Preferred:

```text
Past                    Future
│-------------------------│
TRAIN        VALIDATION   TEST
```

Use chronological splitting.

Example concept:

```text
first 60%  → training
next 20%   → validation
last 20%   → test
```

The exact percentage is not final.

For more robust evaluation, walk-forward or rolling-window validation can later be used.

### Leakage From Rolling Features

Rolling features must only use information available at or before time `t`.

Never compute a centered rolling window that includes future timestamps.

---

## 13. Model Progression

The project should start with simple baselines before complex models.

Recommended progression:

```text
Naive Persistence
      ↓
Moving Average
      ↓
Linear Regression
      ↓
Tree-Based Regression
      ↓
Optional Complex Sequence Model
```

---

## 14. Baseline 1: Persistence Forecast

The simplest forecasting baseline:

```text
prediction(t+h) = current_value(t)
```

Example:

```text
current request rate = 30 req/s
forecast = 30 req/s
```

This baseline is essential.

A more complex model is only justified if it consistently outperforms a simple persistence strategy.

---

## 15. Baseline 2: Moving Average

A moving-average baseline predicts future workload from a recent window.

Example:

```text
forecast = mean(last N request-rate observations)
```

This provides a stronger reference for smooth workloads.

---

## 16. Baseline 3: Linear Regression

Linear regression is the first supervised ML baseline.

Possible input:

```text
request_rate_t
request_rate_t-1
request_rate_t-2
cpu_t
latency_t
replica_count_t
```

Target:

```text
request_rate_t+h
```

Advantages:

- simple;
- interpretable;
- fast training;
- fast inference;
- easy to reproduce.

---

## 17. Main Candidate: XGBoost Regression

The recommended main model candidate is:

> **XGBoost Regressor with lag and rolling features**

Why it is a good fit:

- handles nonlinear relationships;
- works well on structured tabular features;
- does not require massive datasets;
- relatively lightweight to retrain;
- fast inference;
- supports feature importance;
- straightforward MLflow integration;
- easier to operationalize than deep sequence models.

Possible feature vector:

```text
request_rate_t
request_rate_t-1
request_rate_t-2
request_rate_t-3

cpu_t
cpu_t-1

memory_t

latency_t
latency_t-1

rolling_mean_request
rolling_std_request
rolling_mean_cpu

replica_count
```

Target example:

```text
future_request_rate
```

The final feature set must be selected after EDA.

---

## 18. Optional Models

### 18.1 ARIMA / Classical Time-Series Model

Can be used as an additional forecasting baseline, particularly if a single target such as request rate shows strong autoregressive structure.

### 18.2 LSTM

LSTM can be considered if:

- sufficient sequential data has been collected;
- temporal patterns justify a sequence model;
- simpler models have already been evaluated;
- the additional complexity provides measurable benefit.

LSTM should not be the first model simply because the data is time-series.

### 18.3 Reinforcement Learning

RL remains future work and is outside the initial modeling strategy.

---

## 19. Model Evaluation

Primary regression metrics:

- MAE;
- RMSE;
- MAPE.

### MAE

Useful for average prediction error in the same unit as the target.

### RMSE

Penalizes large prediction errors more strongly.

### MAPE

Useful for relative percentage error, but must be interpreted carefully when the true target approaches zero.

If request rate can be zero or near zero, MAPE may become unstable. In that case, MAE/RMSE or another relative metric may be more reliable.

### Evaluation Rule

Do not select the model only from one metric.

Also inspect:

- prediction plots over time;
- errors during spike/bursty periods;
- errors under changed workload distribution;
- inference latency;
- operational usefulness for scaling.

---

## 20. Model Selection

Candidate models should be compared against the baselines using the same chronological dataset split.

Conceptually:

```text
Dataset Version X
      ↓
Same Train / Validation / Test Windows
      ↓
┌───────────────┬────────────┬───────────┐
│ Persistence   │ Linear     │ XGBoost   │
└───────────────┴────────────┴───────────┘
      ↓
MAE / RMSE / MAPE + Operational Criteria
      ↓
Selected Candidate
```

A complex model should not be selected unless the improvement justifies its additional cost and complexity.

---

## 21. DVC Integration

DVC is used to version datasets and make experiments traceable.

Conceptually:

```text
raw data
   ↓
validated dataset
   ↓
dataset v1
dataset v2
dataset v3
```

Each model run should be traceable to:

- dataset version;
- preprocessing version;
- feature configuration;
- training configuration;
- code commit.

Large datasets should not be permanently stored directly in Git.

The final DVC remote/artifact storage strategy remains an open infrastructure decision.

---

## 22. MLflow Integration

MLflow should track each experiment.

Recommended logged information:

### Parameters

- model type;
- hyperparameters;
- target;
- prediction horizon;
- sampling interval;
- lag configuration;
- rolling-window configuration;
- dataset version.

### Metrics

- MAE;
- RMSE;
- MAPE;
- training duration;
- inference latency when measured.

### Artifacts

- model;
- feature list;
- evaluation plots;
- residual/error plots;
- configuration snapshot.

### Tags

- Git commit;
- dataset version;
- experiment/run ID;
- workload regime.

---

## 23. Model Registry

Training must not overwrite the production model automatically.

```text
Training
   ↓
Candidate Model
   ↓
Evaluation
   ↓
┌───────────────┬──────────────┐
│ Promote       │ Reject       │
└───────────────┴──────────────┘
   ↓                   ↓
Production        Keep Current
```

Promotion criteria should be defined after baseline model performance is known.

---

## 24. Model Serving

The selected production model will be served using FastAPI.

Conceptual flow:

```text
Recent Features
      ↓
FastAPI /predict
      ↓
Production Model
      ↓
Forecast + Model Version
```

The exact API schema must remain open until the feature set and target are finalized.

Possible response concept:

```json
{
  "prediction": 42.7,
  "target": "request_rate",
  "horizon_seconds": 30,
  "model_version": "3"
}
```

This is only an example contract.

---

## 25. Scaling Policy

The scaling policy must remain separate from inference.

If the model forecasts request rate, a simple policy might later use experimentally measured safe capacity per replica.

Conceptually:

```text
predicted workload
      ↓
safe capacity per replica
      ↓
recommended replicas
```

Example formula:

```text
recommended_replicas =
ceil(predicted_request_rate / safe_capacity_per_replica)
```

Then apply:

- minimum replicas;
- maximum replicas;
- safety margin;
- cooldown;
- hysteresis if required.

The exact policy must be derived from capacity calibration and scaling experiments.

---

## 26. Why This Separation Matters

Consider:

```text
Model output:
future request rate = 50 req/s
```

The ML component can be evaluated independently.

Then the scaling policy decides:

```text
50 req/s
 ↓
3 replicas
```

If scaling behavior is poor, it becomes easier to identify whether the problem comes from:

- forecast error;
- policy design;
- Kubernetes startup delay;
- resource limits;
- infrastructure capacity.

---

## 27. Drift Monitoring

The initial production model is trained on a reference data distribution.

Later observations may change.

Potential drift signals:

- request-rate distribution change;
- CPU distribution change;
- latency distribution change;
- endpoint-mix change;
- prediction distribution change;
- recent prediction error increase.

The final drift-detection technique must be selected after real data exists.

Possible later candidates:

- Kolmogorov-Smirnov test;
- Wasserstein distance;
- Population Stability Index;
- rolling MAE/RMSE;
- combined data + performance trigger.

Do not lock a method before observing the actual data.

---

## 28. Continuous Training Flow

```text
New Prometheus Data
      ↓
Ingestion
      ↓
Validation
      ↓
Dataset Update
      ↓
DVC Version
      ↓
Drift / Performance Check
      ↓
Trigger?
  ┌───────┴───────┐
  │               │
 No              Yes
  │               ↓
  │           Retraining
  │               ↓
  │        Candidate Model
  │               ↓
  │          Evaluation
  │          ┌────┴────┐
  │          ↓         ↓
  │       Promote    Reject
  │          ↓         ↓
  └──── Production Model
```

---

## 29. Retraining Inputs

Retraining should use validated and versioned data.

Possible strategies:

- all historical data;
- fixed recent window;
- weighted recent data;
- reference data + recent drifted window.

The final strategy should be determined after dataset growth and drift behavior are observed.

---

## 30. Training Pipeline Responsibilities

Recommended:

```text
pipelines/training/train.py
```

should orchestrate:

1. load configuration;
2. load versioned dataset;
3. chronological split;
4. feature generation;
5. baseline training;
6. candidate-model training;
7. evaluation;
8. MLflow logging;
9. model artifact creation;
10. candidate registration.

Reusable logic belongs inside `src/`.

---

## 31. Retraining Pipeline Responsibilities

Recommended:

```text
pipelines/retraining/retrain.py
```

should orchestrate:

1. identify new validated dataset version;
2. check retraining trigger;
3. build training window;
4. train candidate;
5. evaluate candidate against production model;
6. log results;
7. promote or reject.

The production model must remain unchanged when the candidate fails evaluation.

---

## 32. Notebook Responsibilities

Recommended notebooks:

```text
notebooks/
├── 01_data_quality.ipynb
├── 02_eda.ipynb
└── 03_model_experiments.ipynb
```

### Data Quality

Inspect:

- missing timestamps;
- duplicates;
- metric ranges;
- unexpected zeros;
- gaps;
- outliers.

### EDA

Answer:

- what metric best represents workload;
- which metrics correlate with workload;
- how noisy each metric is;
- whether there are recurring patterns;
- how workloads differ across scenarios;
- what sampling interval is appropriate;
- what prediction horizon may be useful.

### Model Experiments

Compare:

- persistence;
- moving average;
- linear regression;
- XGBoost;
- optional additional candidate.

---

## 33. Decision Gate After EDA

Only after EDA should the project finalize:

- prediction target;
- sampling interval;
- prediction horizon;
- lag configuration;
- rolling windows;
- final feature set.

This prevents the model design from being based purely on assumptions.

---

## 34. Decision Gate After Baseline

After baseline evaluation:

```text
If simple model is sufficient
→ keep simple model

If performance is insufficient
→ justify more complex model
```

A complex model is not automatically better for this project.

Operational simplicity is also valuable.

---

## 35. Reactive vs Predictive Evaluation

The predictive system should be evaluated against a reactive baseline under the same workload.

### Reactive

```text
workload increases
      ↓
CPU/resource metric increases
      ↓
threshold crossed
      ↓
HPA scales
```

### Predictive

```text
historical/recent workload
      ↓
forecast future workload
      ↓
scaling policy
      ↓
scale before expected increase
```

Compare:

- response latency;
- p95/p99 latency;
- error rate;
- CPU and memory;
- replica count;
- scaling responsiveness;
- SLO violations;
- resource waste.

Predictive scaling must not be assumed superior before experimental evidence exists.

---

## 36. Recommended Initial Modeling Roadmap

```text
Prometheus Collection
      ↓
Validated Dataset
      ↓
EDA
      ↓
Choose Target / Horizon / Sampling
      ↓
Persistence Baseline
      ↓
Moving Average
      ↓
Linear Regression
      ↓
XGBoost Regression
      ↓
Compare
      ↓
Select Justified Candidate
      ↓
MLflow Registry
      ↓
FastAPI Serving
      ↓
Scaling Policy
      ↓
Kubernetes Integration
      ↓
Drift Monitoring
      ↓
Continuous Training
```

Optional models such as ARIMA/LSTM are added only when justified by the collected data.

---

## 37. Initial Recommendation

Before real data is available, the working hypothesis is:

```text
Task:
time-series forecasting / regression

Likely target:
future request rate

Baselines:
persistence
moving average
linear regression

Main candidate:
XGBoost Regressor

Features:
lag + rolling operational metrics

Serving:
FastAPI

Tracking / Registry:
MLflow

Dataset Versioning:
DVC

Scaling:
separate rule-based scaling policy
```

All values that depend on system behavior must remain open until calibration and EDA are complete.

---

## 38. Summary

The modeling strategy follows five principles:

1. **Start with forecasting/regression, not RL.**
2. **Use real Prometheus operational data.**
3. **Use chronological validation to prevent leakage.**
4. **Compare simple baselines before choosing a more complex model.**
5. **Keep prediction, scaling policy, and model lifecycle as separate components.**
