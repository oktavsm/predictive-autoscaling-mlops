# 🧭 Operational Handoff Guide for AI Agents & Engineers
## Predictive Autoscaling MLOps Platform — titipin.me

> **Target Audience:** Incoming AI Coding Agents (Antigravity/Claude Code/Cursor), DevOps Engineers, and System Operators.  
> **Status:** ✅ Production Live & Verified  
> **Last Updated:** October 2026  
> **Primary URL:** [https://mlops.titipin.me](https://mlops.titipin.me)

---

## 📌 1. Project & Architecture Overview

Sistem ini adalah platform **Predictive Autoscaling MLOps** end-to-end yang mengintegrasikan peramalan beban kerja berbasis Machine Learning (LightGBM / Random Forest / Ridge Regression) dengan orkestrasi klaster Kubernetes (k3s). Platform ini secara proaktif mereplikasi pod aplikasi web Laravel (`api.titipin.me`) sebelum lonjakan trafik terjadi, sekaligus memantau drift data, melatih ulang model secara otonom, dan menyediakan konsol observabilitas FinOps.

### 🌐 Public Domain & Ingress Mapping
Semua domain dikelola via **Cloudflare DNS (Proxy Active)** yang mengarah ke IP publik AWS Control Plane (`16.79.90.160`). Host Control Plane menjalankan reverse proxy **Caddy** dengan otomatisasi sertifikat SSL/TLS Let's Encrypt yang meneruskan permintaan ke NodePort k3s:

| Public Domain | Target In-Cluster Service | NodePort | Protocol | Keterangan & Akses |
|---|---|---|---|---|
| **`mlops.titipin.me`** | `mlops/mlops-dashboard` | `:30851` | HTTPS | **Streamlit Control Center (Design Kit v1.1.0)** |
| **`model.titipin.me`** | `mlops/mlops-inference-svc` | `:30800` | HTTPS | FastAPI Inference Engine & Prometheus `/metrics` |
| **`mlflow.titipin.me`** | `mlops/mlops-mlflow-svc` | `:30500` | HTTPS | MLflow Tracking Server & Model Registry |
| **`grafana.titipin.me`** | `monitoring/monitoring-grafana` | `:30300` | HTTPS | Grafana Observability Dashboards |
| **`storage.titipin.me`** | `titipin/minio` (S3 API) | `:30900` | HTTPS | MinIO S3 API Endpoint & DVC Remote Storage |
| **`minio.titipin.me`** | `titipin/minio` (Console) | `:30901` | HTTPS | MinIO Web Browser Console |
| **`api.titipin.me`** | `titipin/laravel-backend` | `:30080` | HTTPS | Backend API Target Skalabilitas |

---

## 🔐 2. SSH Access & Virtual Machine Topology

Semua host VM telah terkonfigurasi di `~/.ssh/config` stasiun kerja lokal pengembang. Autentikasi menggunakan SSH key (`~/.ssh/id_ed25519`).

### A. Host Alias Matrix (`~/.ssh/config`)

```ssh-config
# 1. AWS Control Plane (Master K3s, Caddy Ingress, Databases)
Host cp
  HostName 16.79.90.160
  User ubuntu
  Port 2222
  IdentityFile ~/.ssh/id_ed25519

# 2. AWS Worker 1 (MLOps UI & MLflow)
Host w1
  HostName 15.232.116.101
  User ubuntu
  Port 22
  IdentityFile ~/.ssh/id_ed25519

# 3. AWS Worker 2 (Inference, Scaler, & Laravel Pods)
Host w2
  HostName 15.232.71.54
  User ubuntu
  Port 22
  IdentityFile ~/.ssh/id_ed25519

# 4. BCC Lab Remote VM (24/7 k6 Load Generator Daemon)
Host cp-bcc
  HostName proxy.bccdev.id
  Port 11049
  User dev
  IdentityFile ~/.ssh/id_ed25519
```

> [!IMPORTANT]
> **Port SSH Control Plane:** Perhatikan bahwa host `cp` mendengarkan SSH di **Port 2222** (bukan 22 default). Hal ini dirancang untuk mencegah pemblokiran egress port 22 oleh firewall jaringan tertentu. Cukup panggil `ssh cp` dan konfigurasi SSH akan otomatis menggunakan port 2222.

---

## 🚀 3. Deployment & Hot-Reload Workflows

### A. Update & Deploy Streamlit Dashboard (`mlops.titipin.me`)
Di lingkungan K3s produksi, berkas `app.py` pada pod `mlops-dashboard` di-mount melalui Kubernetes ConfigMap yang dirujuk volume `dashboard-code` pada deployment. Nama ConfigMap dapat berversi; baca referensi aktif sebelum hot-deploy. Hot-deploy satu file hanya berlaku jika modul, aset, dan versi dependensi pada image sudah sesuai.

Revamp Overview memakai `adapter.py`, `overview.py`, `assets/dashboard.css`, `assets/tokens.json`, font lokal, dan `.streamlit/config.toml`. Untuk rilis yang mengubah modul, aset, atau dependensi, build image dengan `docker/Dockerfile.dashboard` dan sertakan seluruh file tersebut; jangan hanya menyalin `app.py` ke image lama. Image mengunci Streamlit 1.65.0 dan Altair 6.3.0 yang dipakai untuk validasi UI. Buat ConfigMap `app.py` berversi, lalu ganti digest image dan referensi ConfigMap dalam satu perubahan pod template. Simpan ConfigMap lama agar rollback mengembalikan kode yang cocok dengan image sebelumnya. Manifest dashboard menyimpan pasangan image/ConfigMap rilis; bukti deployment ada di `docs/dashboard-revamp/`.

#### ⚡ Alur Hot-Deploy Dashboard (Rolling Update):
Pantau endpoint publik sepanjang rollout. Rilis 13 Oktober mencatat satu sampel HTTP 502 ketika pod berganti; alur ini tidak menjamin tanpa gangguan atau durasi di bawah 30 detik.
```bash
# 1. Pastikan unit tests dashboard lolos di lokal
pytest tests/test_dashboard_adapter.py -v

# 2. Salin app.py lokal ke server Control Plane (cp)
scp src/dashboard/app.py cp:/tmp/app.py

# 3. Update ConfigMap yang benar-benar dipakai deployment (nama dapat berversi)
ssh cp 'set -eu
dashboard_map=$(kubectl -n mlops get deployment mlops-dashboard -o jsonpath="{.spec.template.spec.volumes[?(@.name==\"dashboard-code\")].configMap.name}")
test -n "$dashboard_map"
kubectl create configmap "$dashboard_map" --from-file=app.py=/tmp/app.py -n mlops --dry-run=client -o yaml | kubectl apply -f -'

# 4. Lakukan rolling restart deployment
ssh cp "kubectl rollout restart deployment/mlops-dashboard -n mlops"

# 5. Verifikasi status pod dan periksa live endpoint
ssh cp "kubectl rollout status deployment/mlops-dashboard -n mlops"
curl -sI https://mlops.titipin.me
```

### B. Update Inference & Predictive Scaler (`model.titipin.me`)
Manifest deployment berada di `infrastructure/kubernetes/mlops/03-inference-deployment.yaml`.
Jika memperbarui konfigurasi atau image inference:
```bash
# Terapkan perubahan manifest
ssh cp "kubectl apply -f /path/to/manifest.yaml -n mlops"

# Atau restart deployment untuk memuat model baru dari S3 / MLflow
ssh cp "kubectl rollout restart deployment/mlops-inference -n mlops"
ssh cp "kubectl rollout status deployment/mlops-inference -n mlops"

# Uji health check endpoint
curl -s https://model.titipin.me/health
```

---

## 🛠️ 4. Standard Operational Commands (Cheatsheet)

### A. Cluster & Kubernetes Health
```bash
# Cek seluruh status node klaster
ssh cp "kubectl get nodes -o wide"

# Cek seluruh pod di namespace mlops, titipin, dan monitoring
ssh cp "kubectl get pods -A -o wide"

# Cek resource usage (CPU & RAM) per pod dan per node
ssh cp "kubectl top nodes"
ssh cp "kubectl top pods -n mlops"
ssh cp "kubectl top pods -n titipin"

# Cek jumlah replika pod Laravel backend saat ini
ssh cp "kubectl get deployment laravel-backend -n titipin -o wide"
```

### B. Live Log Streaming
```bash
# Log Streamlit Dashboard
ssh cp "kubectl logs -n mlops deployment/mlops-dashboard --tail=50 -f"

# Log Predictive Autoscaler loop (kontainer predictive-scaler)
ssh cp "kubectl logs -n mlops deployment/mlops-inference -c predictive-scaler --tail=50 -f"

# Log FastAPI Inference Server (kontainer inference-api)
ssh cp "kubectl logs -n mlops deployment/mlops-inference -c inference-api --tail=50 -f"

# Log Ingress Caddy (pada host OS cp)
ssh cp "sudo journalctl -u caddy -f --no-tail -n 50"
```

### C. Traffic Load Generator Control (`cp-bcc`)
Generator trafik berbasis k6 berjalan 24/7 sebagai service systemd pada VM `cp-bcc`.
```bash
# Cek status service load generator
ssh cp-bcc "sudo systemctl status titipin-traffic-generator"

# Live stream log generator beban
ssh cp-bcc "tail -n 50 -f /home/dev/titipin-traffic-generator/daemon.log"

# Trigger skenario lonjakan beban seketika (Spike Mode: 75 VUs)
ssh cp-bcc "/home/dev/titipin-traffic-generator/manage_generator.sh spike"

# Kembalikan ke beban normal (Steady Mode: 8-15 VUs)
ssh cp-bcc "/home/dev/titipin-traffic-generator/manage_generator.sh normal"

# Restart load generator service
ssh cp-bcc "sudo systemctl restart titipin-traffic-generator"
```

### D. Automated Retraining & Drift Pipeline
Pipeline retraining otonom dijadwalkan via K8s CronJob harian (`08-continuous-training-cronjob.yaml`).
```bash
# Cek daftar CronJob yang terdaftar
ssh cp "kubectl get cronjobs -n mlops"

# Trigger manual retraining pipeline secara on-demand
ssh cp "kubectl create job --from=cronjob/continuous-training-cronjob manual-retrain-\$(date +%s) -n mlops"

# Pantau eksekusi pod retraining
ssh cp "kubectl get pods -n mlops -l job-name --watch"
ssh cp "kubectl logs -n mlops -l job-name -f"
```

### E. DVC (Data Version Control) & MinIO Sync
```bash
# Cek status dataset yang dilacak DVC
dvc status

# Melihat perbedaan commit dataset
dvc diff HEAD~1

# Push cache dataset ke remote MinIO S3
dvc push

# Tarik versi dataset terbaru
dvc pull

# Jalankan skrip sinkronisasi remote
bash scripts/sync_dvc_remote.sh
```

### F. Query Prometheus & Telemetri Metrik
```bash
# Cek nilai metrik prediksi replika yang sedang diputuskan oleh scaler
ssh cp "curl -s 'http://127.0.0.1:9090/api/v1/query?query=predictive_autoscaler_recommended_replicas' | jq ."

# Cek metrik drift PSI (Population Stability Index)
ssh cp "curl -s 'http://127.0.0.1:9090/api/v1/query?query=ml_feature_drift_psi' | jq ."

# Cek metrik inference API publik
curl -s https://model.titipin.me/metrics | grep predictive_autoscaler
```

---

## 🔒 5. Credentials & Secret Management Rules

> [!CAUTION]
> **DILARANG KERAS MENYIMPAN ATAU MELAKUKAN COMMIT KREDENSIAL / PRIVATE KEY KE GIT.**

1. **File Kredensial Lokal:**
   - Semua token rahasia, kunci MinIO, MLflow basic auth, dan webhook tersimpan di berkas `.env.internal` dan `.env` yang terdaftar di `.gitignore`.
   - Gunakan `.env.example` sebagai referensi struktur variabel tanpa nilai rahasia.
2. **Kredensial In-Cluster Kubernetes:**
   - Tersimpan aman di K8s Secrets:
     ```bash
     ssh cp "kubectl get secrets -n mlops"
     ssh cp "kubectl get secrets -n titipin"
     ```
   - Contoh secret: `mlops-secrets`, `minio-credentials`, `postgres-secret`.
3. **SSH Keys:**
   - Key privat berada di `~/.ssh/id_ed25519` mesin pengembang dan **tidak boleh disalin keluar**.

---

## 🩺 6. Troubleshooting Playbook

### Problem 1: Dashboard (`mlops.titipin.me`) menampilkan HTTP 502 Bad Gateway
1. Periksa apakah pod dashboard berjalan:
   ```bash
   ssh cp "kubectl get pods -n mlops -l app.kubernetes.io/name=mlops-dashboard"
   ```
2. Jika pod dalam status `CrashLoopBackOff`, cek log:
   ```bash
   ssh cp "kubectl logs -n mlops deployment/mlops-dashboard --previous"
   ```
3. Periksa Caddy reverse proxy:
   ```bash
   ssh cp "sudo systemctl status caddy"
   ```

### Problem 2: Scaler tidak mengubah jumlah pod `laravel-backend`
1. Pastikan role RBAC terpasang dan pod memiliki izin `scale` deployments di namespace `titipin`:
   ```bash
   ssh cp "kubectl auth can-i update deployment/scale -n titipin --as=system:serviceaccount:mlops:mlops-inference-sa"
   ```
   *Harus menghasilkan output:* `yes`.
2. Periksa log loop autoscaler untuk mendeteksi error komunikasi ke K8s API:
   ```bash
   ssh cp "kubectl logs -n mlops deployment/mlops-inference -c predictive-scaler --tail=100"
   ```

### Problem 3: Koneksi ke MinIO S3 API gagal (`storage.titipin.me`)
1. Uji konektivitas HTTPS dari luar:
   ```bash
   curl -sI https://storage.titipin.me/minio/health/live
   ```
2. Pastikan pod MinIO di namespace `titipin` dalam status `Running`:
   ```bash
   ssh cp "kubectl get pods -n titipin -l app=minio"
   ```

---

## 📂 7. Struktur Direktori Kunci untuk Navigasi Cepat

```text
predictive-autoscaling-mlops/
├── src/
│   ├── dashboard/
│   │   ├── app.py                     # [CORE] Streamlit Dashboard (Design Kit v1.1.0)
│   │   └── assets/                    # Logo, CSS style tokens, dan tema visual
│   ├── inference/
│   │   └── service.py                 # FastAPI serving endpoint & Prometheus exporter
│   ├── scaling/
│   │   └── predictive_scaler.py       # Loop kontroler autoscaling proaktif
│   ├── pipeline/
│   │   ├── continuous_training.py     # Pipeline retrain berkala
│   │   ├── autonomous_drift_retrain.py# Trigger retrain berbasis deteksi drift
│   │   └── auto_ingest_and_version.py # Ingesti otomatis dan integrasi DVC
│   └── monitoring/
│       ├── drift_detector.py          # Kolmogorov-Smirnov & PSI statistical drift
│       └── finops_calculator.py       # Kalkulasi efisiensi biaya komputasi & vCPU
├── infrastructure/
│   └── kubernetes/
│       ├── mlops/                     # Manifest K8s (Dashboard, Inference, CronJob, MLflow)
│       └── backend.yaml               # Manifest target Laravel backend
├── workloads/
│   └── load-generator/                # Skrip traffic generator k6 yang sinkron ke VM cp-bcc
├── tests/                             # Unit tests (pytest)
├── scripts/                           # Skrip otomasi shell dan helper MLOps
└── docs/                              # Dokumentasi teknis & coursework akademik
    └── internal/
        ├── AGENT_HANDOFF_OPERATIONS.md# [DOKUMEN INI] Panduan operasional handoff
        └── VM.md                      # Spesifikasi hardware & IP VM klaster
```

---
*Dokumen ini dibuat secara komprehensif agar setiap agent baru dapat langsung beroperasi, mendiagnosis, dan melakukan deployment tanpa ambiguitas.*
