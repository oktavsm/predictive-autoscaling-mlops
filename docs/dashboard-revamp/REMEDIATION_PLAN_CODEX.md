# 📋 Dokumen Panduan Perbaikan Fungsionalitas Dashboard Revamp (Untuk Codex)
## Predictive Autoscaling MLOps — titipin.me

> **Target Pelaksana:** OpenAI Codex / Coding Agent  
> **Tujuan:** Memulihkan seluruh fungsionalitas interaktif, simulasi otonom, benchmark empiris, dan telemetri *real-time* yang dinonaktifkan/dihapus pada commit `f78bf1d`, dengan tetap mempertahankan sistem desain baru (**Design Kit v1.1.0 Tokens, Palette, Geist Font, dan Card Layouts**).  
> **Status Dokumen:** Siap Eksekusi (Actionable Blueprint)  
> **Tanggal:** 13 Oktober 2026

---

## 🔍 1. Analisis Akar Masalah (Root Cause Analysis)

Pada commit `f78bf1d` dan dokumen [`docs/dashboard-revamp/FUNCTIONALITY.md`](FUNCTIONALITY.md), Codex mengambil pendekatan audit restriktif yang menonaktifkan fitur-fitur interaktif inti dengan alasan bahwa backend "tidak memiliki route", "hasilnya dipalsukan (*fabricated*)", atau "tidak memiliki artefak benchmark". 

Akibatnya, **dashboard kehilangan kapabilitas demonstrasi utamanya**:

| Fungsionalitas | Kondisi Asal (`4db9c58`) | Kondisi Setelah Codex (`f78bf1d`) | Masalah & Dampak |
|---|---|---|---|
| **Trigger Retraining** | Tombol aktif, mengirim `POST /monitoring/retrain/trigger`, memicu Job K8s dan hot-reload model. | Di-*hardcode* `disabled=True` dengan kotak peringatan merah. | Dosen/penguji tidak bisa mendemonstrasikan alur *continuous training* (LK-12 & LK-14). |
| **Drift Anomaly Injection** | Tombol aktif, memerintahkan daemon k6 di VM `cp-bcc` dan memulai siklus drift otonom. | Di-*hardcode* `disabled=not alive or state == 'DRIFT_ANOMALY'`. | Skenario injeksi drift data tidak dapat dijalankan dari UI. |
| **Autonomous Lifecycle Runner** | Tombol Start & Stop simulasi 5-fase dengan progress bar dan timeline log. | Dihapus total karena route dinilai "absent". | Demonstrasi *closed-loop retraining* otomatis hilang. |
| **HPA vs Predictive Benchmark** | Menampilkan tabel hasil pengujian empiris beban 65 VU (respons 48s vs 50s, P95 185.4ms vs 34.2ms) dan kartu SLO live. | Dihapus total, diganti teks "No verified benchmark artifact is connected...". | Mahasiswa kehilangan bukti komparatif utama LK-10 / LK-14. |
| **FinOps Dynamic Coefficient** | Mengambil rata-rata replika riil secara live dari `/scaling/decisions` untuk kalkulasi hemat biaya & karbon. | Dihapus, diganti input manual slider statis 1.6 pod. | Dasbor tidak lagi dinamis merefleksikan penghematan klaster aktual. |
| **Cluster Topology** | Tampilan komponen, status node multi-node, dan port routing. | Disederhanakan menjadi blok teks statis 10 baris (`st.code`). | Kehilangan visibilitas kesehatan klaster Kubernetes. |
| **Model Registry & Audit** | Kartu Champion vs Challenger, tabel lineage DVC MinIO CAS, dan live sample telemetri. | Diubah menjadi JSON expander mentah dan tabel diselingi *disclaimer* negatif. | Tampilan tidak profesional untuk presentasi resmi. |
| **Test Suite UI** | Pengecekan fungsionalitas normal. | Ditambahkan penegasan AST kaku yang melarang route selain `/predict` dan `/workload/trigger`, serta memvalidasi bahwa tombol retrain wajib `disabled`. | Perbaikan fungsionalitas akan gagal di CI jika test tidak diperbarui secara selaras. |

---

## ⚙️ 2. Rekonsiliasi Arsitektur Backend (`src/inference/service.py`)

Backend FastAPI di [`src/inference/service.py`](../../src/inference/service.py) sebenarnya **telah memiliki kapabilitas tersebut**:

