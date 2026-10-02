# 📖 Panduan Lengkap Simulasi End-to-End MLOps & Manual Parameter Tuning

Dokumentasi ini disusun untuk memandu pengujian menyeluruh siklus hidup MLOps (*Closed-Loop Automated MLOps*) pada sistem **Predictive Autoscaling Kubernetes**. Panduan ini mencakup eksekusi otomatis satu-perintah (*hands-free*) serta tata cara pengujian bertahap dan penyesuaian (*tuning*) parameter secara manual.

---

## 🚀 1. Eksekusi Otomatis (Full Automated & Hands-Free)

Skrip otomatis telah dirancang agar Anda dapat menjalankan seluruh alur dari awal hingga akhir tanpa perlu menunggui terminal. 

Jalankan perintah berikut:
```bash
bash scripts/run_automated_mlops_pipeline.sh
```

### Alur yang Dijalankan Secara Otomatis:
1. **Tahap 1**: Mengirimkan beban normal steady-state (5 VU, 30s) $\rightarrow$ Scaler mempertahankan 1 pod (`MAINTAIN`).
2. **Tahap 2**: Mengirimkan lonjakan trafik masif (60 VU, 60s, ~100 RPS) $\rightarrow$ Scaler mendeteksi kenaikan gradien, meramal lonjakan, dan langsung menaikkan replika ke **4 pods** secara proaktif.
3. **Tahap 3**: Menginjeksi *Data Drift* telemetri skala besar (pergeseran distribusi rata-rata trafik $3.5\times$), menghitung skor PSI (*Population Stability Index*), dan menyinkronkan snapshot data ke MinIO Object Storage (`s3://mlops-dvc`).
4. **Tahap 4**: Memperbarui ConfigMap klaster, memicu *Kubernetes Continuous Retraining Job*, melatih model-model kandidat (Ridge, LightGBM, Random Forest), mengevaluasi gerbang validasi, dan mempromosikan model Champion baru ke MLflow Model Registry (*Production Stage*).
5. **Tahap 5**: Memuat bobot model baru via endpoint `/model/reload`, memverifikasi inferensi peramalan pada beban kerja tinggi, dan menampilkan tautan *deep-link* observabilitas.

---

## 🛠️ 2. Panduan Pengujian & Tuning Parameter Mandiri (Manual)

Jika di lain hari Anda ingin mengubah intensitas beban, mengubah ambang batas (*threshold*), atau melatih model dengan konfigurasi berbeda, ikuti petunjuk per tahap di bawah ini:

---

### A. Tuning Uji Beban Trafik (k6 Load Testing)

