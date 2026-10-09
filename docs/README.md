# 📚 Predictive Autoscaling MLOps — Documentation Index

> **Pusat Dokumentasi Teknis, Arsitektur, Panduan Operasional, dan Laporan Praktikum**  
> Proyek: *Predictive Horizontal Pod Autoscaler (HPA) menggunakan MLOps pada Arsitektur Multi-Node Kubernetes (K3s)*

---

## 📌 Peta Navigasi Dokumentasi (5 Pilar MLOps)

Seluruh dokumen teknis pada direktori `docs/` dikelompokkan secara terstruktur ke dalam 5 pilar utama untuk memudahkan navigasi pengembang, operator, dan penguji sistem:

```text
docs/
├── 1. Arsitektur & Desain Sistem        (ARCHITECTURE, DECISIONS, ROADMAP, ENVIRONMENT)
├── 2. Data Engineering & DVC            (DATA_PIPELINE, INGESTION, DVC_MINIO)
├── 3. Machine Learning & Model Ops      (MODELING, EXPERIMENT_MLFLOW, MODEL_REGISTRY, RETRAINING)
├── 4. Platform, Infrastruktur & Scaling (KUBERNETES, SETUP_GUIDE, BENCHMARK, REMOTE_VM)
└── 5. Observabilitas, FinOps & AI Trust (OBSERVABILITY, ALERTING, FINOPS, ETHICS, DASHBOARD)
```

---

### 1. Arsitektur & Fondasi Sistem

| Dokumen | Deskripsi & Cakupan Teknis |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Blueprint arsitektur end-to-end, interaksi antar komponen (Prometheus ➔ Ingestion ➔ MLflow ➔ Inference ➔ K8s HPA), dan diagram alur penskalaan proaktif. |
| [`DECISIONS.md`](DECISIONS.md) | *Architecture Decision Records (ADR)*: Pemilihan horizon 60s, alasan Optuna LightGBM vs persistence, strategi zero-downtime hot-reload, dan trade-off desain. |
| [`ROADMAP.md`](ROADMAP.md) | Peta jalan pengembangan dari fase inisiasi hingga kesiapan produksi penuh (Fase 1 s/d Fase 14). |
| [`ENVIRONMENT_AND_DEPLOYMENT_STRATEGY.md`](ENVIRONMENT_AND_DEPLOYMENT_STRATEGY.md) | Standar lingkungan pengembangan, hierarki konfigurasi (`.env`), dan strategi isolasi namespace cluster. |
| [`DOKUMENTASI_ARSITEKTUR_DAN_PERBAIKAN_SISTEM.md`](DOKUMENTASI_ARSITEKTUR_DAN_PERBAIKAN_SISTEM.md) | Rekapitulasi perbaikan teknis sistem, stabilisasi pipeline, integrasi event-driven, dan audit bug fix. |

---

### 2. Data Engineering & Data Versioning (DVC)

| Dokumen | Deskripsi & Cakupan Teknis |
|---|---|
| [`DATA_PIPELINE.md`](DATA_PIPELINE.md) | Spesifikasi pipeline telemetri Prometheus, interval scraping 15s, formula agregasi CPU/RPS/Latency, dan matriks fitur. |
| [`DATA_INGESTION_AND_PREPROCESSING.md`](DATA_INGESTION_AND_PREPROCESSING.md) | Panduan mendalam implementasi modul `src/ingest_data.py` dan `src/preprocess.py`, penanganan missing value, dan sanitasi data. |
| [`DATA_VERSIONING_DVC.md`](DATA_VERSIONING_DVC.md) | Integrasi Data Version Control (DVC), pelacakan hash MD5 pointer,Content-Addressable Storage (CAS), dan simulasi continual learning. |
| [`PANDUAN_DVC_DAN_MINIO_STORAGE.md`](PANDUAN_DVC_DAN_MINIO_STORAGE.md) | Panduan teknis konfigurasi remote storage MinIO S3 (`storage.titipin.me/mlops-dvc`), audit silsilah data, dan *data time-travel*. |

