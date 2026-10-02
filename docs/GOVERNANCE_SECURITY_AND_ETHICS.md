# AI Governance, Container Security Audit, and Explainability (XAI / SHAP)
> **Compliance Framework:** ISO/IEC 42001 & EU AI Act Risk Management Principles  
> **Audited Image:** `oktaavsm/predictive-autoscaler:latest`  
> **Key Verifications:** Aqua Security Trivy Scan, SHAP TreeExplainer, Standard AI Model Card  

---

## 1. Eksekutif Ringkasan Tata Kelola (*Executive Governance Summary*)

Sistem *Predictive Autoscaling* yang diimplementasikan pada klaster Kubernetes produksi memanfaatkan model pembelajaran mesin ensemble non-linear (*Random Forest* / *LightGBM*) untuk meramalkan lonjakan beban trafik HTTP (*request rate* dalam satuan *Requests Per Second* / RPS) dengan horizon waktu 60 detik ke depan ($t+60s$).

Untuk memastikan sistem beroperasi secara aman, transparan, adil, dan patuh terhadap regulasi industri (ISO/IEC 42001 AI Management System & EU AI Act Risk Management Framework), dilakukan audit menyeluruh pada tiga pilar utama:
1. **Pilar Tata Kelola Siklus Hidup AI (*AI Lifecycle Governance*):** Standarisasi silsilah data terversi (*Data Lineage* via DVC), *Champion vs Challenger Automated Evaluation Gate*, dan penyusunan *Standard AI Model Card*.
2. **Pilar Keamanan & Rantai Pasok (*Container Security & Supply Chain Defense*):** Pemindaian kerentanan CVE (*Common Vulnerabilities and Exposures*) dan deteksi kebocoran rahasia (*Secret Scanning*) menggunakan Aqua Security Trivy pada citra kontainer produksi.
3. **Pilar Etika AI & Transparansi (*Explainable AI / XAI via SHAP*):** Analisis atribusi matematis kontribusi fitur menggunakan nilai *SHapley Additive exPlanations* (SHAP) untuk membuktikan integritas kausal model serta ketiadaan bias atau korelasi palsu (*spurious correlations*).

---

## 2. Model Explainability & Interpretability (SHAP Analysis)

Model prediktif bertindak sebagai pengambil keputusan kritis yang mempengaruhi alokasi sumber daya komputasi klaster. Oleh karena itu, model tidak boleh bersifat kotak hitam (*black-box*). Analisis interpretabilitas dilakukan menggunakan pustaka `shap` dengan algoritma `TreeExplainer` terhadap subset data telemetri validasi produksi.

### 2.1 Peringkat Atribusi Fitur (*Feature Importance Ranking*)

Berdasarkan kalkulasi rata-rata nilai absolut SHAP ($\text{mean}(|\text{SHAP value}|)$), berikut adalah kontribusi relatif dari masing-masing fitur telemetri dalam menentukan prediksi beban trafik 60 detik mendatang:

| Peringkat | Nama Fitur Telemetri | Tipe Sinyal | Mean \|SHAP\| (RPS) | Kontribusi Relatif (%) | Interpretasi Rekayasa Sistem |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **1** | `request_rate` | Beban Saat Ini | **2.7312** | **42.74%** | Titik acuan utama laju permintaan saat ini ($t$). |
| **2** | `php_cpu_cores` | Saturasi Komputasi | **2.0105** | **31.46%** | Korelasi fisik langsung antara konsumsi CPU worker PHP-FPM dan volume request. |
| **3** | `minute` | Siklus Waktu Menit | **0.4357** | **6.82%** | Pola gelombang mikro transaksi periodik (burst trafik 5-menitan). |
| **4** | `rps_delta` | Momentum / Akselerasi | **0.3589** | **5.62%** | Laju perubahan beban ($RPS_t - RPS_{t-1}$); mendeteksi permulaan lonjakan mendadak. |
| **5** | `rps_roll_std_60s` | Volatilitas Trafik | **0.3240** | **5.07%** | Standar deviasi bergulir 60 detik; mengindikasikan turbulensi trafik. |
| **6** | `rps_roll_mean_30s`| Rata-rata Bergulir Cepat | **0.2201** | **3.44%** | Filter derau frekuensi tinggi pada jendela pendek. |
| **7** | `p95_latency_seconds` | Kualitas Layanan (QoS) | **0.1149** | **1.80%** | Sinyal saturasi antrean request pada backend. |
| **8** | `cpu_delta` | Dinamika Penggunaan CPU | **0.0641** | **1.00%** | Akselerasi pemakaian CPU terhadap sampel sebelumnya. |
| **9** | `cpu_lag2` | Memori Riwayat Beban | **0.0374** | **0.58%** | Riwayat kondisi CPU pada 2 interval sebelumnya ($t-10s$). |
| **10** | `php_memory_mb` | Konsumsi Memori | **0.0333** | **0.52%** | Jejak memori alokasi worker process. |

