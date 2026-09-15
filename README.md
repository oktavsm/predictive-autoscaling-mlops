# Predictive Autoscaling MLOps

> A production-oriented MLOps system for forecasting application workload and enabling proactive autoscaling in Kubernetes.

## Overview

This project explores the use of Machine Learning and MLOps practices to build a predictive autoscaling system for a containerized application.

The system uses an existing semi-e-commerce application for Jastip (personal shopping service) and preloved goods as the experimental workload. The application provides both a React web client and an Android client built with Kotlin and Jetpack Compose, both of which consume the same Laravel backend API.

Instead of relying on static datasets, the project continuously collects operational metrics from the running application and Kubernetes environment. These metrics are used to build a time-series dataset for workload forecasting.

The predicted workload can then be used to support proactive scaling decisions before the system reaches a critical resource or performance condition.

The project focuses not only on the Machine Learning model, but on the complete operational lifecycle of the model:

```text
Data Collection → Data Validation → Dataset Versioning → Model Training
→ Model Evaluation → Model Registry → Model Serving → Inference
→ Predictive Scaling → Monitoring → Drift / Performance Detection
→ Continuous Training → Training
```

## Project Motivation

Traditional reactive autoscaling responds to workload changes after a resource threshold has already been reached. This project investigates whether workload forecasting can provide useful information for proactive scaling.

The main goal is not to develop a novel Machine Learning algorithm, but to investigate how a Machine Learning model can be operationalized reliably as part of a cloud-native system.

## Application Workload

The experimental workload is an existing semi-e-commerce application for Jastip and preloved goods, including listing search/creation and offer-related activities.

| Component | Technology |
|---|---|
| Web Client | React |
| Android Client | Kotlin + Jetpack Compose |
| Backend | PHP Laravel |
| Database | Existing application database |

Both web and Android clients communicate with the same Laravel backend. For controlled experiments, workload can be generated directly against the backend API using load-testing scenarios; the frontend applications do not need to run inside the experimental Kubernetes cluster.

## High-Level Architecture

```text
React Web / Android App
          ↓
    Laravel Backend
          ↓
      Kubernetes
      ↙        ↘
 Worker 1    Worker 2
      ↘        ↙
      Prometheus
       ↙     ↘
     Data   Grafana
      ↓
      DVC
      ↓
 Model Training
      ↓
    MLflow
      ↓
 Inference API
      ↓
 Scaling Policy
      ↓
 Kubernetes
```

## Experimental Infrastructure

The initial experiment is planned to use three laboratory VMs.

| Node | Role | Initial Resources |
|---|---|---|
| VM-01 | Kubernetes Control Plane + Monitoring/MLOps | 2 vCPU / 4 GB RAM / 30–50 GB |
| VM-02 | Kubernetes Worker | 1 vCPU / 1 GB RAM / 12 GB |
| VM-03 | Kubernetes Worker | 1 vCPU / 1 GB RAM / 12 GB |

The worker nodes intentionally use constrained resources to make workload and scaling behavior more observable. Resources may be increased if Kubernetes system components or application workloads become constrained by the infrastructure itself.

## Data Pipeline

Operational metrics will be collected from the application and Kubernetes environment using Prometheus. Initial candidate metrics include request rate, CPU utilization, memory utilization, response latency, replica count, and relevant network metrics.

```text
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
Validation
        ↓
Versioned Dataset
```

The final ML features and prediction target will be determined after exploratory data analysis of the collected workload data.

## Machine Learning Task

**Time-Series Forecasting / Regression**

The model will use historical and current workload metrics to predict future workload or resource demand.

Potential targets include:
- Future request rate
- Future CPU utilization
- Future workload/resource demand

The final target is intentionally not fixed yet and will be selected based on the real dataset.

### Evaluation Metrics

Model metrics:
- MAE
- RMSE
- MAPE

System and operational metrics may include:
- Inference latency
- Response latency
- CPU utilization
- Memory utilization
- Replica count
- Scaling responsiveness
- Resource efficiency
- Reliability
- Overload/SLO violations

