# Project Roadmap — Predictive Autoscaling MLOps
## Aligned with LK CIF60050 (Universitas Brawijaya)

> **Repo:** `oktavsm/predictive-autoscaling-mlops`
> **Dosen:** Rizal Setya Perdana, Ph.D. & Drs. Muh. Arif Rahman, M.Kom.
> **Last updated:** September 2026

---

## Status Legend

| Symbol | Status |
|--------|--------|
| ✅ | Selesai & ter-commit di `main` |
| 🔄 | In progress / sebagian selesai |
| ⬜ | Belum dikerjakan |
| 📄 | Luaran berupa dokumen/PDF (non-coding) |

---

## Overview Timeline

```
Pekan  1  — LK-01 ✅  Proposal & definisi masalah (PDF)
Pekan  2  — LK-02 ✅  GitHub repo, Codespaces, branching, README
Pekan  3  — LK-03 ⬜  Data pipeline architecture plan (PDF + diagram)
Pekan  4  — LK-04 🔄  Data ingestion scripts + preprocessing automation
Pekan  5  — LK-05 ⬜  DVC setup + data versioning + MinIO remote
Pekan  6  — LK-06 ⬜  MLflow experiment tracking + model training
Pekan  7  — LK-07 ⬜  MLflow Model Registry + model lifecycle management
Pekan  8  ─── UTS ────────────────────────────────────────────────────
Pekan  9  — LK-08 ⬜  GitHub Actions CI/CD pipeline (code-as-trigger)
Pekan 10  — LK-09 ⬜  Docker Compose multi-service orchestration
Pekan 11  — LK-10 ⬜  Kubernetes deployment (K8s manifests + Helm)
Pekan 12  — LK-11 ⬜  Monitoring & observability (Prometheus + Grafana)
Pekan 13  — LK-12 ⬜  Continuous Training pipeline (automated retraining)
Pekan 14  — LK-13 ⬜  Governance audit (XAI/SHAP, security, ethics)
Pekan 15  — LK-14 ⬜  Final presentation + live demo
```

---

## Phase 0 — Infrastructure & App (DONE) ✅

> *Ini adalah fondasi yang sudah kita bangun, bukan bagian LK secara langsung tapi menjadi infrastruktur nyata sebagai pengganti dataset statis.*

| Komponen | Status | Detail |
|---|---|---|
| K3s multi-node cluster (3 AWS VMs) | ✅ | CP: `16.79.90.160`, W1: `15.232.116.101`, W2: `15.232.71.54` |
| Laravel backend di Kubernetes | ✅ | Nginx + PHP-FPM sidecar, NodePort 30080 |
| PostgreSQL, Redis, MinIO sebagai StatefulSet | ✅ | Namespace `titipin` |
| Caddy reverse proxy + SSL | ✅ | `api.titipin.me`, `grafana.titipin.me`, `storage.titipin.me` |
| Prometheus + Grafana (kube-prometheus-stack) | ✅ | Helm, NodePort 30300 |
| Reactive HPA | ✅ | `--cpu-percent=60 --min=1 --max=4` |
| K3s manifests di repo | ✅ | `infrastructure/kubernetes/` |

**Files:** `infrastructure/`, `docs/SETUP_GUIDE.md`, `configs/grafana-demo-dashboard.json`

---

## Phase 1 — LK-01: Project Initiation ✅

> **Pekan 1 | Luaran: PDF proposal**

| Task | Status |
|---|---|
| Definisi masalah & domain (predictive autoscaling) | ✅ |
| Analisis karakteristik data dinamis (time-series metrics) | ✅ |
| Strategi Continual Learning / Continuous Training | ✅ |
| Metrik keberhasilan (MAE, RMSE, p95 latency, SLO violations) | ✅ |
| Diagram arsitektur pipeline end-to-end | ✅ |

**Files:** `docs/PROJECT_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`
**Luaran LK:** `LK01-Nama-NIM.pdf` (proposal dokumen)

---

## Phase 2 — LK-02: GitHub Setup & Codespaces ✅

> **Pekan 2 | Luaran: URL repo + screenshot Codespaces + README**