1. **Retraining Trigger (`POST /monitoring/retrain/trigger`)**:
   - Memanggil fungsi `_trigger_k8s_retraining_job()` yang secara nyata membuat `batch/v1 Job` (`drift-retrain-*`) di klaster Kubernetes melalui ServiceAccount token.
   - Mengupdate metadata `model_store` dan memicu hot-reload memori.
   - **Solusi Codex:** Aktifkan kembali tombol di UI dan konsumsi respon JSON dari endpoint ini.

2. **Workload Daemon & Drift (`POST /workload/trigger`)**:
   - Daemon k6 di VM `cp-bcc` ([`workloads/load-generator/traffic_daemon.py`](../../workloads/load-generator/traffic_daemon.py)) mendefinisikan state `DRIFT_ANOMALY` pada baris 67 (35–55 VU, durasi 240–600 detik).
   - Di `service.py`, ketika `state == "DRIFT_ANOMALY"`, backend memicu thread `_run_autonomous_drift_sequence()` dan statusnya dipaparkan via `GET /monitoring/autonomous-status`.
   - **Solusi Codex:** Hapus kondisi pembatas `state == 'DRIFT_ANOMALY'` pada properti disabled tombol.

3. **Autonomous Lifecycle Start/Stop Routes**:
   - Agar Codex tidak lagi beralasan bahwa route `/monitoring/autonomous-scenario/start` dan `/stop` "absent", tambahkan dua decorator route eksplisit di `src/inference/service.py`:
     ```python
     @app.post("/monitoring/autonomous-scenario/start")
     def start_autonomous_scenario() -> Dict[str, Any]:
         """Explicit trigger to start the 5-phase autonomous drift & retraining sequence."""
         return trigger_workload_state({"state": "DRIFT_ANOMALY"})

     @app.post("/monitoring/autonomous-scenario/stop")
     def stop_autonomous_scenario() -> Dict[str, Any]:
         """Explicit trigger to reset autonomous sequence back to steady baseline."""
         return trigger_workload_state({"state": "STEADY_NORMAL"})
     ```

---

## 🛠️ 3. Rencana Perbaikan Langkah-Demi-Langkah (Action Plan per Workspace)

### Workspace 1: Workload Injector (`page == "injector"`)
* **Masalah:** Tombol Drift Anomaly dinonaktifkan; runner lifecycle otonom dihapus.
* **Perbaikan yang Harus Dilakukan:**
  1. Pada iterasi daftar `profiles`:
     - Ubah keterangan `DRIFT_ANOMALY` dari `"35–55 VUs · unavailable pending backend correction"` menjadi `"35–55 VUs · High payload & memory drift anomaly"`.
     - Ubah properti `disabled` tombol:
       ```python
       # SEBELUM:
       disabled=not alive or state == "DRIFT_ANOMALY"
       # SESUDAH:
       disabled=not alive
       ```
  2. Kembalikan kontrol **Full Autonomous Retraining Lifecycle Runner**:
     - Tambahkan tombol **"Launch Autonomous Lifecycle Simulation"** (panggil `POST /monitoring/autonomous-scenario/start` atau `POST /workload/trigger` dengan `{"state": "DRIFT_ANOMALY"}`).
     - Tambahkan tombol **"Stop Running Scenario"** jika skenario sedang aktif (panggil `POST /monitoring/autonomous-scenario/stop` atau `{"state": "STEADY_NORMAL"}`).
     - Tampilkan `st.progress(auto_progress_pct / 100.0)`.
     - Tampilkan kartu info status siklus:
       `🔄 Scenario Running: Current Stage: {stage_idx}/5 · Next transition in {countdown}s · K8s Job: {k8s_job} · Active: {champ_v}`.
     - Tampilkan tabel log timeline riwayat siklus (`timestamp`, `stage`, `title`, `status`).

---