## Workload Scenarios

Controlled workload generation will be used for reproducible experiments.

1. **Steady** — stable request rate
2. **Gradual Increase** — progressively increasing traffic
3. **Spike** — sudden workload increase
4. **Periodic** — repeating workload pattern
5. **Bursty** — short, irregular workload spikes

These scenarios will be used to evaluate model behavior and autoscaling response under different workload characteristics.

## Data Drift

Workload characteristics may change over time. Potential causes include increased traffic, different request patterns, application changes, resource configuration changes, time-dependent usage patterns, and previously unseen workload patterns.

Data drift and prediction performance will therefore be monitored as part of the Continuous Training lifecycle.

## Continuous Training

The project uses a combination of scheduled and condition-based retraining.

### Scheduled Trigger

The system periodically checks whether enough new validated data has accumulated.

### Condition-Based Trigger

Retraining may be triggered when data drift exceeds a defined threshold, prediction error increases, or model performance degrades on recent data.

```text
New Production Data
        ↓
Data Validation
        ↓
Dataset Update
        ↓
Drift / Performance Check
        ↓
Training Trigger
        ↓
Retraining
        ↓
Candidate Model
        ↓
Evaluation
     ↙       ↘
 Promote   Reject
    ↓          ↓
Production  Keep Existing
   Model     Production Model
```

A candidate model must pass evaluation before becoming the new production model.

## MLOps Technology Stack

| Area | Technology |
|---|---|
| Containerization | Docker |
| Orchestration | Kubernetes |
| Monitoring | Prometheus |
| Visualization | Grafana |
| Dataset Versioning | DVC |
| Experiment Tracking | MLflow |
| Model Registry | MLflow |
| Model Serving | FastAPI |
| CI/CD | GitHub Actions |
| ML | Python |
| Infrastructure | Laboratory VMs |

The stack may evolve during implementation based on technical constraints and experimental requirements.

## Repository Structure

The repository is dedicated to the predictive autoscaling MLOps system, organized following industry best practices (similar to Cookiecutter Data Science and Cloud-Native MLOps patterns).

```text
predictive-autoscaling-mlops/
├── .devcontainer/              # Reproducible GitHub Codespaces environment
├── .github/workflows/          # CI/CD pipelines (testing, linting, automation)
├── api/                        # Model Serving & Inference REST API (FastAPI)
├── configs/                    # System, exporter, and Grafana dashboard configurations
├── data/                       # DVC-managed data directory (raw, interim, processed)
├── docs/                       # Technical architecture, setup guides, and LK course reports
├── infrastructure/             # Infrastructure-as-Code (Kubernetes, Docker, Monitoring)
│   ├── demo/                   # Demo compose setup (e.g. Titipin Frontend on port 3000)
│   ├── docker/                 # Production & development Dockerfiles / compose files
│   ├── kubernetes/             # K3s manifests (Deployments, Services, Ingress, HPA)
│   └── monitoring/             # Prometheus rules, ServiceMonitors, Alertmanager
├── notebooks/                  # Jupyter notebooks for interactive EDA & modeling experiments
├── pipelines/                  # Automated pipeline stage definitions
│   ├── ingestion/              # Telemetry extraction & sync pipelines
│   ├── training/               # Model training and MLflow experiment logging pipelines
│   └── retraining/             # Continuous Training (CT) and drift evaluation pipelines
├── scripts/                    # Operational utility scripts & load testing runners
├── src/                        # Core application source code
│   ├── data/                   # Ingestion logic, dataset validation, and data loaders
│   ├── features/               # Feature engineering (lag features, rolling stats, deltas)
│   ├── models/                 # Model definitions, training logic, and baseline predictors
│   ├── inference/              # Inference engine and MLflow Model Registry integration
│   └── scaling/                # Predictive autoscaling policy and replica decision logic
├── tests/                      # Automated quality gates and unit tests (pytest)
└── workloads/                  # Synthetic workload generation scenarios (k6 scripts)
```

