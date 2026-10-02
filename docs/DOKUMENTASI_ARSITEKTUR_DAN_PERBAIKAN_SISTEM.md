# 📘 Dokumentasi Lengkap Arsitektur, Perbaikan Sistem, & Operasional MLOps

Dokumen ini merangkum secara komprehensif seluruh perbaikan arsitektur, pemisahan tanggung jawab kecerdasan buatan (*AI Model*) dan kontrol infrastruktur (*Scaling Policy*), pemecahan masalah observabilitas Grafana, generator beban 24/7 di VM `cp-bcc`, serta pedoman operasional sistem **Predictive Autoscaling MLOps**.

---

## 📑 Daftar Isi
1. [Pemisahan Peran: Model ML vs Autoscaling Policy Controller](#1-pemisahan-peran-model-ml-vs-autoscaling-policy-controller)
2. [Investigasi & Perbaikan Bug Observabilitas Grafana](#2-investigasi--perbaikan-bug-observabilitas-grafana)
3. [Konfigurasi Penskalaan 1 s.d. 6 Pod & Dinamika Co-Existing HPA](#3-konfigurasi-penskalaan-1-sd-6-pod--dinamika-co-existing-hpa)
4. [Continuous Stochastic Load Generator 24/7 (VM cp-bcc)](#4-continuous-stochastic-load-generator-247-vm-cp-bcc)
5. [Pipeline Simulasi Otomatis (Hands-Free Master Runner)](#5-pipeline-simulasi-otomatis-hands-free-master-runner)
6. [Tabel Referensi Port, URL Layanan, & Perintah Penting](#6-tabel-referensi-port-url-layanan--perintah-penting)

---

## 1. Pemisahan Peran: Model ML vs Autoscaling Policy Controller

Seringkali terjadi kesalahpahaman bahwa model Machine Learning langsung memprediksi "jumlah pod Kubernetes". Dalam arsitektur sistem ini, diterapkan prinsip **Decoupling (Pemisahan Tanggung Jawab)**:

```
                      ┌─────────────────────────────────────────┐
                      │        Model Machine Learning           │
                      │ (Random Forest / LightGBM / Ridge)      │
                      └────────────────────┬────────────────────┘
                                           │ Memprediksi Workload
                                           ▼ (Request Rate / RPS t+60s)
                      ┌─────────────────────────────────────────┐
                      │    Autoscaling Policy Controller        │
                      │       (src/scaling/predictive_scaler)   │
                      └────────────────────┬────────────────────┘
                                           │ Menerapkan Aturan Kapasitas:
                                           │ Pod = ceil(Predicted_RPS / 10.0)
                                           │ Dibatasi: [MIN=1, MAX=6]
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │      Kubernetes Deployment Scale        │
                      │         (titipin/laravel-backend)       │
                      └─────────────────────────────────────────┘
```

### A. Apa yang Diprediksi oleh Model AI?
* **Target Prediksi**: Nilai skalar **`target_rps_60s`** (Laju trafik / *Incoming Request Rate* dalam satuan **RPS** untuk cakrawala waktu $t+60$ detik ke depan).
* **Fitur Input**: 15 fitur telemetri yang mencakup *lag features* ($t-15s, t-30s$), *rolling statistics* (mean, std dev), laju perubahan gradien ($\Delta RPS, \Delta CPU$), footprint memori PHP-FPM, dan waktu (jam/menit).
* **Karakteristik Model**: Model AI berfokus murni pada pemodelan deret waktu (*time-series forecasting*) dan dinamika fluktuasi beban pengguna.

### B. Apa yang Menentukan Jumlah Replika Pod?
Jumlah replika pod dihitung dan diputuskan oleh **Autoscaling Policy Controller** di lapisan aplikasi/infrastruktur menggunakan formula kapasitas:
$$\text{Desired Replicas} = \text{clamp}\left(\left\lceil \frac{\text{Predicted RPS}}{\text{TARGET\_RPS\_PER\_POD}} \right\rceil, \text{MIN\_REPLICAS}, \text{MAX\_REPLICAS}\right)$$

* `TARGET_RPS_PER_POD = 10.0` (Kapasitas ideal per pod Laravel untuk menjaga latensi P95 $< 100\text{ms}$).
* `MIN_REPLICAS = 1` (Batas bawah / *floor* saat idle).
* `MAX_REPLICAS = 6` (Batas atas / *ceiling* keselamatan infrastruktur).

### C. Mengapa Mengubah Batas Pod (4 ke 6 Pod) Tidak Perlu Retraining Model?
* Mengubah rentang replika dari `1-4` menjadi `1-6` pod **bukanlah perubahan bobot matematika AI**, melainkan **perubahan kebijakan kapasitas infrastruktur (*infrastructure policy threshold*)**.
* Model Champion aktif (v8) sudah dilatih pada dataset telemetri *flash-sale* yang mencakup laju trafik hingga $65+\text{ RPS}$. Saat trafik masuk mencapai $55-65\text{ RPS}$, model AI memprediksi laju beban tinggi tersebut, dan *policy controller* secara otomatis mengonversikannya menjadi **6 Pods**.

---

## 2. Investigasi & Perbaikan Bug Observabilitas Grafana

Dua kendala utama pada visualisasi Grafana telah diinvestigasi dan diselesaikan secara tuntas:

### Masalah 1: Notifikasi *"No datasource was found"*
* **Akar Masalah**: Container Grafana sebelumnya menggunakan image tag `grafana/grafana:13.2.1-distroless`. Pada build eksperimental tersebut, plugin inti `prometheus` tidak terkompilasi di dalam image (hanya ada *alertmanager*, *cloudwatch*, dan *graphite*). Akibatnya, Grafana menolak query dengan log error:  
  `Could not find plugin definition for data source datasource_type=prometheus`.
* **Solusi Perbaikan**:
  1. Image Grafana di-update ke rilis resmi stabil: **`docker.io/grafana/grafana:11.5.2`**.
  2. Plugin `prometheus` kini aktif secara bawaan (*native/builtin*), query proxy Prometheus kembali normal (**HTTP 200**).
  3. Mengaktifkan **Anonymous Access** (`[auth.anonymous] enabled = true, org_role = Viewer`) sehingga siapapun dapat melihat dashboard tanpa terhalang form login.
  4. Menetapkan **Default Home Dashboard UID** ke `titipin-mlops-predictive-autoscaler` agar saat URL dibuka, langsung menyajikan dashboard utama MLOps.

---

### Masalah 2: Metrik Duplikat Menjadi 3 & Kotak Bertumpuk
* **Akar Masalah**:
  1. Pada query PromQL awal, metrik dipanggil mentah tanpa fungsi agregasi: `predictive_scaler_predicted_workload_rps`.
  2. Saat klaster melakukan *rolling update* pod inferensi, Prometheus menyimpan time series dari pod lama dalam jendela waktu 1 jam (misal `pod-67d8...`, `pod-5f8c...`, dan `pod-76db...`).
  3. Karena label nama pod berbeda, Grafana menganggapnya 3 metrik yang berbeda sehingga menggambar **3 garis tumpang tindih** di grafik dan merender **3 kotak stat bertumpuk**.
  4. Pada panel replika, penggunaan operator `or` tanpa agregasi (`predictive_scaler_current_replicas or kube_deployment_status_replicas...`) mengembalikan 2 frame terpisah karena skema label berbeda.
* **Solusi Perbaikan**:
  Semua query dibungkus dengan fungsi agregasi PromQL dan penyetelan panel Stat:
  * **Panel Stat Kotak**: Disetel ke `instant: true` dan `range: false`.
  * **Current Replicas**: `max(kube_deployment_status_replicas{namespace="titipin", deployment="laravel-backend"})` $\rightarrow$ Tepat 1 angka bersih.
  * **Desired Replicas**: `max(predictive_scaler_desired_replicas)` $\rightarrow$ Tepat 1 angka bersih.
  * **Predicted RPS**: `max(predictive_scaler_predicted_workload_rps)` $\rightarrow$ Tepat 1 kurva halus.
  * **Actual Traffic**: `sum(rate(caddy_http_requests_total{host=~"api.titipin.me.*"}[1m])) or vector(0)`.
  * **Scale Events**: `sum(predictive_scaler_scale_events_total) or vector(0)`.

---

## 3. Konfigurasi Penskalaan 1 s.d. 6 Pod & Dinamika Co-Existing HPA

### A. Kapasitas Hardware Node Worker (AWS)
Pengujian kapasitas membuktikan bahwa klaster memiliki ruang resource yang sangat aman untuk menjalankan 6 pod:
* `worker-1`: CPU 8% terpakai | RAM 42% (817 MiB)
* `worker-2`: CPU 2% terpakai | RAM 49% (935 MiB)
* Permintaan per pod `laravel-backend`: hanya **175m CPU** dan **152 MiB RAM**. Alokasi 6 pod tersebar merata (3 pod di worker-1, 3 pod di worker-2).

### B. Mengapa Native Kubernetes HPA Dibiarkan Aktif Berdampingan?
Klaster saat ini memiliki **dua mekanisme penskalaan aktif**:
1. **Kubernetes Native HPA (`titipin/laravel-backend`)**:
   * Ambang batas: Target CPU 60%, Min 1 pod, Max 6 pod.
   * Karakteristik: **Reaktif & Mengalami Scaling Lag**. HPA baru bersiap menambah pod setelah CPU pod fisik tertekan di atas 60% selama periode waktu tertentu.
2. **Predictive Autoscaler (ML Controller)**:
   * Ambang batas: Target 10 RPS/pod, Min 1 pod, Max 6 pod.
   * Karakteristik: **Proaktif & Zero Lag**. Kontroler membaca tren kenaikan trafik dari edge Caddy dan menaikkan pod sebelum antrean request menumpuk.

#### Manfaat Ilmiah & Presentasi Coursework:
Di panel dashboard Grafana **`Pod Replicas: Predictive Scaler vs Reactive Baseline`**, pergerakan kedua kontroler ini dapat dibandingkan secara langsung (*head-to-head*):
* **Garis Hijau (AI Recommendation)**: Melonjak lebih awal saat mendeteksi laju perubahan trafik.
* **Garis Kuning (Reactive HPA)**: Baru menyusul naik setelah CPU terbebani, mendemonstrasikan keunggulan AI dalam mengeliminasi *scaling lag*.

---

## 4. Continuous Stochastic Load Generator 24/7 (VM cp-bcc)

Untuk memastikan dashboard Grafana tidak pernah kosong dan memiliki pola realistis layaknya aplikasi produksi harian, VM `cp-bcc` dikonfigurasi sebagai generator beban latar belakang (*background service*).

### A. Arsitektur State Machine Probabilistik (Markov Chain)
Generator berganti kondisi (*state*) secara otomatis menggunakan distribusi probabilitas:

| State | Beban (RPS / VUs) | Rentang Durasi | Perilaku Sistem |
|---|---|---|---|
| **`STEADY_NORMAL`** | 4 – 12 RPS (4–8 VUs) | 20 – 45 menit | Trafik pengguna harian. Grafik bergelombang natural, pod stabil di 1 replika optimal. |
| **`BURST_BUSY`** | 20 – 40 RPS (18–28 VUs) | 10 – 20 menit | Jam sibuk siang/sore. Kontroler mulai mempersiapkan replika tambahan (2-3 pods). |
| **`FLASH_ANOMALY`** | 60 – 95 RPS (50–75 VUs) | 3 – 8 menit | **ANOMALI / FLASH SALE**: Lonjakan tajam mendadak! Scaler langsung meramal dan menaikkan pod ke **4 hingga 6 pods**. |
| **`COOLING_DOWN`** | 10 – 20 $\rightarrow$ 2 RPS | 5 – 10 menit | Periode pendinginan. Menunjukkan periode stabilisasi *cooldown* 60 detik sebelum replika diturunkan bertahap. |
| **`IDLE_SILENT`** | 0 – 1 RPS (0 VUs) | 5 – 15 menit | Menyimulasikan tengah malam / sepi total. Grafik Grafana turun ke nol, pod tetap di 1 replika. |

### B. Manajemen Generator via SSH
Service berjalan di bawah systemd: `titipin-traffic-generator.service` (aktif dan auto-start saat reboot).

Perintah cepat dari terminal lokal:
```bash
# 1. Pantau log pergerakan trafik & durasi state yang aktif
ssh cp-bcc "cd ~/titipin-traffic-generator && ./manage_generator.sh logs"

# 2. Paksa transisi instan ke lonjakan FLASH SALE (Bagus untuk live demo)
ssh cp-bcc "cd ~/titipin-traffic-generator && ./manage_generator.sh trigger spike"

# 3. Paksa transisi instan ke momen hening (0 request)
ssh cp-bcc "cd ~/titipin-traffic-generator && ./manage_generator.sh trigger idle"

# 4. Paksa kembali ke trafik normal stabil
ssh cp-bcc "cd ~/titipin-traffic-generator && ./manage_generator.sh trigger steady"

# 5. Cek status service
ssh cp-bcc "cd ~/titipin-traffic-generator && ./manage_generator.sh status"
```

---

## 5. Pipeline Simulasi Otomatis (Hands-Free Master Runner)

Skrip pengujian otomatis menyeluruh tersedia di [`scripts/run_automated_mlops_pipeline.sh`](file:///home/oktaavsm/Code/github.com/college/predictive-autoscaling-mlops/scripts/run_automated_mlops_pipeline.sh). 

Jalankan perintah ini kapan saja Anda ingin menunjukkan pengujian komprehensif tanpa perlu menyentuh keyboard:
```bash
bash scripts/run_automated_mlops_pipeline.sh
```

### Tahapan yang Dijalankan Secara Otomatis:
1. **Tahap 1 (Baseline)**: Menjalankan k6 5 VU (30s) $\rightarrow$ Verifikasi 1 replika pod aktif.
2. **Tahap 2 (Spike Surge)**: Menjalankan k6 60 VU (60s) $\rightarrow$ Scaler mendeteksi kenaikan, meramal $80+\text{ RPS}$, dan menaikkan replika ke kapasitas puncak.
3. **Tahap 3 (Data Drift)**: Menghasilkan dataset *flash-sale*, menghitung skor PSI ($\text{PSI} > 0.20$ pada 4 fitur), dan mengunggah snapshot ke MinIO S3 (`s3://mlops-dvc/processed/`).
4. **Tahap 4 (Continuous Retraining)**: Meluncurkan K8s Job `mlops-continuous-training`, melatih model kandidat, mengevaluasi gerbang validasi, dan mempromosikan model Champion baru ke MLflow Registry (`@champion Production`).
5. **Tahap 5 (Closed-Loop Validation)**: Menembak endpoint `/model/reload`, menguji inferensi beban tinggi 65 RPS, dan mengonfirmasi respon autoscaling `recommended_replicas: 6`.

---

## 6. Tabel Referensi Port, URL Layanan, & Perintah Penting

### A. Tautan Web Portal Terverifikasi
| Layanan | URL Publik | Keterangan & Akses |
|---|---|---|
| **Grafana Dashboard** | [https://grafana.titipin.me](https://grafana.titipin.me) | Bebas akses (Anonymous Viewer). Dashboard default MLOps. |
| **MLflow Tracking & Registry** | [https://mlflow.titipin.me](https://mlflow.titipin.me) | Model Registry (`predictive-autoscaler`) & Experiment Runs. |
| **MinIO Object Storage** | [https://minio.titipin.me](https://minio.titipin.me) | Bucket `mlops-dvc` (User: `titipin_minio`, Pass: `rahasiawoy`). |
| **Streamlit UI Simulator** | [https://mlops.titipin.me](https://mlops.titipin.me) | What-If Simulator & Architecture Visualizer. |
| **Model Inference API Docs** | [https://model.titipin.me/docs](https://model.titipin.me/docs) | Swagger UI Interactive API documentation. |
| **Target Backend Web API** | [https://api.titipin.me](https://api.titipin.me) | Endpoint aplikasi Laravel (Target beban k6). |

### B. Perintah Diagnostik Penting di Terminal
```bash
# Cek kondisi pod MLOps dan pod Backend
kubectl get pods -n mlops
kubectl get pods -n titipin

# Pantau keputusan penskalaan Predictive Scaler secara live
kubectl logs -n mlops deploy/mlops-inference -c predictive-scaler -f

# Uji kesehatan endpoint inferensi model & batas replika
curl -s https://model.titipin.me/health | python3 -m json.tool

# Uji keputusan peramalan secara manual
curl -s -X POST https://model.titipin.me/scale-decision \
  -H "Content-Type: application/json" \
  -d '{"request_rate": 65.0, "php_cpu_cores": 1.1, "p95_latency_seconds": 0.16, "php_memory_mb": 200.0, "current_replicas": 1}' \
  | python3 -m json.tool

# Cek status HPA bawaan Kubernetes
kubectl get hpa -n titipin
```