---

### 3. Machine Learning & Model Lifecycle (MLflow)

| Dokumen | Deskripsi & Cakupan Teknis |
|---|---|
| [`MODELING.md`](MODELING.md) | Formulasi problem regresi deret waktu, rekayasa fitur lag ($t-15\text{s}$, $t-30\text{s}$), rolling window, dan target horizon $t+60\text{s}$. |
| [`EXPERIMENT_TRACKING_MLFLOW.md`](EXPERIMENT_TRACKING_MLFLOW.md) | Pelacakan eksperimen pada server MLflow (`mlflow.titipin.me`), perbandingan metrik validasi (MAE, RMSE, $R^2$), dan hyperparameter Optuna. |
| [`MODEL_REGISTRY.md`](MODEL_REGISTRY.md) | Tata kelola lifecycle model: *Staging*, *Production*, aliases (`@champion`, `@challenger`), dan verifikasi artefak model terdaftar. |
| [`CONTINUOUS_TRAINING_AND_DRIFT.md`](CONTINUOUS_TRAINING_AND_DRIFT.md) | Arsitektur Continuous Training (CT) otomatis via Kubernetes CronJob dan deteksi Population Stability Index (PSI). |
| [`AUTONOMOUS_DRIFT_RETRAINING.md`](AUTONOMOUS_DRIFT_RETRAINING.md) | Mekanisme *Closed-Loop Autonomous Drift*: deteksi drift ➔ injeksi data ➔ penarikan telemetri ➔ re-training ➔ evaluasi gate ➔ hot reload. |

---

### 4. Platform, Infrastruktur & Autoscaling

| Dokumen | Deskripsi & Cakupan Teknis |
|---|---|
| [`KUBERNETES_PREDICTIVE_AUTOSCALING.md`](KUBERNETES_PREDICTIVE_AUTOSCALING.md) | Cara kerja kontroler autoscaler proaktif, algoritma sizing replika pod, mitigasi reactive scaling lag, dan cooldown policy. |
| [`BENCHMARK_HPA_VS_PREDICTIVE.md`](BENCHMARK_HPA_VS_PREDICTIVE.md) | Analisis uji komparatif empiris: Kubernetes Reactive HPA vs Predictive Autoscaler di bawah beban *flash-sale traffic spike*. |
| [`SETUP_GUIDE.md`](SETUP_GUIDE.md) | Panduan langkah demi langkah *bootstraping* klaster multi-node K3s, instalasi komponen backend Laravel, database, dan ingress. |
| [`INFRASTRUCTURE_SETUP.md`](INFRASTRUCTURE_SETUP.md) | Detail provisioning VM, network overlay Flannel, node tokens, dan konfigurasi firewall/port klaster. |
| [`DOCKER_COMPOSE_ORCHESTRATION.md`](DOCKER_COMPOSE_ORCHESTRATION.md) | Panduan orkestrasi lokal Docker Compose untuk stack MLOps (MinIO, MLflow, Inference, Dashboard, Prometheus). |
| [`REMOTE_VM_AUTOMATION.md`](REMOTE_VM_AUTOMATION.md) | Dokumentasi otomatisasi VM worker (`cp-bcc`), systemd daemon traffic generator, sinkronisasi DVC in-cluster, dan SSH tunnels. |
| [`CLOUDFLARE_DOMAIN_SETUP.md`](CLOUDFLARE_DOMAIN_SETUP.md) | Konfigurasi DNS Cloudflare, SSL/TLS full strict, dan reverse proxy Caddy untuk domain publik (`titipin.me`). |
| [`CODESPACE_SETUP.md`](CODESPACE_SETUP.md) | Panduan lingkungan pengembangan berbasis cloud GitHub Codespaces dengan pre-installed k6, kubectl, dan devcontainer. |

---