| Task | Status |
|---|---|
| Repo publik `predictive-autoscaling-mlops` dengan `.gitignore` + MIT License | ✅ |
| `.devcontainer/devcontainer.json` (Python 3.12 + Jupyter + Ruff + Pylance) | ✅ |
| `requirements.txt` dan `requirements-dev.txt` dengan versi exact | ✅ |
| Struktur direktori `data/`, `models/`, `notebooks/`, `src/`, `configs/` | ✅ |
| Branching strategy: `feat/initial-eda` → PR → merge ke `main` | ✅ |
| README dengan instruksi Codespaces dan GitHub Flow | ✅ |
| `tests/test_dataset.py` — 8 smoke tests (8 passed) | ✅ |
| `pyproject.toml` — ruff + pytest config | ✅ |

**Files:** `.devcontainer/`, `requirements*.txt`, `pyproject.toml`, `tests/`, `README.md`

> [!IMPORTANT]
> **Bukti untuk LK-02:** Screenshot Codespaces menunjukkan `python --version` = 3.12.x,
> `pytest -q` = 8 passed, `ruff check .` = All checks passed.

---

## Phase 3 — LK-03: Data Pipeline Architecture Plan ⬜

> **Pekan 3 | Luaran: Dokumen PDF + diagram arsitektur**
> **Tipe: Analisis & Perancangan (non-coding)**

Berdasarkan sistem kita yang sudah berjalan, dokumen LK-03 perlu menjelaskan:

| Task | Status | Keterangan |
|---|---|---|
| Identifikasi sumber data: Prometheus API di VPS K3s | ✅ Ada | Dokumentasikan secara formal |
| Desain ETL pipeline: Prometheus → export → validation → storage | 🔄 | Ada script, belum didokumentasikan sebagai arsitektur formal |
| Diagram arsitektur data flow (Excalidraw/Draw.io) | ⬜ | Perlu dibuat visual diagram |
| Rencana versioning data (persiapan DVC di LK-05) | ⬜ | Formal plan belum ada |
| Skema data awal (kolom, tipe, unit, range) | ✅ Ada | `src/data/demo_metrics.csv` |