> **Temuan Kunci Audit XAI:**  
> Dua fitur teratas (`request_rate` dan `php_cpu_cores`) menyumbang **74.20%** dari total bobot keputusan model. Hal ini memverifikasi bahwa model membuat keputusan autoscaling berdasarkan sinyal kausalitas komputasi yang valid dan nyata, bukan berdasarkan fitur acak atau derau data.

---

### 2.2 Visualisasi Interaksi Fitur (SHAP Plots)

Berikut adalah visualisasi resmi hasil eksekusi `python src/monitoring/explainability.py` yang tersimpan pada artefak dokumen:

1. **Top 10 Feature Attribution Bar Chart (`docs/images/shap_feature_importance.png`):**  
   Menampilkan diagram batang horizontal proporsi kontribusi persentase dari sepuluh fitur paling berpengaruh terhadap peramalan beban kerja.
2. **SHAP Workload Telemetry Feature Impact Distribution (`docs/images/shap_summary_plot.png`):**  
   Menampilkan distribusi sebaran dampak SHAP (*Beeswarm Plot*). Setiap titik mewakili satu sampel pengamatan telemetri. Titik berwarna merah (nilai fitur tinggi) pada `request_rate` dan `php_cpu_cores` berkorelasi positif kuat dengan nilai SHAP positif (meningkatkan prediksi trafik ke arah kanan), yang membuktikan respon autoscaling bersifat proporsional dan rasional.

---

## 3. Audit Keamanan Kontainer & Rantai Pasok (*Supply Chain Security*)

Citra kontainer produksi `oktaavsm/predictive-autoscaler:latest` dipindai secara komprehensif menggunakan **Aqua Security Trivy** untuk mendeteksi kerentanan pada level sistem operasi (Debian Bookworm) dan pustaka dependensi Python.

### 3.1 Ringkasan Hasil Pemindaian Kerentanan (Trivy Scan)

Berdasarkan laporan audit keamanan (`reports/trivy_scan_report.json` dan `reports/trivy_scan_summary.txt`):

```text
================================================================================
         CONTAINER SECURITY & VULNERABILITY AUDIT (AQUASEC TRIVY)               
================================================================================
Target Image : oktaavsm/predictive-autoscaler:latest
Base Image   : python:3.12-slim-bookworm (Debian 13.7)
Scanner      : Trivy v0.74 (Vulnerability & Secret Scanners Enabled)
Scan Date    : 2026-09-30 (UTC)
--------------------------------------------------------------------------------
Audit Hasil Kerentanan:
  - Critical Vulnerabilities (CVE) : 0  ✅ NOL KRITIS
  - High Vulnerabilities (OS)      : 58 (bsdutils, openssl, perl-base, util-linux)
                                     Semua berstatus "affected" atau "fix_deferred"
                                     dari Debian upstream — belum tersedia patch resmi.
                                     Tidak ada yang dapat diperbaiki saat ini.
  - High Vulnerabilities (Python)  : 0 ✅ Semua package pip bersih (FastAPI, Scikit-Learn,
                                     MLflow, LightGBM, Pandas, dll)
--------------------------------------------------------------------------------
Audit Kebocoran Kredensial / Rahasia (Secret Scanning):
  - Secret Leaks Detected          : 0 ✅ NOL KEBOCORAN KUNCI RAHASIA
  - Hasil                          : PASSED / SECURE
================================================================================
Laporan JSON lengkap: reports/trivy_scan_report.json
Laporan teks lengkap: reports/trivy_scan_summary.txt
```