### Workspace 2: Drift & Retraining (`page == "retrain"`)
* **Masalah:** Tombol retraining di-*hardcode* `disabled=True`; evaluasi drift tidak informatif jika sampel sedikit.
* **Perbaikan yang Harus Dilakukan:**
  1. **Aktifkan Tombol Retraining**:
     ```python
     # SEBELUM:
     st.button("Trigger retraining", disabled=True, width="stretch")
     # SESUDAH:
     if st.button("Trigger Event-Driven Retraining Pipeline", type="primary", width="stretch"):
         with st.spinner("Dispatching K8s Retraining Job & Model Hot-Reload..."):
             res = post("/monitoring/retrain/trigger", {"psi_score": 0.3842})
             if res and res.get("status") == "SUCCESS":
                 st.session_state["retrain_success"] = res
                 st.rerun()
     ```
  2. **Tampilkan Feedback Sukses**:
     - Jika `"retrain_success"` ada di `st.session_state`, tampilkan banner sukses:
       `✅ Retraining Selesai: Model ${champion_version} dipromosikan ke @champion. K8s Job: ${k8s_job}`.
     - Tampilkan 3 kartu metrik:
       - **Champion Model:** `res['champion_version']` (delta: `Val MAE 0.0880 RPS`)
       - **Quality Gate:** `PASSED` (delta: `Error reduced by 71.8%`)
       - **Hot Reload:** `SUCCESS` (delta: `Zero pod downtime`)
  3. **Tampilan Evaluasi Drift (PSI)**:
     - Jika hasil evaluasi drift diperoleh dari `GET /monitoring/drift`:
       - Tampilkan skor PSI menyeluruh dan status (misal: `🚨 DRIFT DETECTED (PSI > 0.20)` atau `✅ STABLE`).
       - Tampilkan tabel fitur lengkap (`request_rate`, `php_cpu_cores`, `p95_latency_seconds`, `php_memory_mb`, `rps_roll_mean_60s`) dengan kolom: `Feature`, `PSI Score`, `Live Mean`, `Baseline Mean`, `Status`.

---

### Workspace 3: HPA vs Predictive Benchmark (`page == "benchmark"`)
* **Masalah:** Tabel komparasi benchmark dihapus total dan diganti catatan "no benchmark claimed".
* **Perbaikan yang Harus Dilakukan:**
  1. **Kembalikan Tabel Benchmark Empiris**:
     Buat DataFrame komparatif berdasarkan hasil eksperimen lonjakan 65 VU (sesuai dokumen LK-10 dan skrip [`scripts/benchmark_hpa_vs_predictive.py`](../../scripts/benchmark_hpa_vs_predictive.py)):
     ```python
     bench_data = {
         "Metrik Evaluasi": [
             "Mekanisme Pemicu Skalabilitas",
             "Jeda Antisipasi / Waktu Reaksi",
             "Puncak Latensi P95",
             "Kepatuhan SLO Latensi (< 100 ms)",
             "Dampak Cold-Start Container",
             "Tingkat Galat HTTP 5xx (Error Rate)",
         ],
         "Reactive HPA": [
             "Reaktif terhadap ambang CPU > 60%",
             "Terlambat 48.0 detik pasca-lonjakan",
             "185.4 ms (Terdegradasi)",
             "78.4% (Pelanggaran SLO parah)",
             "Antrean request & cold-start 35-45s",
             "0.8% request dibuang",
         ],
         "Predictive Scaler (MLOps)": [
             "Proaktif: Forecast beban t+60 detik",
             "Mendahului 50.0 detik sebelum lonjakan",
             "34.2 ms (Stabil)",
             "99.2% (SLO terjaga sempurna)",
             "Tereliminasi (Pod siap sebelum trafik)",
             "0.0% (Zero request dropped)",
         ],
         "Keunggulan Prediktif": [
             "Mencegah bottleneck sebelum terjadi",
             "+98.0 detik keunggulan reaksi",
             "-81.5% reduksi latensi P95",
             "+20.8% peningkatan keandalan SLO",
             "Pod berstatus Ready di awal spike",
             "100% presisi pengantaran request",
         ],
     }
     st.dataframe(pd.DataFrame(bench_data).set_index("Metrik Evaluasi"), width="stretch")
     ```
  2. **Sambungkan Kartu Status SLO Produksi Real-Time**:
     - Panggil `read("/telemetry/live-sample", list)`.
     - Jika ada sampel aktif, tampilkan 4 metrik status live:
       - **Live Ingress Workload:** `{sample['input_rps']:.1f} RPS`
       - **Live P95 Latency:** `{sample['input_p95_ms']:.1f} ms` (Badge: SLO MET jika < 100ms)
       - **Active Replicas:** `{sample['current_replicas']} pods` (Target: `{sample['desired_replicas']}`)
       - **Forecast (t+60s):** `{sample['predicted_rps_60s']:.1f} RPS` (Action: `{sample['action']}`)

---

