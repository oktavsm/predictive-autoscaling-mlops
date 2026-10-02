# 🎮 Panduan Live Web UI & Eksekusi Demo Praktikum (LK-14)
## Pusat Kendali MLOps: Injeksi Beban Real-Time & Demonstrasi Interaktif

Dokumen ini adalah panduan lengkap bagi mahasiswa untuk mendemonstrasikan sistem **Predictive Autoscaling MLOps** secara langsung di hadapan dosen penguji tanpa perlu mengetikkan perintah rumit di terminal saat presentasi.

---

## 🌐 1. Akses Portal & Dashboard Terintegrasi

| Layanan / Portal | URL Publik | Fungsi Utama |
|:---|:---|:---|
| **⚡ MLOps Control Hub (Streamlit)** | **https://mlops.titipin.me** | Mengontrol injeksi beban, simulasi scaling, kalkulator FinOps, dan pemicu pipeline. |
| **📊 Grafana Observability** | **https://grafana.titipin.me** | Memantau grafik telemetri RPS, P95 latency, dan replika pod secara langsung (Viewer Mode). |
| **🔬 MLflow Model Registry** | **https://mlflow.titipin.me** | Memperlihatkan perbandingan metrik model dan promosi alias `@champion`. |
| **🗄️ MinIO S3 Console** | **https://minio.titipin.me** | Memperlihatkan silsilah dan versioning dataset DVC di bucket `mlops-dvc`. |
| **📑 Inference API Docs (Swagger)** | **https://model.titipin.me/docs** | Dokumentasi interaktif OpenAPI/Swagger untuk testing endpoint REST API. |

---

## 🚀 2. Cara Kerja Tab: "Live Workload Injector (VM cp-bcc)"

Fitur ini menghubungkan dashboard Streamlit ke remote VM **`cp-bcc`** secara decoupled melalui REST API:

```
 [ Browser Mahasiswa / Dosen ]
             │
             │ Klik tombol: "Flash-Sale Spike Anomaly"
             ▼
 [ Streamlit Dashboard (mlops.titipin.me) ]
             │
             │ POST /workload/trigger {"state": "FLASH_ANOMALY"}
             ▼
 [ FastAPI Inference Service (model.titipin.me) ]
             │
             ▲ Polling status tiap 2-3 detik
             │
 [ Traffic Generator Daemon (VM cp-bcc: proxy.bccdev.id) ]
             │
             │ Eksekusi k6 runner (50-75 VUs)
             ▼
 [ Target Ingress Caddy (api.titipin.me) ]
             │
             ▼
 [ Predictive Autoscaler & Laravel Backend ]
 (Mendeteksi lonjakan & menambah pod hingga 6 Pods)
```

---

## 🎬 3. Skenario Demo Langkah Demi Langkah (Durasi: ~5 Menit)

Saat mempresentasikan **LK-14 (Live Demo)**, buka dua tab browser berdampingan:
* **Tab Kiri:** `https://mlops.titipin.me` (Streamlit Dashboard)
* **Tab Kanan:** `https://grafana.titipin.me` (Dashboard MLOps Autoscaler)

### Langkah 1: Tunjukkan Kondisi Klaster Tenang (Baseline)
1. Buka tab **"🚀 Live Workload Injector (VM cp-bcc)"** di Streamlit.
2. Klik tombol **`🟢 1. Daytime Steady Workload (5-12 RPS)`**.
3. Tunjukkan di Grafana:
   * Trafik masuk berada di kisaran $6-10\text{ RPS}$.
   * Replika pod `laravel-backend` stabil di **1 Pod** (hemat resource).

### Langkah 2: Picu Lonjakan Mendadak (Flash-Sale Spike Anomaly)
1. Klik tombol merah **`🔴 3. Flash-Sale Spike Anomaly (60-95 RPS)`**.
2. Alihkan pandangan dosen ke layar Grafana:
   * Garis ungu **Predicted Workload $t+60$s** langsung melonjak tinggi mendahului trafik riil.
   * Kontroler prediktif langsung menaikkan replika pod dari **1 Pod $\rightarrow$ 6 Pods**.
   * Ketika trafik aktual (garis biru) tiba di puncak $60+\text{ RPS}$, keenam pod sudah berstatus `Ready`!
   * Tunjukkan metrik **P95 Latency** yang tetap stabil di bawah $50\text{ms}$ tanpa ada error HTTP 5xx.

### Langkah 3: Tunjukkan Analisis FinOps & Green Computing (LK-13)
1. Pindah ke tab **"💰 FinOps & Sustainability (LK-13)"** di Streamlit.
2. Tunjukkan kepada penguji:
   * Biaya jika menggunakan over-provisioning statis (6 pod 24/7): **~$100+ USD/bulan**.
   * Biaya dengan Predictive Autoscaler: **~$27 USD/bulan**.
   * Penghematan konkret: **>70% (setara Rp 1.150.000+ per bulan)**.
   * Dampak lingkungan: **Pengurangan emisi karbon ~10.8 kg CO₂e/bulan**.

### Langkah 4: Tunjukkan Tata Kelola MLflow & DVC (LK-05, LK-06, LK-07)
1. Buka `https://mlflow.titipin.me`:
   * Tunjukkan model `predictive-autoscaler` yang aktif dengan tag `@champion` (v8) dan `@challenger` (v7).
   * Perlihatkan metrik perbandingan MAE, RMSE, dan artefak model `model.pkl`.
2. Buka `https://minio.titipin.me`:
   * Tunjukkan hash chunk data DVC yang tersimpan aman di S3.

### Langkah 5: Kembalikan ke Mode Otomatis
1. Di tab Streamlit Injector, klik **`🔄 Kembalikan ke Mode Acak Otomatis`**.
2. Sistem akan kembali beroperasi secara mandiri 24/7.

---

## 🏆 4. Tips Menjawab Pertanyaan Dosen Penguji

1. **T: *"Kenapa tidak pakai HPA bawaan Kubernetes saja?"***  
   *Jawab:* *"HPA bawaan hanya reaktif terhadap rata-rata CPU. Pada runtime PHP-FPM, ada waktu inisialisasi cold-start 30-45 detik. Jika ada flash-sale mendadak, server akan mengalami lonjakan latensi parah dan galat 502/504 sebelum HPA sempat menambah pod. Predictive autoscaler memprediksi beban 60 detik sebelumnya, sehingga pod sudah siap sebelum lonjakan tiba."*

2. **T: *"Bagaimana kalau karakteristik trafik pengguna berubah drastis (Data Drift)?"***  
   *Jawab:* *"Sistem kami dilengkapi algoritma Population Stability Index (PSI). Jika nilai PSI melampaui 0.25, sistem otomatis mengirimkan alert insiden ke Discord/Telegram dan memicu Autonomous Retraining Job di Kubernetes. Model baru dievaluasi otomatis dan jika lolos quality gate, langsung di-hot reload ke memori serving tanpa perlu merestart pod."*

3. **T: *"Apakah penambahan batas 6 pod memerlukan training ulang model?"***  
   *Jawab:* *"Tidak, Pak. Arsitektur kami memisahkan tanggung jawab (Decoupled). Model Machine Learning hanya memprediksi workload dalam satuan RPS, sedangkan jumlah pod dihitung oleh Autoscaling Policy Controller menggunakan formula kapasitas $Pod = \lceil \frac{\text{RPS}}{10} \rceil$ yang dibatasi hingga 6 pod."*