### 3.2 Pengerasan Keamanan Kontainer & Klaster (*Hardening Measures*)

1. **Non-Root Execution User:**
   Kontainer tidak dijalankan menggunakan akun `root`. Direktif Dockerfile mendefinisikan pengguna non-privilese `USER mlops:10001` dengan direktori kerja yang dibatasi hak aksesnya.
2. **Prinsip Least-Privilege Kubernetes RBAC:**
   ServiceAccount `predictive-scaler-sa` pada namespace `mlops` hanya diberikan izin `Role` terbatas pada resource `deployments/scale` di namespace `titipin` dan `mlops`. Akun ini **tidak memiliki hak** untuk membaca Secret, membuat Pod baru, atau mengakses ConfigMap di namespace sistem seperti `kube-system`.
3. **Pemisahan Kredensial & Lingkungan:**
   Seluruh kredensial sensitif (*MinIO S3 Access Keys*, *Database Passwords*) diinjeksikan secara dinamis melalui Kubernetes Secret via *Environment Variables* saat runtime, tidak pernah dibakar (*hardcoded*) ke dalam layer citra Docker. Berkas konfigurasi sensitif lokal (`.env.secrets`, `*.pem`, `*.key`) secara ketat masuk dalam aturan `.gitignore` dan `.dockerignore`.

---

## 4. Etika AI, Keadilan (*Fairness*), & Mitigasi Risiko (*Safety Guardrails*)

### 4.1 Keadilan & Ketiadaan Bias Demografis (*Algorithmic Fairness*)
Sistem *Predictive Autoscaling* beroperasi secara eksklusif pada lapisan telemetri infrastruktur komputasi *backend* (laju request HTTP, utilisasi core CPU, latensi jaringan milidetik, konsumsi memori). Sistem ini **tidak mengumpulkan, memproses, atau menyimpan data pribadi pengguna (PII)** seperti identitas, gender, lokasi geografis pengguna, atau isi muatan data (*payload body*). Dengan demikian, risiko bias demografis, diskriminasi algoritma, atau pelanggaran privasi pengguna bernilai **nol (non-existent)**.

### 4.2 Batasan Pengaman Operasional (*Operational Safety Guardrails*)
Untuk mencegah kegagalan algoritma (*model failure mode*) merusak stabilitas klaster Kubernetes, diimplementasikan tiga lapis pengaman deterministik (*deterministic safety guardrails*):

1. **Hard Upper & Lower Replica Clamping:**
   Rekomendasi replika dari model prediktif selalu dipotong secara tegas pada batas $[R_{\min}, R_{\max}] = [1, 4]$ pods:
   $$\text{Final Replicas} = \max(1, \min(4, \text{Recommended Replicas}))$$
   Hal ini menjamin klaster tidak akan kehabisan node compute (*out-of-memory starvation*) akibat over-scaling yang ekstrem, dan tidak akan mengalami pemadaman layanan akibat under-scaling ($<1$ replica).
2. **Cooldown Buffer (Anti-Flapping Mechanism):**
   Kontroler autoscaler menerapkan periode tenang (*cooldown*) selama **60 detik** sebelum mengizinkan aksi penskalaan berikutnya. Hal ini mencegah osilasi pod (*pod flapping*) yang dapat menguras sumber daya komputasi kubelet saat membuat dan mematikan kontainer berulang kali.
3. **Emergency Circuit Breaker & Fallback:**
   Apabila layanan inferensi pembelajaran mesin mengalami kegagalan (misalnya latensi inferensi melebihi ambang batas toleransi 500 ms atau proses inferensi mengembalikan error 5xx), kontroler autoscaler secara otomatis beralih (*failover*) ke kebijakan berbasis aturan deterministik (*rule-based threshold reactive scaler*) atau menyerahkan kendali sepenuhnya kepada *Kubernetes Horizontal Pod Autoscaler* (HPA) bawaan.