Skenario beban terletak di [`workloads/k6/scenarios/spike.js`](file:///home/oktaavsm/Code/github.com/college/predictive-autoscaling-mlops/workloads/k6/scenarios/spike.js). Anda dapat menimpa parameter secara langsung melalui CLI:

#### 1. Mengubah Jumlah Virtual Users (VUs) & Durasi:
```bash
# Uji beban rendah (baseline normal)
k6 run --vus 10 --duration 45s -e TARGET_URL=https://api.titipin.me workloads/k6/scenarios/spike.js

# Uji lonjakan ekstrem (stress testing / flash sale)
k6 run --vus 80 --duration 90s -e TARGET_URL=https://api.titipin.me workloads/k6/scenarios/spike.js
```

#### 2. Parameter yang Dapat Disesuaikan di `workloads/k6/scenarios/spike.js`:
* **`sleep(Math.random() * 0.5 + 0.1)`** (Baris 53): Waktu jeda antar-request (*think time*). Jika ingin request lebih rapat/agresif, ubah menjadi `sleep(0.05)`.
* **`thresholds.http_req_duration`** (Baris 26): Batas toleransi latensi P95 (contoh: `p(95)<1500` untuk 1.5 detik).

---

### B. Tuning Kebijakan Predictive Autoscaler

Konfigurasi autoscaler dikendalikan oleh environment variables pada ConfigMap [`infrastructure/kubernetes/mlops/02-configmap.yaml`](file:///home/oktaavsm/Code/github.com/college/predictive-autoscaling-mlops/infrastructure/kubernetes/mlops/02-configmap.yaml):

| Variabel | Default | Deskripsi & Saran Tuning |
|---|---|---|
| `TARGET_RPS_PER_POD` | `10.0` | Kapasitas target per pod Laravel. Jika ingin pod lebih cepat bertambah banyak pada beban rendah, turunkan ke `5.0` atau `7.5`. |
| `MIN_REPLICAS` | `1` | Jumlah pod minimum saat idle. |
| `MAX_REPLICAS` | `4` | Jumlah pod maksimum saat lonjakan trafik. Bisa dinaikkan ke `6` atau `8` jika node worker masih memiliki kapasitas memori. |
| `SCALE_INTERVAL_SECONDS` | `15` | Seberapa sering kontroler mengevaluasi metrik Prometheus. (Disarankan 10–15s). |
| `COOLDOWN_SECONDS` | `60` | Periode stabilisasi sebelum scale down diizinkan. Mengurangi fenomena *pod flapping*. |

Cara menerapkan perubahan parameter kontroler:
```bash
# Edit file configmap
nano infrastructure/kubernetes/mlops/02-configmap.yaml

# Terapkan ke klaster dan restart deployment
kubectl apply -f infrastructure/kubernetes/mlops/02-configmap.yaml
kubectl rollout restart deployment/mlops-inference -n mlops
```

Untuk memantau kalkulasi keputusan kontroler secara live di terminal:
```bash
kubectl logs -n mlops deploy/mlops-inference -c predictive-scaler -f
```

---

### C. Tuning Deteksi Data Drift & Threshold PSI

Deteksi drift menggunakan modul [`scripts/calculate_drift.py`](file:///home/oktaavsm/Code/github.com/college/predictive-autoscaling-mlops/scripts/calculate_drift.py) atau [`src/monitoring/drift_detector.py`](file:///home/oktaavsm/Code/github.com/college/predictive-autoscaling-mlops/src/monitoring/drift_detector.py).

#### 1. Menjalankan Analisis Drift Antar Dua Dataset:
```bash
python3 scripts/calculate_drift.py <PATH_DATASET_BASELINE> <PATH_DATASET_BARU>
```

#### 2. Kriteria Nilai PSI (Population Stability Index):
* $\text{PSI} < 0.10$: Distribusi stabil (*No Shift*).
* $0.10 \le \text{PSI} < 0.20$: Pergeseran moderat (*Moderate Drift*).
* $\text{PSI} \ge 0.20$: Pergeseran signifikan (*Significant Drift* $\rightarrow$ Wajib Retraining).

#### 3. Mengubah Intensitas Drift Sintetis:
Jika ingin membuat skenario lonjakan trafik yang lebih ekstrem atau lebih halus, ubah pengali pada script generator:
* `traffic_multiplier`: Ubah ke `4.5` untuk lonjakan luar biasa tinggi, atau `1.5` untuk kenaikan landai.
* `cpu_multiplier`: Sesuaikan konsumsi CPU (contoh: `3.0`).

---

### D. Menjalankan Retraining Model & MLflow Logging Secara Manual

Anda dapat memicu retraining baik secara lokal maupun langsung di klaster Kubernetes:

#### Cara 1: Menjalankan Retraining via Kubernetes Job (Direkomendasikan)
```bash
# 1. Update data training di ConfigMap jika menggunakan dataset baru
kubectl create configmap mlops-training-data \
  --from-file=metrics_demo_processed.csv=data/processed/metrics_flashsale_drifted.csv \
  -n mlops --dry-run=client -o yaml | kubectl apply -f -

# 2. Buat job retraining baru
JOB_NAME="manual-retrain-$(date +%s)"
kubectl create job --from=cronjob/mlops-continuous-training ${JOB_NAME} -n mlops

# 3. Pantau log pelatihan secara real-time
kubectl logs -f job/${JOB_NAME} -n mlops
```

#### Cara 2: Menjalankan Pelatihan di Mesin Lokal (Virtualenv)
```bash
python3 src/models/train.py \
  --data-path data/processed/metrics_flashsale_drifted.csv \
  --tracking-uri http://mlops-mlflow-svc.mlops.svc.cluster.local:5000 \
  --experiment-name predictive-autoscaling-workload
```

---

### E. Menguji Inference Engine & Hot-Reload Model

Setelah model baru selesai dilatih dan dipromosikan ke MLflow, Anda dapat menginstruksikan container inferensi untuk memuat bobot model baru tanpa me-restart pod:

```bash
# 1. Panggil reload model
curl -s -X POST https://model.titipin.me/model/reload | python3 -m json.tool

# 2. Periksa status kesehatan dan model aktif
curl -s https://model.titipin.me/health | python3 -m json.tool

# 3. Uji prediksi manual dengan payload custom
curl -s -X POST https://model.titipin.me/predict \
  -H "Content-Type: application/json" \
  -d '{
    "request_rate": 75.0,
    "php_cpu_cores": 1.1,
    "p95_latency_seconds": 0.16,
    "php_memory_mb": 200.0,
    "rps_roll_mean_60s": 70.0,
    "rps_delta": 5.0
  }' | python3 -m json.tool
```

---

## 📊 3. Cara Memeriksa Data & Observabilitas di Web UI

### 1. Grafana Observability (`https://grafana.titipin.me`)
* **Dashboard Autoscaler & Workload**:  
  Buka: [https://grafana.titipin.me/d/titipin-mlops-predictive-autoscaler/5b6dab5](https://grafana.titipin.me/d/titipin-mlops-predictive-autoscaler/5b6dab5)  
  *Gunakan time picker di kanan atas (misal **"Last 15 minutes"**) untuk melihat bentuk grafik kurva lonjakan beban (RPS) dan kenaikan pod replika.*
* **Dashboard Kesehatan VM / Node Kubernetes**:  
  Buka: [https://grafana.titipin.me/d/7d57716318ee0dddbac5a7f451fb7753/node-exporter-nodes](https://grafana.titipin.me/d/7d57716318ee0dddbac5a7f451fb7753/node-exporter-nodes)  
  *Pilih instance di dropdown kiri atas (`172.31.4.113:9100` untuk control-plane, atau worker nodes) untuk melihat CPU utilization, memory saturation, dan disk IOPS.*

### 2. MLflow Tracking & Model Registry (`https://mlflow.titipin.me`)
* **Experiments**: Klik experiment `predictive-autoscaling-workload`.
  * Bandingkan metrik `val_mae` antar model (`random-forest-default`, `lightgbm-default`, `ridge`).
  * Klik run untuk melihat visualisasi grafik evaluasi di tab **Artifacts** (`evaluation_plots/`).
* **Models**: Klik model `predictive-autoscaler`.
  * Lihat versi yang memiliki alias **`@champion`** (*sedang melayani inferensi di Production*) dan **`@challenger`** (*Staging*).

### 3. MinIO Object Storage (`https://minio.titipin.me`)
* Login dengan user: `titipin_minio` / pass: `rahasiawoy`.
* Buka bucket **`mlops-dvc`** $\rightarrow$ folder **`processed`**.
* File dataset hasil drift (`metrics_flashsale_drifted.csv`) dan file versi DVC tersimpan di sini.
