# Panduan Audit Log Operasional & Telemetri Real-Time

Dokumen ini menjelaskan arsitektur, cara kerja, dan panduan verifikasi dari **Operational Telemetry & Audit Console** yang tersedia pada platform [https://mlops.titipin.me](https://mlops.titipin.me).

Fitur ini dirancang untuk menjawab kebutuhan transparansi tata kelola MLOps (*MLOps Governance & Observability*) tingkat enterprise, khususnya membuktikan empat pilar operasional autoscaling:
1. **Kapan data ingestion terakhir dan bagaimana mekanisme auto-refresh-nya.**
2. **Kapan model retraining terakhir dan bagaimana riwayat versi-versi sebelumnya.**
3. **Kapan API scaling dipanggil dan bagaimana hasil kalkulasi inferensinya.**
4. **Kapan penskalaan pod dilakukan dan scaling ke berapa replika.**

---

## 1. Arsitektur End-to-End Audit Trail

Sistem pelacakan audit bekerja secara terintegrasi antara **Prometheus Operator**, **FastAPI Serving Engine**, **Predictive Scaler Daemon**, dan **Streamlit Control Console**:

```
+--------------------------------------------------------------------------------------------------+
|                                ALIR DATA TELEMETRI & AUDIT TRAIL                                 |
+--------------------------------------------------------------------------------------------------+
                                                                                                    
 [ Caddy Ingress / cAdvisor ]                                                                       
           │ (Scrape RPS, CPU, RAM, P95)                                                            
           ▼                                                                                        
 [ Prometheus Operator (9090) ]                                                                     
           │                                                                                        
           ├────────────────────────────┐                                                           
           ▼ (Every 15s Scrape)         ▼ (15m Rolling Window Ingestion)                            
 [ predictive-scaler Daemon ]    [ Data Ingestion Engine (DVC) ]                                     
   - Ingest current metrics        - Save: metrics_flashsale_drifted.csv                            
   - Calls /scale-decision         - CAS MD5 Hash: 70caf5ea7e6f4e72243ecd8a15e8f4e5                 
           │                       - Remote: MinIO S3 bucket titipin-dvc                            
           ▼                                                                                        
 [ FastAPI inference-api (:8000) ]                                                                  
   - ML Forecast: Predicted RPS (t+60s)                                                             
   - Policy: ceil(Predicted_RPS / 10)                                                               
   - Records into in-memory ring buffers:                                                           
       * scaling_decisions_ring (maxlen=60)                                                         
       * scaling_actions_ring (maxlen=40)                                                           
   - Exposes endpoint: GET /operations/audit                                                        
           │                                                                                        
           ├────────────────────────────┐                                                           
           ▼ (If Replicas Change)       ▼ (HTTP Polling via Fragment)                               
 [ K8s Deployment Patch ]        [ Streamlit Console (mlops.titipin.me) ]                           
   - Deployment: laravel-backend   - Tab: ⏱️ Telemetry & Operational Audit                           
   - Scale: 1 -> 6 Pods Replicas   - Auto-Refresh Fragment (5s, 10s, 15s, 30s)                      
   - Status: APPLIED               - Interactive Tooltips & SRE Badges                              
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Empat Pilar Audit Operasional

### A. Pilar 1: Data Ingestion & Auto-Refresh
* **Tujuan**: Mengetahui kapan data telemetri terakhir ditarik, berapa banyak data yang dikumpulkan, dan memastikan konsol selalu terbarui secara otomatis.
* **Metrik yang Dicatat**:
  - **Waktu Ingestion Terakhir**: `2026-10-02 14:00:00 UTC` (`21:00:00 WIB`).
  - **Window Pengumpulan**: `15 Menit Rolling Window` (Interval agregasi scrape Prometheus).
  - **Volume Data Points**: `250 baris telemetri` (RPS, CPU cores, RAM, latensi P95, lag features).
  - **Target Dataset**: `data/processed/metrics_flashsale_drifted.csv`.
  - **Penyimpanan Objek & DVC**: Tersimpan di MinIO S3 (`s3://titipin-dvc/`) dengan integritas hash MD5 `70caf5ea7e6f4e72243ecd8a15e8f4e5` pada Git tag `v2.0-data`.
  - **Status Pipeline**: `HEALTHY_INGESTED`.
* **Mekanisme Auto-Refresh di UI**:
  - Menggunakan dekorator Streamlit `@st.fragment(run_every=refresh_interval)`.
  - Konsol melakukan pembaruan parsial (*non-blocking partial rerun*) tanpa me-reload seluruh halaman browser sehingga tidak mengganggu interaksi pengguna dengan slider atau tombol lainnya.
  - Tersedia opsi interval refresh: **5 detik**, **10 detik**, **15 detik**, dan **30 detik**, serta tombol manual **🔄 Segarkan Data Sekarang**.

---

### B. Pilar 2: Riwayat Retraining Terakhir & Versi Sebelumnya
* **Tujuan**: Membuktikan kapan model dilatih ulang secara otonom (*Continuous Training*), apa alasannya, dan bagaimana perbandingan performa antar versi di **MLflow Model Registry**.
* **Retraining Terakhir (Champion Model)**:
  - **Versi Model**: `Version 10`
  - **Algoritma**: `Random Forest Regressor` (`n_estimators=100`, `max_depth=8`)
  - **Waktu Retraining**: `2026-10-02 14:00:50 UTC` (`21:00:50 WIB`)
  - **Pemicu Retraining**: `Autonomous CT Job (PSI > 0.25 pada Flash-Sale Spike)`
  - **Akurasi Validasi**: `Validation MAE: 0.0210 RPS` (Galat terendah)
  - **Tahap MLflow**: `@champion (Production)`
  - **Status Serving**: Lolos *Evaluation Gate* dan di-reload secara langsung ke memori RAM (*Zero-Downtime Hot Reload*).
* **Riwayat Retraining Sebelumnya**:

| Versi Model | Waktu Retraining (UTC) | Algoritma Machine Learning | Validation MAE | Tahap MLflow | Pemicu Retraining / Konteks | Status Evaluasi |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **v10** | `2026-10-02 14:00:50` | Random Forest Regressor | **0.0210 RPS** | `@champion (Production)` | Autonomous CT Job (PSI > 0.25) | Lolos & Dipromosikan |
| **v9** | `2026-10-02 14:00:50` | LightGBM Regressor | `0.1246 RPS` | `@challenger (Staging)` | Autonomous Multi-Model Candidate | Disimpan sebagai Challenger |
| **v8** | `2026-10-02 12:20:00` | Random Forest Regressor | `0.0241 RPS` | `Archived` | Flash-Sale Training Run | Digantikan oleh v10 |
| **v7** | `2026-09-30 20:45:00` | LightGBM Regressor | `0.1310 RPS` | `Archived` | Continual Learning Batch 2 | Baseline Candidate |
| **v6** | `2026-09-28 10:30:00` | Ridge / Random Forest | `0.1450 RPS` | `Archived` | Baseline Dataset v1.0 | Initial Production Baseline |

---

### C. Pilar 3: Log Pemanggilan API Scaling (`/scale-decision`)
* **Tujuan**: Mengetahui kapan endpoint inferensi scaling dipanggil oleh controller, apa saja fitur input yang dikirim, dan bagaimana hasil kalkulasi AI-nya.
* **Mekanisme Panggilan**:
  - Daemon `predictive-scaler` berjalan dalam kontainer sidecar pod `mlops-inference` dan mengeksekusi siklus evaluasi setiap **15 detik**.
  - Mengirim snapshot telemetri berupa:
    ```json
    {
      "request_rate": 12.49,
      "php_cpu_cores": 0.075,
      "p95_latency_seconds": 0.0238,
      "php_memory_mb": 130.0,
      "current_replicas": 2
    }
    ```
* **Hasil Kalkulasi yang Dicatat**:
  - `Predicted Workload (t+60s)`: Estimasi laju request 60 detik ke depan.
  - `Desired Replicas`: Hasil formula deterministik $\lceil \text{Predicted\_RPS} / 10 \rceil$ dibatasi batas aman (1 s.d. 6 pod).
  - `Keputusan Aksi`: `SCALE_UP`, `SCALE_DOWN`, atau `MAINTAIN_CAPACITY`.
  - `Inference Latency`: Waktu eksekusi inferensi model di memori RAM (rata-rata **11-15 milidetik**).
* **Buffer Penyimpanan**:
  - Disimpan dalam in-memory ring buffer berkapasitas 60 entri terakhir (`scaling_decisions_ring`) pada servis FastAPI, sehingga dapat ditampilkan secara live di Streamlit tanpa membebani disk.

---

### D. Pilar 4: Log Eksekusi Penskalaan Pod Klaster (Scaling Actions)
* **Tujuan**: Mengetahui kapan penskalaan pod *benar-benar dieksekusi* ke klaster Kubernetes, perubahan jumlah replikanya (dari berapa ke berapa), dan apa alasan kontrolernya.
* **Mekanisme Eksekusi**:
  - Kontroler membandingkan `desired_replicas` dari model AI dengan `current_replicas` yang sedang berjalan di Kubernetes.
  - Jika terjadi perbedaan dan *cooldown window* (60 detik) telah terpenuhi, kontroler mengeksekusi patch deklaratif ke `Deployment/laravel-backend`:
    ```bash
    kubectl scale deployment laravel-backend -n titipin --replicas=<desired_replicas>
    ```
  - Kontroler kemudian mengirimkan log audit ke endpoint `POST /scaling/action-record`.
* **Contoh Riwayat Aksi Penskalaan Aktual**:

| Waktu Eksekusi (UTC) | Aksi Skala | Transisi Pod | Beban Pemicu (RPS) | Alasan Kontroler (*Controller Reason*) | Status Klaster Kubernetes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `2026-10-02 12:20:25` | `SCALE_UP` | `1 ➔ 4 Pods` | 42.8 RPS | Penskalaan proaktif antisipasi jam sibuk | `APPLIED (K8s Patched)` |
| `2026-10-02 12:34:24` | `SCALE_DOWN` | `4 ➔ 1 Pods` | 8.5 RPS | Cooldown period 60s selesai, trafik mereda | `APPLIED (K8s Patched)` |
| `2026-10-02 14:00:58` | `MAINTAIN` | `1 ➔ 1 Pods` | 10.4 RPS | Beban stabil pasca hot-reload model v10 | `STABLE` |
| `2026-10-02 14:03:38` | `SCALE_UP` | `1 ➔ 6 Pods` | 65.2 RPS | Penskalaan darurat lonjakan Flash-Sale Spike | `APPLIED (K8s Patched)` |

---

## 3. Panduan Verifikasi Langsung (CLI & UI)

### 1. Verifikasi Melalui Browser UI (Streamlit)
1. Buka tautan: [https://mlops.titipin.me](https://mlops.titipin.me)
2. Tab pertama: **`⏱️ Telemetry & Operational Audit`**
3. Perhatikan:
   - Status badge di atas: `● AUTO-REFRESH AKTIF (10s)` dan waktu sinkronisasi `WIB`.
   - Empat kartu ringkasan: Ingestion Terakhir, Retraining Terakhir, Total Panggilan API Scaling, dan Aksi Skala Terakhir.
   - Tabel 1: Riwayat Ingestion Batch & Hash DVC MinIO.
   - Tabel 2: Riwayat Retraining Model v10 s.d. v6 di MLflow Registry.
   - Tabel 3: Log Live Pemanggilan `/scale-decision` (akan bertambah otomatis setiap 15 detik).
   - Tabel 4: Log Eksekusi Penskalaan Pod Klaster (menampilkan transisi `1 ➔ 6 Pods` dsb).
4. Coba ubah interval auto-refresh di sidebar kiri menjadi **5 detik** atau matikan toggle untuk mode manual.

### 2. Verifikasi Melalui API Endpoint (cURL)
Jalankan perintah berikut di terminal:
```bash
# Query audit operasional terpadu
kubectl exec -n mlops deploy/mlops-inference -c inference-api -- \
  curl -s http://localhost:8000/operations/audit | jq .

# Query log panggilan API skala terbaru
kubectl exec -n mlops deploy/mlops-inference -c inference-api -- \
  curl -s http://localhost:8000/scaling/decisions | jq .

# Query log eksekusi tindakan penskalaan
kubectl exec -n mlops deploy/mlops-inference -c inference-api -- \
  curl -s http://localhost:8000/scaling/actions | jq .
```

---

## 4. Keunggulan Teknis & Kepatuhan Tata Kelola MLOps

1. **Enterprise Observability**: Menggabungkan metrik performa (*telemetry metrics*), siklus model AI (*model lifecycle*), dan status infrastruktur (*infrastructure orchestration*) ke dalam satu layar kaca tunggal.
2. **Explainability & Accountability**: Setiap keputusan autoscaling memiliki audit trail yang jelas (fitur input, estimasi beban $t+60$s, formula policy, hingga nomor replika pod yang dihasilkan).
3. **Reproducibility**: Setiap batch data ingestion dan model retraining dapat dilacak kembali ke commit hash Git dan MD5 content-addressable storage di MinIO S3.
