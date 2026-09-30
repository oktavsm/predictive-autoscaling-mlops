# Panduan Presentasi Proyek Akhir & Live Demonstration — LK-14
> **Dokumen Luaran:** Slide Presentasi (PPTX/PDF) + Live Demo  
> **Branch:** `main`  
> **Domain Publik yang Didemokan:** `grafana.titipin.me`, `mlops.titipin.me`, `storage.titipin.me`, `mlflow.titipin.me`

---

## 1. Struktur Slide Presentasi (Panduan Isi)

Presentasi akhir harus mencakup **10–15 slide** yang menceritakan narasi MLOps end-to-end:

| Nomor | Judul Slide | Konten Utama |
|:---:|:---|:---|
| 1 | **Judul & Tim** | Nama, NIM, nama proyek, tagline |
| 2 | **Latar Belakang & Masalah** | Scaling lag problem pada HPA reaktif; kerugian SLA |
| 3 | **Arsitektur Sistem** | Diagram alur: Prometheus → Ingest → DVC → MLflow → K8s → Grafana |
| 4 | **Data Pipeline (LK-04/05)** | Contoh data telemetri, feature engineering lag/roll, DVC versioning |
| 5 | **Eksperimen & Model Selection (LK-06/07)** | Tabel komparasi 4 model; champion RF MAE 0.0295 |
| 6 | **CI/CD Otomatis (LK-08/09)** | Diagram 4 DAG workflow GitHub Actions; Docker Compose diagram |
| 7 | **Kubernetes Deployment (LK-10)** | Arsitektur namespace mlops di K3s; pod diagram |
| 8 | **Observability (LK-11)** | Screenshot Grafana dashboard live; PrometheusRule |
| 9 | **Continuous Training (LK-12)** | PSI/KS drift detection diagram; CronJob timeline |
| 10 | **Governance & Security (LK-13)** | SHAP plot; Trivy 0 critical; Model Card |
| 11 | **Live Demo** | Tangkapan layar split-screen selama demo berlangsung |
| 12 | **Hasil & Analisis** | Grafik perbandingan reactive vs predictive (scaling lag eliminated) |
| 13 | **Kesimpulan & Future Work** | Pencapaian; potensi pengembangan (multi-cluster, KEDA) |

---

## 2. Setup Live Demo (Sebelum Presentasi)

### 2.1 Pre-Flight Checklist (Lakukan 15 menit sebelum demo)

```bash
# 1. Verifikasi semua pod berjalan
kubectl get pods -n mlops
kubectl get pods -n titipin

# 2. Pastikan Prometheus targets UP
kubectl exec -n mlops deploy/mlops-inference -c inference-api -- \
  curl -s "http://monitoring-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090/api/v1/targets" | \
  jq '.data.activeTargets[] | select(.labels.namespace=="mlops") | {job: .labels.job, health: .health}'

# 3. Buka browser ke semua domain (pastikan login)
# - https://grafana.titipin.me  (Dashboard "MLOps Predictive Autoscaling")
# - https://mlflow.titipin.me   (Model Registry "predictive-autoscaler@champion")
# - https://storage.titipin.me  (MinIO — bucket mlops-dvc)
# - https://mlops.titipin.me    (Streamlit Predictive Dashboard)

# 4. Cek scaler metrics
curl -s http://<NODE_IP>:30902/metrics | grep autoscaler_recommended_replicas
```

### 2.2 Setup Split-Screen Layout

Atur layout layar laptop menjadi 3 panel berdampingan:
- **Panel Kiri:** Terminal A — `kubectl get pods -n titipin -w`
- **Panel Tengah:** Browser — `https://grafana.titipin.me` (Dashboard MLOps)
- **Panel Kanan:** Terminal B — `bash scripts/demo_traffic_spike.sh`

---

## 3. Prosedur Live Demo (Step-by-Step)

### Langkah 1 — Show Baseline State (2 menit)
```bash
# Tunjukkan replika awal (1 pod laravel)
kubectl get pods -n titipin
# Output: laravel-backend-xxx-xxx   1/1 Running

# Tunjukkan metrik prediksi saat ini
curl -s http://<NODE_IP>:30800/metrics | python3 -c "
import sys
for line in sys.stdin:
    if 'recommended' in line or 'predicted_workload' in line:
        print(line.strip())"
```

**Yang harus diceritakan:** "Saat ini sistem berjalan normal, 1 replica pod, predicted RPS sekitar X."