### Directory Breakdown & Explanations

| Direktori / Subdirektori | Deskripsi & Fungsi |
|---|---|
| **`.devcontainer/`** | **Lingkungan Pengembangan Reproducible:** Berisi konfigurasi `devcontainer.json` untuk GitHub Codespaces (Python 3.12, ekstensi VS Code, port forwarding 3000/8000/8501) agar lingkungan kerja seragam bagi siapapun yang membuka repositori. |
| **`.github/workflows/`** | **CI/CD Automation:** Pipeline GitHub Actions untuk menjalankan automated testing (`pytest`), linting (`ruff`), serta integrasi pemicu otomatis (*code-as-a-trigger*) pada siklus MLOps (LK-08). |
| **`api/`** | **Model Serving REST API:** Layanan inferensi berbasis FastAPI yang menyajikan endpoint prediksi (`/predict`), pemeriksaan kesehatan (`/health`), dan metrik internal (`/metrics`) untuk dikonsumsi oleh autoscaler atau sistem eksternal. |
| **`configs/`** | **Konfigurasi Sistem:** Menyimpan file konfigurasi deklaratif, seperti template dashboard Grafana (`grafana-demo-dashboard.json`), konfigurasi parameter Prometheus exporter, ambang batas HPA, dan hyperparameter pemodelan. |
| **`data/`** | **Data Versioning (DVC):** Direktori penyimpanan dataset yang dilacak menggunakan DVC (Data Version Control) dan dihubungkan ke MinIO S3 (`storage.titipin.me`):<br>• `data/raw/`: Partisi data mentah telemetri dari Prometheus (bersifat *immutable*).<br>• `data/interim/`: Data intermediate yang telah dibersihkan, diurutkan secara monotonik, dan diselaraskan ke grid waktu 15 detik.<br>• `data/processed/`: Matriks fitur final siap latih (*training-ready*) lengkap dengan fitur lag, rolling window, dan target horizon $t+60\text{s}$. |
| **`docs/`** | **Dokumentasi & Laporan Perkuliahan:** Dokumentasi arsitektur sistem (`ARCHITECTURE.md`, `DATA_PIPELINE_DESIGN.md`), panduan setup (`SETUP_GUIDE.md`, `CODESPACE_SETUP.md`), strategi deployment (`ENVIRONMENT_AND_DEPLOYMENT_STRATEGY.md`), roadmap proyek (`ROADMAP_LK.md`), serta laporan resmi perancangan lembar kerja (seperti `LK-03_DATA_PIPELINE_ARCHITECTURE.md`). |
| **`infrastructure/`** | **Infrastructure-as-Code (IaC) & Runtime Orkestrasi:**<br>• `infrastructure/kubernetes/`: Manifest Kubernetes K3s (Deployment Laravel, StatefulSet PostgreSQL/Redis/MinIO, Service, Ingress Caddy, dan konfigurasi HPA reaktif).<br>• `infrastructure/docker/`: Dockerfile dan file Docker Compose untuk pembangunan kontainer layanan.<br>• `infrastructure/monitoring/`: Konfigurasi *observability stack* (Prometheus, Grafana, Alertmanager).<br>• `infrastructure/demo/`: File compose khusus untuk menjalankan demo aplikasi Web Frontend Titipin di port 3000. |
| **`notebooks/`** | **Eksplorasi & Analisis Data Interaktif:** Menyimpan Jupyter Notebooks untuk analisis eksploratif data (EDA), visualisasi distribusi, pengukuran *scaling lag* HPA (~45 detik), pembuktian horizon prediksi 60 detik, dan eksperimen awal (`01_initial_eda.ipynb`). |
| **`pipelines/`** | **Definisi Alur Kerja Otomatis (DVC Pipelines):**<br>• `pipelines/ingestion/`: Alur penarikan data telemetri berkala dari Prometheus API.<br>• `pipelines/training/`: Alur pelatihan model otomatis dan pencatatan eksperimen ke MLflow.<br>• `pipelines/retraining/`: Alur evaluasi performa model baru vs model produksi dan pemicu *Continuous Training* (CT) saat terjadi data drift. |
| **`scripts/`** | **Skrip Utilitas & Operasional:** Kumpulan skrip CLI otomasi pendukung, seperti penarikan metrik Prometheus (`export_dataset.py`), penggabungan partisi dataset (`merge_datasets.py`), dan runner sekuens skenario pengujian beban (`run_workload_sequence.sh`). |
| **`src/`** | **Source Code Inti Aplikasi MLOps:**<br>• `src/data/`: Modul logika penarikan data, validasi skema, pembersihan, dan data loader (`demo_metrics.csv` sebagai sampel data terverifikasi).<br>• `src/features/`: Modul *feature engineering* untuk mengekstrak fitur lag ($t-1$, $t-2$), *rolling mean/std*, diferensial ($\Delta\text{RPS}$, $\Delta\text{CPU}$), dan komponen waktu.<br>• `src/models/`: Kode pelatihan model Machine Learning, algoritma baseline (*persistence*, *rolling mean*), dan fungsi evaluasi metrik (MAE, RMSE, MAPE).<br>• `src/inference/`: Mesin pemuatan model produksi dari MLflow Model Registry dan eksekusi prediksi *real-time*.<br>• `src/scaling/`: Kebijakan *predictive autoscaling* yang menerjemahkan hasil peramalan trafik menjadi rekomendasi jumlah replika pod Kubernetes. |
| **`tests/`** | **Quality Gates & Automated Testing:** Pengujian otomatis menggunakan `pytest` untuk memvalidasi integritas dataset (`test_dataset.py`: 8 smoke tests), fungsi transformasi fitur, dan stabilitas endpoint API sebelum kode diizinkan di-merge ke branch utama. |
| **`workloads/`** | **Generasi Beban Terkontrol (Workload Scenarios):** Definisi skrip pengujian beban menggunakan Grafana k6 (`workloads/k6/`), mencakup skenario *steady*, *spike*, *periodic*, *gradual ramp-up*, *bursty*, hingga simulasi *data drift*. |