### 5. Observabilitas, FinOps & AI Governance

| Dokumen | Deskripsi & Cakupan Teknis |
|---|---|
| [`OBSERVABILITY_PROMETHEUS_GRAFANA.md`](OBSERVABILITY_PROMETHEUS_GRAFANA.md) | Arsitektur pemantauan klaster: Prometheus Operator, ServiceMonitor, scraping endpoints, dan dashboard Grafana (`grafana.titipin.me`). |
| [`ALERTING_DAN_INCIDENT_MANAGEMENT.md`](ALERTING_DAN_INCIDENT_MANAGEMENT.md) | Dispatcher notifikasi insiden otomatis ke Discord dan Telegram untuk anomali drift, kegagalan inferensi, dan lonjakan beban. |
| [`FINOPS_DAN_COST_EFFICIENCY.md`](FINOPS_DAN_COST_EFFICIENCY.md) | Model efisiensi biaya komputasi awan, kalkulasi penghematan vCPU hours, dan analisis reduksi emisi karbon (*Green AI*). |
| [`GOVERNANCE_SECURITY_AND_ETHICS.md`](GOVERNANCE_SECURITY_AND_ETHICS.md) | Tata kelola AI/ML, audit kerentanan kontainer (Trivy), model card, privasi data pengguna, dan etika model proaktif. |
| [`PANDUAN_AUDIT_LOG_DAN_TELEMETRI_OPERASIONAL.md`](PANDUAN_AUDIT_LOG_DAN_TELEMETRI_OPERASIONAL.md) | Penjelasan ring buffer audit telemetri operasional, format log penskalaan, dan endpoint `/operations/audit`. |
| [`PANDUAN_SIMULASI_DAN_TUNING_PARAMETER.md`](PANDUAN_SIMULASI_DAN_TUNING_PARAMETER.md) | Panduan tuning parameter autoscaling: target RPS per pod, min/max pod bounds, threshold PSI drift, dan bobot optimasi. |
| [`DOKUMENTASI_LENGKAP_STREAMLIT_DASHBOARD.md`](DOKUMENTASI_LENGKAP_STREAMLIT_DASHBOARD.md) | Panduan komprehensif seluruh tab pada Streamlit Dashboard (`mlops.titipin.me`) dan operasi di balik layar. |
| [`LIVE_DEMO_GUIDE.md`](LIVE_DEMO_GUIDE.md) | Runbook skenario demonstrasi interaktif untuk pengujian langsung fungsionalitas inferensi dan autoscaling. |
| [`WORKLOAD_GENERATION.md`](WORKLOAD_GENERATION.md) | Katalog skenario uji beban k6: Steady, Gradual, Periodic, Spike, dan Bursty. |
| [`CICD_AUTOMATION.md`](CICD_AUTOMATION.md) | Detail pipeline automasi GitHub Actions untuk linting, data quality checks, packaging, dan image publishing. |
| [`CICD_DESIGN.md`](CICD_DESIGN.md) | Desain arsitektur integrasi berkelanjutan (CI), pengiriman berkelanjutan (CD), dan pelatihan berkelanjutan (CT). |

---

## 📂 Sub-Direktori Khusus di `docs/`

1. **[`coursework/`](coursework/)**:
   Berisi seluruh laporan praktikum Lembar Kerja mahasiswa (LK-01 hingga LK-14) yang disusun sesuai format rubrik akademik dan tugas perkuliahan.
2. **[`images/`](images/)**:
   Aset grafis, diagram arsitektur mermaid hasil render, tangkapan layar Grafana, perbandingan grafik HPA, dan ilustrasi visual.
3. **[`internal/`](internal/)**:
   Catatan teknis internal pengembang, riwayat setup VM, panduan pembagian kerja (*work division*), kamus struktur proyek (`PROJECT_FILE_DICTIONARY.md`), dan laporan audit direktori (`AUDIT_STRUKTUR_DIREKTORI.md`).