### Langkah 2 — Trigger Traffic Spike (3 menit)
```bash
# Jalankan lonjakan trafik dengan k6
bash scripts/demo_traffic_spike.sh https://api.titipin.me
```

**Yang harus ditunjukkan sambil k6 berjalan:**
1. Grafana: Garis biru `Predicted RPS t+60s` mulai naik
2. Setelah ~30 detik: Grafana: Garis oranye `Pod Replicas` naik ke 2-3 (SEBELUM garis merah `Actual Request Rate` mencapai puncak)
3. Terminal kubectl: `laravel-backend` menambah replica secara proaktif

**Poin demo kunci:** *"Sistem menambah pod pada menit ke-1:30, padahal beban baru mencapai puncak di menit ke-2:00. Ini adalah bukti eliminasi scaling lag."*

### Langkah 3 — Cool-Down (1 menit)
Setelah k6 selesai, tunjukkan bahwa:
- Predicted RPS turun
- Pod replicas kembali ke 1 setelah cooldown 60 detik

---

## 4. Domain Cloudflare Setup (Catatan untuk Kamu)

> **Semua domain ini sudah dikonfigurasi via Cloudflare Tunnel + Caddy di control plane.**
> Informasikan ke penguji bahwa semua ini diakses via domain publik:

| Domain | Layanan | Port Internal | Status |
|:---|:---|:---:|:---:|
| `api.titipin.me` | Laravel Backend API | 8000 (NodePort 30800) | ✅ Aktif |
| `storage.titipin.me` | MinIO Object Storage Console | 9001 | ✅ Aktif |
| `mlflow.titipin.me` | MLflow Tracking Server | 5000 | ✅ Aktif |
| `grafana.titipin.me` | Grafana Observability | 3000 | ✅ Aktif |
| `mlops.titipin.me` | Streamlit Predictive Dashboard | 8501 | ✅ Aktif |

---

## 5. Ringkasan Pencapaian Teknis (Untuk Slide Kesimpulan)

| Lembar Kerja | Komponen Utama | Bukti Teknis |
|:---:|:---|:---|
| **LK-04** | Data Ingestion dari Prometheus | `src/ingest_data.py`, `src/preprocess.py` |
| **LK-05** | Data Versioning (DVC + MinIO S3) | `.dvc/config`, Git tags `v1.0-data`, `v2.0-data` |
| **LK-06** | MLflow Experiment Tracking | 4 model trained; RF champion Val MAE: 0.0295 RPS |
| **LK-07** | MLflow Model Registry | `@champion` (RF) + `@challenger` (LightGBM) live |
| **LK-08** | CI/CD GitHub Actions | `.github/workflows/mlops-ci.yaml` — 4 DAG jobs |
| **LK-09** | Multi-Service Docker Compose | 4 services healthy (MinIO, MLflow, API, Dashboard) |
| **LK-10** | Kubernetes Deployment + Predictive Scaler | `mlops-inference` 2/2 Running; NodePort 30800/30902/30851 |
| **LK-11** | Prometheus Scraping + Grafana Dashboard | 2 targets UP; Dashboard UID `titipin-mlops-predictive-autoscaler` |
| **LK-12** | Continuous Training + Drift Detection | PSI + KS-test; CronJob `0 2 * * *` |
| **LK-13** | AI Governance + Security + SHAP | 0 CRITICAL CVEs; 0 secret leaks; feature causality verified |
| **LK-14** | Live Demo + Presentasi Akhir | Domain publik aktif; Demo spike script: `scripts/demo_traffic_spike.sh` |

---

## 6. Perintah Berguna Saat Demo

```bash
# Pantau pod secara real-time
kubectl get pods -n titipin -w

# Pantau scaler controller log
kubectl logs -n mlops deploy/mlops-inference -c predictive-scaler -f | grep -E "Scal|predict|recommend"

# Cek recommended replicas via API
curl -s http://<NODE_IP>:30800/predict | python3 -m json.tool

# Cek Prometheus metrics langsung
curl -s http://<NODE_IP>:30902/metrics | grep -E "autoscaler_recommended|autoscaler_predicted"

# Paksa satu siklus scaler (untuk demo instan)
kubectl exec -n mlops deploy/mlops-inference -c predictive-scaler -- \
  python3 -c "from src.scaling.predictive_scaler import PredictiveScaler; s=PredictiveScaler(); s.run_once()"
```