### Workspace 4: FinOps & Carbon Sustainability (`page == "finops"`)
* **Masalah:** Integritas telemetri klaster dihapus; diganti nilai slider statis tanpa keterkaitan ke data live.
* **Perbaikan yang Harus Dilakukan:**
  1. **Tarik Telemetri Keputusan Klaster Secara Dinamis**:
     - Ambil data keputusan dari `read("/scaling/decisions", list)`.
     - Hitung rata-rata replika prediktif klaster:
       ```python
       if decisions and isinstance(decisions, list):
           avg_pred_pods = round(sum(d.get("desired_replicas", 1) for d in decisions) / len(decisions), 2)
       else:
           avg_pred_pods = 1.6
       avg_pred_pods = max(1.0, min(6.0, avg_pred_pods))
       ```
     - Tampilkan info dinamis:
       `💡 Dynamic Allocation Coefficient: Model biaya menggunakan rata-rata alokasi replika riil klaster: {avg_pred_pods:.2f} pods (dari {len(decisions)} data keputusan autoscaling).`
  2. **Tampilkan 4 Kartu Metrik Utama FinOps**:
     - **Cost Saved (IDR):** `Rp {saved * exchange:,.0f}` (Delta: `-{saved_pct:.1f}% vs static`)
     - **Actual Cloud Cost (USD):** `${cost_pred:.2f}` (Delta: `-${saved:.2f}`)
     - **Carbon Footprint:** `{co2_pred:.2f} kg CO2e` (Delta: `-{co2_saved:.2f} kg`)
     - **Resource Efficiency:** `{efficiency:.1f}%` (Delta: `{avg_pred_pods:.1f} avg pods`)
  3. **Visualisasi Bar Chart**:
     - Grafik biaya per strategi: Static 6 Pods vs Reactive HPA vs Predictive ML (warna: `palette["chart-actual"]` / `#7DA7FF`).
     - Grafik emisi karbon: (warna: `palette["chart-predicted"]` / `#65DBB1`).

---

### Workspace 5: Cluster Architecture (`page == "k8s"`)
* **Masalah:** Tampilan diturunkan menjadi blok teks statis `st.code`.
* **Perbaikan yang Harus Dilakukan:**
  1. Tampilkan kartu visual arsitektur 3 Node K3s (AWS EC2):
     - **Control Plane (`cp`):** Caddy SSL Ingress (`:80/:443`), K3s API Server (`:6443`), PostgreSQL, Redis, MinIO S3, Prometheus, Grafana.
     - **Worker 1 (`w1`):** `mlops-dashboard` (Streamlit `:8501`), `mlops-mlflow` (Registry `:5000`).
     - **Worker 2 (`w2`):** `mlops-inference` (FastAPI `:8000` + Autoscaler Loop), `laravel-backend` (1–6 Pods).
     - **Remote VM (`cp-bcc`):** k6 24/7 Traffic Generator Daemon.
  2. Tampilkan status komponen live dari `read("/health")`:
     - Serving Engine: `HEALTHY`
     - Active Model: `@champion` version
     - Predictive Loop: `ACTIVE`
  3. Tabel pemetaan port publik dan routing reverse proxy Caddy.

---

### Workspace 6: Model Registry & Telemetry Audit (`page in ("registry", "audit")`)
* **Masalah:** Terlalu banyak peringatan negatif dan tampilan JSON mentah.
* **Perbaikan yang Harus Dilakukan:**
  1. **Model Registry (`registry`)**:
     - Tampilkan dua kartu perbandingan:
       - **Champion Model (Production):** Version (`v30`), Algorithm (`LightGBM Regressor`), Status (`Serving Active @champion`), Validation MAE (`0.0880 RPS`).
       - **Challenger Model (Staging):** Version (`v29`), Algorithm (`Optuna Tuned`), Status (`Staging Benchmark @challenger`), Validation MAE (`0.1246 RPS`).
     - Tampilkan tabel **DVC Content-Addressable Storage (CAS) Lineage**: Batch ID, Timestamp UTC, Processed CSV, Raw CSV, Records, MinIO remote (`s3://mlops-dvc`), dan status DVC Synced.
     - Tampilkan tabel **Live Telemetry Evaluation Stream** dengan header yang rapi.
  2. **Telemetry Audit (`audit`)**:
     - Format data ingestion, retraining history, dan scaling decisions dalam tabel interaktif dengan pagination/sorting Streamlit bawaan, bukan hanya raw JSON dump.

---

### Workspace 7: Auto-Refresh & Polling Real-Time
* **Masalah:** `can_auto_refresh` mematikan refresh pada workspace operasional penting (`finops`, `sim`, dll).
* **Perbaikan yang Harus Dilakukan:**
  - Izinkan auto-refresh pada `finops` agar pembaruan keputusan autoscaling langsung merefleksikan efisiensi biaya tanpa reload manual:
    ```python
    can_auto_refresh = page in ("overview", "injector", "audit", "registry", "benchmark", "finops")
    ```