## Development and Deployment Workflow

Development is performed locally, while GitHub is used for source control and CI/CD.

```text
Local Development
       ↓
Git Commit / Push
       ↓
GitHub Repository
       ↓
GitHub Actions
       ↓
Test / Build
       ↓
Docker Image
       ↓
Deployment
       ↓
Laboratory VM
       ↓
Kubernetes
```

GitHub Codespaces is not considered a production runtime environment. If required by a course assignment, it can be used as an additional development environment while the experimental deployment remains on laboratory infrastructure.

## Project Goals

1. Build a reproducible MLOps pipeline for a real application workload.
2. Collect continuously growing operational data.
3. Build a workload forecasting model.
4. Deploy the model as an inference service.
5. Monitor both infrastructure and model behavior.
6. Implement model and dataset versioning.
7. Implement Continuous Training.
8. Explore predictive autoscaling in Kubernetes.
9. Compare predictive autoscaling with reactive autoscaling.
10. Evaluate the system from both ML and operational perspectives.

## Project Scope

### In Scope

- Dynamic metrics collection
- Time-series dataset creation
- Machine Learning forecasting
- Docker
- Kubernetes
- Prometheus
- Grafana
- DVC
- MLflow
- Inference API
- Continuous Training
- Predictive scaling prototype
- Predictive vs reactive evaluation

### Out of Scope for Initial Implementation

- Developing a novel ML algorithm
- Rebuilding the existing application
- Autoscaling the database
- Automatically scaling the laboratory VMs
- Full production-grade cloud infrastructure
- Assuming predictive autoscaling is superior without experimental evidence

## Current Decisions