**Deliverable untuk dosen:**
- Dokumen PDF yang menjelaskan: sumber data (Prometheus), metrik yang dikumpulkan (5 kolom), interval scraping (15s), flow data, rencana DVC versioning.
- Diagram arsitektur menggunakan [Excalidraw](https://excalidraw.com/) atau Draw.io.
- Screenshot bukti berhasil mengakses/mengambil data (gunakan `src/data/demo_metrics.csv` sebagai buktinya).

**Files yang sudah ada sebagai referensi:** `docs/WORKLOAD_GENERATION.md`, `scripts/export_dataset.py`, `scripts/merge_datasets.py`

---

## Phase 4 — LK-04: Data Ingestion & Preprocessing ✅→⬜

> **Pekan 4 | Luaran: Script Python + laporan PDF**
> **Tipe: Implementasi teknis**

| Task | Status | Keterangan |
|---|---|---|
| Script ingestion otomatis dari Prometheus API | ✅ | `scripts/export_dataset.py` |
| Error handling & retry logic | 🔄 | Basic ada, belum robust |
| Script preprocessing / feature engineering | 🔄 | Ada di notebook, belum di `src/data/` |
| Data validation (null check, range check, duplicate check) | ✅ | `tests/test_dataset.py` |
| Script dapat dijalankan secara berkala (cron-ready) | 🔄 | `scripts/run_workload_sequence.sh` ada, belum scheduled |
| Dokumentasi instruksi eksekusi di README | 🔄 | Perlu diperjelas |

**Yang perlu dikerjakan di branch `feat/lk04-ingestion`:**
```bash
# Buat src/data/ingest.py (clean version dari export_dataset.py)
# Buat src/data/preprocess.py (feature engineering dari notebook)
# Update README dengan cara menjalankan ingestion
```

---

## Phase 5 — LK-05: DVC Data Versioning ⬜

> **Pekan 5 | Luaran: .dvc files + laporan PDF + README update**

| Task | Status |
|---|---|
| `dvc init` di repo | ⬜ |
| Track dataset dengan `dvc add data/raw/` | ⬜ |
| Konfigurasi DVC remote ke MinIO di K3s (`mlops-dvc` bucket) | ⬜ |
| `dvc push` dataset pertama | ⬜ |
| Simulasi continual learning: jalankan ulang ingestion → versi baru data | ⬜ |
| `dvc diff` untuk compare versi data | ⬜ |
| Update README dengan alur penambahan versi data | ⬜ |

**Config yang dibutuhkan:**
```bash
dvc remote add -d minio s3://mlops-dvc
dvc remote modify minio endpointurl http://storage.titipin.me
dvc remote modify minio access_key_id <MINIO_ACCESS_KEY>
dvc remote modify minio secret_access_key <MINIO_SECRET_KEY>
```

> [!NOTE]
> MinIO bucket `mlops-dvc` perlu dibuat dulu di `storage.titipin.me`. Bucket `titipin-app` sudah ada untuk app, buat bucket baru khusus MLOps.

---

## Phase 6 — LK-06: MLflow Experiment Tracking & Model Training ⬜

> **Pekan 6 | Luaran: `train.py` + laporan PDF dengan screenshot MLflow UI**

| Task | Status |
|---|---|
| Deploy MLflow tracking server di K3s (Helm chart atau manifest) | ⬜ |
| Buat `src/models/train.py` dengan integrasi MLflow | ⬜ |
| Baseline 1: Persistence model (last-value) | ⬜ |
| Baseline 2: Rolling mean (60s window) | ⬜ |
| Kandidat model: Linear Regression | ⬜ |
| Kandidat model: Random Forest / XGBoost (time-series features) | ⬜ |
| Log params, metrics (MAE, RMSE, MAPE), artifacts ke MLflow | ⬜ |
| Minimal 3 run eksperimen dengan hyperparameter berbeda | ⬜ |
| Screenshot MLflow UI comparison antar run | ⬜ |

**Target metrik (dari EDA kita):**
- Prediction target: `request_rate` (req/s)
- Horizon: 60 detik (4 steps @ 15s)
- Feature window: 4 samples lookback
- Evaluation: MAE, RMSE on test split (last 15% chronologically)

**MLflow deployment di K3s:**
```yaml
# infrastructure/kubernetes/mlflow.yaml
# - MLflow server dengan PostgreSQL backend (reuse DB di cluster)
# - MinIO artifact store (bucket mlops-mlflow-artifacts)
# - Service: mlflow.titipin (ClusterIP) + Caddy proxy jika perlu akses eksternal
```

---

## Phase 7 — LK-07: MLflow Model Registry ⬜

> **Pekan 7 | Luaran: laporan PDF + metadata file + README update**

| Task | Status |
|---|---|
| Register model terbaik dari LK-06 ke MLflow Model Registry | ⬜ |
| Buat versi model v2 dengan parameter berbeda | ⬜ |
| Transisi stage: `None` → `Staging` → `Production` | ⬜ |
| Sinkronisasi metadata model dengan DVC | ⬜ |
| Verifikasi inferensi: `mlflow.pyfunc.load_model()` | ⬜ |
| Dokumentasi model mana yang aktif di README | ⬜ |

> [!NOTE]
> Setelah LK-07, ada UTS di Pekan ke-8. Pastikan semua artifacts dari LK-01 s/d LK-07 sudah lengkap sebelum UTS.

---

## Phase 8 — LK-08: GitHub Actions CI/CD Pipeline ⬜

> **Pekan 9 (setelah UTS) | Luaran: `.yaml` workflow file + log eksekusi + refleksi PDF**

| Task | Status |
|---|---|
| `.github/workflows/mlops-automation.yaml` | ⬜ |
| Job 1: Automated testing (`pytest`) on push | ⬜ |
| Job 2: Automated training (`train.py`) dengan data DVC | ⬜ |
| Job 3: Model evaluation vs threshold | ⬜ |
| Job 4: Auto-register ke MLflow Registry jika lolos validasi | ⬜ |
| Simulasi: commit kecil → trigger otomatis → pantau action logs | ⬜ |
| Notifikasi gagal jika threshold tidak terpenuhi | ⬜ |

```yaml
# .github/workflows/mlops-automation.yaml
on:
  push:
    branches: [main]
    paths:
      - 'src/models/**'
      - 'src/data/**'
      - 'configs/**'
```

---

## Phase 9 — LK-09: Docker Compose Orchestration ⬜

> **Pekan 10 | Luaran: `docker-compose.yml` + laporan PDF**

| Task | Status |
|---|---|
| Dockerfile untuk FastAPI inference service | ⬜ |
| Dockerfile untuk Streamlit ML dashboard | ⬜ |
| `docker-compose.yml` yang menyatukan: FastAPI + MLflow + MinIO + Streamlit | ⬜ |
| Environment variable management via `.env` | ⬜ |
| Health checks untuk setiap service | ⬜ |
| End-to-end test: kirim request → terima prediksi | ⬜ |

**Referensi:** `infrastructure/docker/docker-compose.prod.yaml` sudah ada (untuk Laravel), buat versi baru untuk MLOps stack.

---

## Phase 10 — LK-10: Kubernetes Deployment ⬜

> **Pekan 11 | Luaran: K8s manifests + laporan PDF**

> [!IMPORTANT]
> **Keunggulan kita:** K3s cluster sudah berjalan di AWS! LK-10 bisa langsung deploy ke cluster nyata, bukan hanya simulasi lokal seperti kebanyakan teman sekelas.

| Task | Status |
|---|---|
| K8s manifest untuk FastAPI inference service | ⬜ |
| K8s manifest untuk Streamlit ML dashboard | ⬜ |
| Service: `mlops.titipin.me` via Caddy | ⬜ |
| ConfigMap dan Secret untuk environment variables | ⬜ |
| Resource requests/limits yang sesuai VM constraints | ⬜ |
| Deploy ke cluster nyata: `kubectl apply -f infrastructure/kubernetes/mlops/` | ⬜ |
| Verifikasi deployment berjalan | ⬜ |

**Target:** `mlops.titipin.me` → Caddy → Streamlit dashboard (port 8501)

---

## Phase 11 — LK-11: Monitoring & Observability ⬜

> **Pekan 12 | Luaran: screenshot dashboard Grafana + laporan PDF**

> [!NOTE]
> **Keunggulan kita:** Prometheus + Grafana sudah live di `grafana.titipin.me`. Tinggal tambahkan panel khusus MLOps.

| Task | Status |
|---|---|
| Grafana dashboard untuk model metrics (MAE trend, drift status) | ⬜ |
| Grafana dashboard untuk inference latency | ⬜ |
| Alert rules: MAE melebihi threshold → trigger notifikasi | ⬜ |
| Prometheus metrics dari FastAPI inference service (`/metrics`) | ⬜ |
| Panel: actual vs predicted request_rate (time series) | ⬜ |
| Panel: replica recommended vs applied | ⬜ |

**Referensi:** `configs/grafana-demo-dashboard.json` sudah ada, perlu diperluas dengan MLOps panels.

---

## Phase 12 — LK-12: Continuous Training Pipeline ⬜

> **Pekan 13 | Luaran: Kubernetes CronJob / GitHub Actions scheduled + laporan PDF**

| Task | Status |
|---|---|
| Drift detection module (`src/monitoring/drift.py`) | ⬜ |
| Rolling error calculation (MAE/RMSE pada prediksi vs aktual) | ⬜ |
| Retraining trigger: jika MAE > threshold ATAU drift terdeteksi | ⬜ |
| Kubernetes CronJob untuk ingestion berkala (setiap 1 jam) | ⬜ |
| GitHub Actions scheduled workflow untuk retraining mingguan | ⬜ |
| Evaluasi kandidat model vs model production: hanya promote jika lebih baik | ⬜ |
| Rollback otomatis jika model baru gagal validasi | ⬜ |

**Trigger logic:**
```python
if rolling_mae > baseline_mae * 1.2 or psi_score > 0.2:
    trigger_retraining()
```

---

## Phase 13 — LK-13: Governance Audit ⬜

> **Pekan 14 | Luaran: dokumen PDF (audit report)**
> **Tipe: Analisis (non-coding utama)**

| Task | Status |
|---|---|
| Security scanning Docker image (`trivy` atau `grype`) | ⬜ |
| XAI/SHAP values untuk interpretasi keputusan model | ⬜ |
| Verifikasi tidak ada PII di pipeline data (metrics Prometheus tidak ada PII) | ⬜ |
| Risk matrix: identifikasi risiko keamanan dan rencana mitigasi | ⬜ |
| Pemetaan ke SKKNI 299/2020 atau prinsip etika AI | ⬜ |

> [!NOTE]
> Untuk proyek kita, justifikasi "tidak ada bias" cukup kuat karena data adalah **sistem metrics** (CPU, latency, replicas) — bukan data demografis manusia. Fokus audit bisa ke security (container vulnerabilities) dan model explainability (SHAP feature importance).

---

## Phase 14 — LK-14: Final Presentation ⬜

> **Pekan 15 | Luaran: Slides PDF/PPTX + live demo + laporan akhir PDF**

| Task | Status |
|---|---|
| Slides presentasi: problem → architecture → results → demo | ⬜ |
| Live demo: ingestion → training → inference → Streamlit dashboard | ⬜ |
| Final README dengan instruksi replikasi lengkap | ⬜ |
| Laporan akhir PDF (gabungan semua LK) | ⬜ |

**Demo flow yang harus bisa ditunjukkan:**
```
k6 generate load → Prometheus scrapes → export_dataset.py → DVC commit
→ train.py → MLflow Registry → FastAPI /predict → Streamlit dashboard
→ Grafana alerts → Continuous Training trigger
```

---

## Key Technical Decisions (Sudah Fixed dari EDA)

| Keputusan | Nilai | Sumber |
|---|---|---|
| Prediction target | `request_rate` (req/s) | EDA Section 8 |
| Sampling interval | 15 detik | Prometheus scrape |
| Feature window | 4 samples (~60s lookback) | EDA Section 8 |
| Prediction horizon | 60 detik (4 steps) | EDA Section 9 |
| Train/Val/Test split | 70/15/15 chronological | EDA Section 10 |
| HPA scaling lag | ~30–90s (mean ~45s) | EDA Section 7 |
| Scale-up threshold | ~8 req/s → 2 replicas | Calibration |
| Baseline to beat | Persistence + Rolling Mean | Phase 6 LK-06 |

---

## Repository Branch Strategy

```
main
├── feat/lk03-data-pipeline-plan    (LK-03: diagram + dokumen)
├── feat/lk04-ingestion             (LK-04: src/data/ingest.py + preprocess.py)
├── feat/lk05-dvc                   (LK-05: dvc init + versioning)
├── feat/lk06-mlflow-training       (LK-06: train.py + MLflow)
├── feat/lk07-model-registry        (LK-07: registry + lifecycle)
├── feat/lk08-cicd                  (LK-08: .github/workflows/)
├── feat/lk09-docker-compose        (LK-09: Dockerfiles + compose)
├── feat/lk10-k8s-deploy            (LK-10: infrastructure/kubernetes/mlops/)
├── feat/lk11-monitoring            (LK-11: Grafana dashboards)
├── feat/lk12-continuous-training   (LK-12: CT pipeline)
└── feat/lk13-governance-audit      (LK-13: audit report)
```

> Setiap branch dibuat dari `main` → dikerjakan → PR dengan bukti evidence → merge ke `main`.

---

## Immediate Next Steps (Pekan Ini)

### 1. Selesaikan LK-02 Evidence *(sekarang)*
- [ ] Screenshot Codespaces yang sukses rebuild (setelah fix devcontainer)
- [ ] Screenshot terminal: `python --version` + `pytest -q` + `ruff check .`
- [ ] Screenshot notebook `01_initial_eda.ipynb` yang berjalan di Codespace

### 2. Kerjakan LK-03 *(minggu depan)*
- [ ] Buat branch `feat/lk03-data-pipeline-plan`
- [ ] Buat diagram arsitektur data pipeline di Excalidraw/Draw.io
- [ ] Tulis dokumen PDF: sumber data, skema, ETL flow, rencana DVC
- [ ] Submit sebelum sesi praktikum Pekan ke-4

### 3. Fix Codespaces container *(urgent)*
- [ ] Di Codespace: `git pull origin main` → Rebuild Container
- [ ] Verifikasi `python -m pip check` dan `pytest -q` berjalan

---

## References & Tools

| Tool | Kegunaan | Status |
|---|---|---|
| GitHub Codespaces | Dev environment reproducible | ✅ Configured |
| k6 | Load generation eksternal | ✅ Installed |
| kubectl | Cluster management | ✅ Configured |
| Prometheus | Metrics scraping | ✅ Live |
| Grafana | Visualization | ✅ Live |
| DVC | Dataset versioning | ⬜ Phase 5 |
| MLflow | Experiment tracking + model registry | ⬜ Phase 6 |
| FastAPI | Inference API | ⬜ Phase 9 |
| Streamlit | MLOps dashboard | ⬜ Phase 9 |
| GitHub Actions | CI/CD automation | ⬜ Phase 8 |
| SHAP | Model explainability | ⬜ Phase 13 |
| Trivy | Container security scanning | ⬜ Phase 13 |