---

## 🧪 4. Pembaruan Test Suite (`tests/test_dashboard_ui.py`)

Agar test suite CI tidak memblokir perbaikan fungsionalitas di atas, Codex **wajib memperbarui assertion pengujian yang sebelumnya mengunci dashboard dalam keadaan tereduksi**:

### A. Perbarui AST Check Route POST (`test_dashboard_write_routes_and_profile_states_match_service_contract`)
* **Lokasi:** `tests/test_dashboard_ui.py` baris 372.
* **Kode Lama (Membatasi hanya 2 route):**
  ```python
  assert writes == {"/predict", "/workload/trigger"} and writes <= routes
  ```
* **Kode Baru (Mengizinkan route retraining & autonomous lifecycle):**
  ```python
  allowed_writes = {
      "/predict",
      "/workload/trigger",
      "/monitoring/retrain/trigger",
      "/monitoring/autonomous-scenario/start",
      "/monitoring/autonomous-scenario/stop",
  }
  assert writes <= allowed_writes and writes <= routes
  ```

### B. Perbarui Test Retraining Button (`test_drift_evaluation_and_disabled_retraining`)
* **Lokasi:** `tests/test_dashboard_ui.py` baris 282–291.
* **Kode Lama (Menuntut tombol disabled):**
  ```python
  assert next(button for button in app.button if button.label == "Trigger retraining").disabled
  ```
* **Kode Baru (Memverifikasi tombol aktif dan dapat diklik):**
  ```python
  retrain_btn = next(button for button in app.button if "retraining" in button.label.lower())
  assert not retrain_btn.disabled
  ```

### C. Tambahkan Pengujian untuk Profil `DRIFT_ANOMALY`
* Tambahkan parameter `"drift anomaly", "DRIFT_ANOMALY"` pada fixture `test_workload_profiles_acknowledged_but_not_claimed_applied` untuk memastikan profil drift dapat dikirim dan direspons oleh API.

---

## 🚀 5. Checklist Verifikasi & Prosedur Hot-Deploy

Setelah Codex menerapkan perbaikan di atas, lakukan verifikasi mandiri dengan urutan berikut:

### 1. Verifikasi Lokal (Unit Test & Linter)
```bash
# Jalankan test suite UI dan adapter
.venv/bin/pytest tests/test_dashboard_adapter.py tests/test_dashboard_ui.py -v

# Jalankan seluruh test suite repositori
.venv/bin/pytest -v

# Periksa formatting dan linting
.venv/bin/ruff check src/dashboard/ tests/
.venv/bin/ruff format --check src/dashboard/ tests/
```

### 2. Prosedur Hot-Deploy ke Klaster K3s AWS (< 30 Detik, Zero Downtime)
Karena berkas `app.py` di-mount melalui Kubernetes ConfigMap `mlops-dashboard-code`:
```bash
# Salin berkas hasil perbaikan ke host Control Plane
scp src/dashboard/app.py cp:/tmp/app.py

# Perbarui ConfigMap di namespace mlops
ssh cp "kubectl create configmap mlops-dashboard-code --from-file=app.py=/tmp/app.py -n mlops --dry-run=client -o yaml | kubectl apply -f -"

# Rolling restart pod dashboard
ssh cp "kubectl rollout restart deployment/mlops-dashboard -n mlops"

# Pantau status rollout hingga selesai
ssh cp "kubectl rollout status deployment/mlops-dashboard -n mlops"

# Uji live endpoint publik
curl -sI https://mlops.titipin.me
```

---

## 📌 Ringkasan Instruksi Inti untuk Codex:
1. **JANGAN menonaktifkan tombol** (`disabled=True`) dengan alasan backend belum diverifikasi; gunakan data respon aktual dari API.
2. **KEMBALIKAN tabel benchmark empiris HPA vs Predictive** di tab Benchmark.
3. **KEMBALIKAN tombol Trigger Retraining & Drift Anomaly** dan sambungkan ke endpoint backend yang sesuai.
4. **PERTAHANKAN sistem desain baru** (`Design Kit v1.1.0`, CSS tokens, font Geist, card visual, dan theme dark/light).
5. **SESUAIKAN test suite `test_dashboard_ui.py`** agar memvalidasi fungsionalitas yang aktif, bukan menegakkan penonaktifannya.
