# Predictive Autoscaling MLOps — Live Demonstration & Verification Runbook
> **Environment:** Production Kubernetes Cluster (K3s AWS Multi-Node)  
> **Target:** Anticipatory Traffic Forecasting & Zero-Scaling-Lag Verification  
> **Public Observability:** `grafana.titipin.me` | `mlops.titipin.me` | `minio.titipin.me` | `mlflow.titipin.me`

---

## 1. Executive Summary & Objective

Traditional Horizontal Pod Autoscalers (HPA) in Kubernetes are inherently **reactive**: they observe CPU or memory saturation *after* latency has already degraded, incurring a 2–3 minute scaling lag during cold container starts.

This project implements an **anticipatory (predictive) autoscaling engine** that:
1. Ingests operational telemetry from Prometheus (`request_rate`, `php_cpu_cores`, latency).
2. Predicts future workload volume at $t+60\text{s}$ using an ensemble Random Forest regression model.
3. Proactively adjusts deployment replicas **before** request traffic peaks, eliminating scaling lag while adhering to production cooldown safeguards.

---

## 2. Pre-Flight Checklist

Execute these checks before running the live workload demonstration:

```bash
# 1. Verify all MLOps and workload pods are healthy
kubectl get pods -n mlops
kubectl get pods -n titipin

# 2. Check that the predictive scaler is serving metrics to Prometheus
kubectl exec -n mlops deploy/mlops-inference -c inference-api -- \
  curl -s "http://monitoring-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090/api/v1/targets" | \
  jq '.data.activeTargets[] | select(.labels.namespace=="mlops") | {job: .labels.job, health: .health}'

# 3. Verify public endpoints are accessible
# - https://grafana.titipin.me  (Observability Dashboard)
# - https://mlops.titipin.me    (Streamlit Control Plane)
# - https://minio.titipin.me    (MinIO Web Console)
# - https://mlflow.titipin.me   (MLflow Model Registry)
```

---

## 3. Split-Screen Layout for Live Verification

For clear visual verification during demonstrations, arrange terminal and browser windows in a 3-panel split layout:

```text
┌─────────────────────────┬─────────────────────────┬─────────────────────────┐
│       PANEL 1           │        PANEL 2          │        PANEL 3          │
│  Traffic Generator      │  Grafana Live Dashboard │  K8s Pod Watcher        │
│                         │                         │                         │
│  make demo-spike        │  https://               │  kubectl get pods       │
│  (k6 workload spike)    │  grafana.titipin.me     │  -n titipin -w          │
└─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

---

## 4. Demonstration Walkthrough Steps

### Phase 1: Baseline State Inspection (Initial Equilibrium)
```bash
# Verify initial steady-state replica count (1 replica)
kubectl get pods -n titipin -l app=laravel-backend

# Query active scaler recommendation
curl -s http://16.79.90.160:30800/predict | jq .
```
- **Expected Outcome:** `target_rps_per_pod = 10.0`, `recommended_replicas = 1`.

### Phase 2: Traffic Spike Injection (k6 Workload Generator)
```bash
# Trigger automated progressive spike scenario (30 -> 60 -> 120 -> 200 Virtual Users)
make demo-spike
```
- **What to Observe in Grafana (`https://grafana.titipin.me`):**
  1. The **blue curve** (`Predicted RPS t+60s`) begins ascending immediately upon detecting early lag-1 telemetry acceleration.
  2. The **green curve** (`Pod Replicas`) scales out proactively from 1 to 2, then 3 pods.
  3. The scaling action occurs **~30–45 seconds BEFORE** the **red curve** (`Actual Request Rate`) reaches its peak.
  4. Response latency ($p95$) remains strictly below the 200ms SLO threshold throughout the surge.

### Phase 3: Traffic Normalization & Cooldown Enforcement
After the spike scenario completes, the workload returns to baseline ($VU=30$):
- **Expected Outcome:** The scaler enters a 60-second cooldown period, preventing flapping, before smoothly scaling back down to minimum replicas (`min_replicas=1`).

---

## 5. Automated Interactive Walkthrough Script

An automated, interactive demonstration script is provided for guided presentations:

```bash
# Start the 5-segment guided verification sequence
make demo-live

# Or run non-interactively in automated test environments
bash scripts/demo_live.sh --no-wait
```

### Demonstration Script Segments:
1. **Segment 1:** Kubernetes cluster topology & running pod status.
2. **Segment 2:** MLflow Model Registry audit (inspecting `@champion` and `@challenger` tags).
3. **Segment 3:** Prometheus metrics scraping & Grafana dashboard verification.
4. **Segment 4:** Real-time k6 traffic spike simulation & anticipatory scaling proof.
5. **Segment 5:** AI Governance, Container Security (Trivy), and Explainability (SHAP).

---

## 6. End-to-End System Architecture Reference

| Subsystem | Technology Stack | Operational Responsibility |
|:---|:---|:---|
| **Telemetry Ingestion** | Prometheus, Python 3.12, Pandas | Collects edge HTTP request rate, CPU usage, and latency. |
| **Data Versioning** | DVC, MinIO S3 Remote | Immutable dataset tracking, data lineage, and version tagging. |
| **Model Development** | Scikit-Learn, LightGBM, MLflow | Training multi-step time-series forecasting models with automated gates. |
| **Model Registry** | MLflow Model Registry | Champion/Challenger deployment strategy (`@champion` promotion gate). |
| **CI/CD Pipeline** | GitHub Actions | 4-stage automated gate: Linting, Data Quality, Model Quality, Container Tests. |
| **Microservices Stack** | Docker Compose | Local reproducible environment orchestrating 4 core containers. |
| **Serving & Autoscaling** | FastAPI, Kubernetes K3s | Microservice serving predictions and custom autoscaling controller. |
| **Observability** | Prometheus, Grafana | Custom ServiceMonitor, PrometheusRule alerting, and real-time dashboard. |
| **Continuous Training** | Kubernetes CronJob, PSI / KS-Test | Automated drift detection and challenger retraining pipeline. |
| **Governance & Security** | Aqua Security Trivy, SHAP | Container vulnerability scanning, secret detection, and model explainability. |

---

## 7. Troubleshooting & Operational Commands

```bash
# Stream predictive scaler controller logs
kubectl logs -n mlops deploy/mlops-inference -c predictive-scaler -f

# Inspect active Prometheus exporter metrics directly
curl -s http://16.79.90.160:30902/metrics | grep autoscaler_

# Trigger an immediate single inference cycle for sanity checking
kubectl exec -n mlops deploy/mlops-inference -c predictive-scaler -- \
  python3 -c "from src.scaling.predictive_scaler import PredictiveScaler; s=PredictiveScaler(); s.run_once()"
```