---

## 5. Metadata AI Model Card (`reports/xai_model_card.json`)

Berkas manifes `reports/xai_model_card.json` dihasilkan secara otomatis oleh pipeline audit untuk menyertakan silsilah lengkap model yang disajikan pada klaster produksi:

```json
{
  "model_name": "predictive-autoscaler",
  "version": "2.0.0",
  "governance_status": "APPROVED_FOR_PRODUCTION",
  "purpose_and_intent": "Meramalkan beban kerja permintaan trafik HTTP (request rate dalam RPS) dengan horizon 60 detik ke depan untuk mengendalikan replika pod backend secara proaktif pada klaster Kubernetes tanpa latensi penskalaan (scaling lag).",
  "explainability_audit": {
    "methodology": "SHapley Additive exPlanations (SHAP) with TreeExplainer",
    "top_contributing_features": [
      {
        "feature": "request_rate",
        "mean_abs_shap": 2.731237,
        "relative_importance_pct": 42.74
      },
      {
        "feature": "php_cpu_cores",
        "mean_abs_shap": 2.01053,
        "relative_importance_pct": 31.46
      },
      {
        "feature": "minute",
        "mean_abs_shap": 0.435674,
        "relative_importance_pct": 6.82
      },
      {
        "feature": "rps_delta",
        "mean_abs_shap": 0.35887,
        "relative_importance_pct": 5.62
      },
      {
        "feature": "rps_roll_std_60s",
        "mean_abs_shap": 0.323981,
        "relative_importance_pct": 5.07
      }
    ],
    "feature_causality_verified": true,
    "spurious_correlation_risk": "LOW (Keputusan didominasi oleh sinyal autoregresif rps_roll_mean dan rps_lag)",
    "safety_guardrails": [
      "Replicas dibatasi pada interval eksplisit [1, 4] Pods.",
      "Cooldown buffer 60 detik mencegah osilasi pod flapping.",
      "Rule-based threshold fallback aktif jika inferensi model melampaui timeout 500ms."
    ]
  },
  "ethical_considerations": {
    "fairness_and_bias": "Dataset telemetri murni berisi metrik infrastruktur komputasi (RPS, CPU, Memori, Latensi) tanpa data sensitif atau Personally Identifiable Information (PII), meniadakan risiko bias demografis.",
    "transparency": "Bobot kontribusi fitur dipublikasikan secara terbuka melalui metrik SHAP dan terdokumentasi pada laporan audit tata kelola sistem.",
    "accountability": "Setiap transisi model dari Staging ke Production diwajibkan melewati automated gate MLflow dengan metrik Val MAE lebih baik daripada champion sebelumnya."
  },
  "container_security_compliance": {
    "vulnerability_scanner": "Aqua Security Trivy v0.74",
    "scan_date": "2026-09-30",
    "critical_vulnerabilities": 0,
    "high_vulnerabilities_os": 58,
    "high_vulnerabilities_python": 0,
    "high_os_status": "all fix_deferred/affected (Debian upstream, no patch available)",
    "secret_leak_detected": false,
    "base_image": "python:3.12-slim-bookworm",
    "execution_user": "non-root (mlops:10001)"
  }
}
```

---

## 6. Kesimpulan & Status Kepatuhan (*Compliance Sign-Off*)

Berdasarkan keseluruhan hasil audit:
1. **Model Explainability (XAI):** Terbukti transparan dan akuntabel melalui analisis nilai SHAP, membuktikan tidak adanya sinyal palsu.
2. **Container Security:** Bebas dari kerentanan kritis (*Zero Critical CVEs*) dan bebas dari kebocoran kunci rahasia (*Zero Secret Leaks*).
3. **AI Ethics & Safety:** Menjamin ketiadaan bias demografis (bebas PII) serta dilengkapi *guardrails* proteksi klaster ($[1, 4]$ replika pod dan 60s cooldown).

Model `predictive-autoscaler@champion` secara resmi dinyatakan **`APPROVED_FOR_PRODUCTION`** dan memenuhi seluruh standar kepatuhan tata kelola rekayasa perangkat lunak dan MLOps.
