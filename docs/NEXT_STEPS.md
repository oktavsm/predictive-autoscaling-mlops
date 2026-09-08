# Next Steps (MLOps Development Phase)

This document outlines the actionable steps to transition from the **Infrastructure Setup Phase** to the **MLOps Development Phase**, following the successful deployment of the K3s cluster, monitoring stack, and initial workload calibration.

## 1. Data Collection & Dataset Versioning (DVC)
* **Action:** Generate diverse workload patterns (steady, burst, gradual ramp-up, periodic) using `k6`.
* **Action:** Run the workloads for an extended period to collect a robust time-series dataset.
* **Action:** Ingest data via the Prometheus API and construct the raw dataset.
* **Action:** Initialize **DVC** in the repository and version the raw datasets.

## 2. Exploratory Data Analysis (EDA)
* **Action:** Start Jupyter notebooks in the `notebooks/` directory (`01_eda.ipynb`).
* **Action:** Analyze the correlation between `request_rate` and `cpu_utilization`.
* **Action:** Determine the optimal prediction target (e.g., predicting CPU usage directly vs. predicting request rate and calculating required CPU).
* **Action:** Determine the optimal forecasting horizon (e.g., predicting 1 minute or 5 minutes ahead) based on the application's startup latency.

## 3. Baseline Models & Feature Engineering
* **Action:** Develop feature engineering pipelines in `src/features/` (lagged variables, rolling means).
* **Action:** Implement naive baseline models (e.g., Persistence/Last-Value, Simple Moving Average) in `src/models/`.
* **Action:** Establish the baseline evaluation metrics (RMSE, MAE).

## 4. Machine Learning Experimentation (MLflow)
* **Action:** Deploy an MLflow tracking server (can be hosted on the Control Plane VM).
* **Action:** Train candidate models (e.g., Linear Regression, XGBoost, or simple LSTMs).
* **Action:** Track experiments, parameters, and evaluation metrics using MLflow.
* **Action:** Register the best performing model in the MLflow Model Registry.

## 5. Model Deployment (Inference API)
* **Action:** Wrap the selected prediction model in a REST API (using **FastAPI**).
* **Action:** Containerize the API and deploy it to the Kubernetes cluster.
* **Action:** Verify the API can retrieve current metrics from Prometheus, compute features, and return a prediction in real-time.

## 6. Predictive Scaling Controller
* **Action:** Develop the custom Kubernetes controller or configure a tool like **KEDA** to consume the Inference API predictions.
* **Action:** Implement the logic to pre-scale the `laravel-backend` deployment based on the forecast.

## 7. Comparison Experiment
* **Action:** Run identical `k6` load profiles against two setups:
  1. **Reactive HPA** (The current baseline).
  2. **Predictive Scaling** (The new ML-driven controller).
* **Action:** Compare and document the results based on p95 latency, scaling delay, and resource utilization (as defined in the proposal).

## 8. Continuous Training (Optional / Stretch Goal)
* **Action:** Implement drift detection on incoming production metrics.
* **Action:** Trigger automated retraining pipelines when data distribution shifts significantly.