| Decision | Status |
|---|---|
| Existing application as workload | Decided |
| Laravel backend as primary scaling target | Decided |
| React/Android as workload sources | Decided |
| Kubernetes | Decided |
| Three lab VMs | Decided |
| Prometheus | Decided |
| ML task: forecasting/regression | Decided |
| Continuous Training | Decided |
| Exact prediction target | Open |
| Prediction horizon | Open |
| Final ML model | Open |
| Drift detection method | Open |
| Scaling policy | Open |

Open decisions should be resolved based on collected data and experiments rather than assumptions.

## Development with GitHub Codespaces

GitHub Codespaces provides the reproducible development environment for this project (EDA, testing, local API previews). Production-experiment services run on the VPS/K3s cluster; a Codespace is development-only and not used as a persistent runtime.

1. Open this repository on GitHub.
2. Select **Code → Codespaces → Create codespace on `feat/initial-eda`** (or `main`).
3. Wait for the `postCreateCommand` dependency installation to finish.
4. Validate the environment:

   ```bash
   python --version       # Python 3.12.x
   python -m pip check    # No broken requirements
   pytest -q              # 8 smoke tests passed
   ruff check .           # All checks passed
   ```

5. Open `notebooks/01_initial_eda.ipynb`, select the Python 3.12 kernel, and run all cells against the committed sample dataset (`src/data/demo_metrics.csv`).

Use **GitHub Flow** for all changes:

```bash
git switch -c feat/<short-name>
git push -u origin feat/<short-name>
```

Open a pull request, validate the result, and merge it into `main`. The required initial EDA branch is `feat/initial-eda`.

> **Security:** Do not commit `.env` files, tokens, kubeconfigs, datasets managed by DVC, or generated model artifacts.

For detailed setup instructions, see:
- [`docs/CODESPACE_SETUP.md`](docs/CODESPACE_SETUP.md) — Step-by-step Codespaces setup and validation guide
- [`docs/ENVIRONMENT_AND_DEPLOYMENT_STRATEGY.md`](docs/ENVIRONMENT_AND_DEPLOYMENT_STRATEGY.md) — Full environment boundaries and deployment strategy

## Documentation

- `docs/PROJECT_CONTEXT.md` — project context, goals, scope, and MLOps principles
- `docs/ARCHITECTURE.md` — infrastructure and system architecture
- `docs/ROADMAP.md` — implementation roadmap and milestones
- `docs/DECISIONS.md` — architectural and technical decision log
- `docs/SETUP_GUIDE.md` — comprehensive infrastructure setup guide (K3s, backend, monitoring, k6)
- `docs/WORKLOAD_GENERATION.md` — workload generation methodology and scenarios
- `docs/CODESPACE_SETUP.md` — GitHub Codespaces development setup guide
- `docs/ENVIRONMENT_AND_DEPLOYMENT_STRATEGY.md` — environment strategy and target VPS deployment

## Academic Context

This project is developed as part of the **Machine Learning Operations (MLOps)** course and is designed around Machine Learning lifecycle management, dynamic data, CI/CD, model versioning, model deployment, monitoring, data drift, Continuous Training, and production-oriented Machine Learning systems.

## Status

**Current phase:** Phase 2/3 — Data Collection & Exploratory Data Analysis (EDA).

Completed milestones:
- [x] K3s multi-node cluster deployed on AWS (Control Plane + 2 Workers).
- [x] Laravel backend deployed as Kubernetes pods with reactive HPA.
- [x] Prometheus and Grafana operational (`api.titipin.me`, `grafana.titipin.me`).
- [x] k6 automated workload scenarios calibrated and executed (steady, spike, periodic, gradual).
- [x] Telemetry dataset collected, merged, and deduplicated (284 observations).
- [x] Reproducible Codespaces devcontainer configured and tested (`feat/initial-eda`).
- [x] Initial exploratory data analysis (`notebooks/01_initial_eda.ipynb`) executed and validated.

Immediate priorities:
1. Open and merge PR for `feat/initial-eda` into `main`.
2. Phase 2: Initialize DVC and configure remote storage (MinIO).
3. Phase 4: Build baseline models (persistence and moving average).
4. Phase 5: Deploy MLflow tracking server on K3s.
