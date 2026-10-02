# 🚨 Panduan Observabilitas & Alerting Terintegrasi: Discord & Telegram (LK-11 & LK-13)

Dokumen ini memaparkan arsitektur observabilitas aktif, konfigurasi *PrometheusRule*, dan modul *incident management dispatcher* yang mengirimkan notifikasi insiden operasional klaster secara otomatis ke **Discord Webhook** dan **Telegram Bot**.

---

## 🏗️ 1. Arsitektur Incident Management MLOps

```
   ┌───────────────────────────────────────────────┐
   │       Klaster Kubernetes & Aplikasi           │
   │  - Ingress Latency (P95 > 200ms)              │
   │  - Max Pod Saturation (Replicas >= 6)         │
   │  - Data Drift (PSI > 0.25)                    │
   │  - Retraining & Model Lifecycle Promotion     │
   └───────────────────────┬───────────────────────┘
                           │
                           ▼
   ┌───────────────────────────────────────────────┐
   │     Prometheus Operator & Alert Dispatcher    │
   │      (src/monitoring/alert_dispatcher.py)     │
   └───────────────────────┬───────────────────────┘
                           │
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
   ┌───────────┐                       ┌───────────┐
   │  Discord  │ (Rich Embed Cards)    │ Telegram  │ (HTML / Markdown)
   │  Webhook  │                       │ Bot Alert │
   └───────────┘                       └───────────┘
```

---

## 📋 2. Kategori & Aturan Alert (PrometheusRule)

Aturan alert didefinisikan pada manifest [`infrastructure/monitoring/rules/mlops-alerts.yaml`](file:///home/oktaavsm/Code/github.com/college/predictive-autoscaling-mlops/infrastructure/monitoring/rules/mlops-alerts.yaml) di namespace `monitoring`:

| Nama Alert | Ekspresi PromQL | Tingkat (*Severity*) | Deskripsi Insiden |
|:---|:---|:---:|:---|
| **`MLOpsInferenceServiceDown`** | `up{job="mlops-inference-svc"} == 0` | `Critical` | Pod layanan inferensi FastAPI atau predictive scaler mati selama $> 1\text{m}$. |
| **`MLOpsInferenceHighLatency`** | `histogram_quantile(0.95, ...) > 0.200` | `Warning` | Latensi P95 pada gerbang Ingress Caddy melampaui ambang batas $200\text{ms}$ selama $> 2\text{m}$. |
| **`MLOpsMaxReplicaSaturation`**| `max(kube_deployment_status_replicas) >= 6` | `Warning` | Pod target telah menyentuh batas maksimum kapasitas infrastruktur ($6\text{ Pods}$) selama $> 5\text{m}$. |
| **`MLOpsHighSLOViolationRate`**| `sum(rate(5xx)) / sum(rate(total)) > 0.01` | `Critical` | Tingkat kegagalan HTTP 5xx melebihi $1\%$ dari total request. |

---

## 🛠️ 3. Konfigurasi Dispatcher (`src/monitoring/alert_dispatcher.py`)

Modul `AlertDispatcher` dirancang fleksibel dan dapat dipanggil langsung dari Python code, pipeline retraining, atau terminal CLI:

### A. Environment Variables:
```bash
# Tambahkan ke .env atau Kubernetes Secret jika ingin mengaktifkan webhook nyata:
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRstuVWXyz"
export TELEGRAM_CHAT_ID="-100123456789"
```

### B. Pengujian Manual Dispatcher:
```bash
python3 src/monitoring/alert_dispatcher.py --test
```

Output audit log tersimpan secara persisten dalam format JSON Lines di `logs/alerts_history.jsonl` untuk keperluan audit compliance dan rekam jejak tata kelola AI (**LK-13**).

---

## 💬 4. Contoh Tampilan Notifikasi Insiden

### Format Discord (Rich Embed):
* **Judul:** `🚨 [INCIDENT] High Data Drift Detected (PSI Alert)`
* **Warna:** Deep Orange (`#FF5722`)
* **Fields:**
  * 📊 **PSI Score:** `0.2840` (Threshold: `0.25`)
  * ⚠️ **Drift Level:** Major Distribution Shift
  * 🧬 **Affected Features:** `request_rate, php_cpu_cores, p95_latency_seconds`
  * 🔄 **Automated Action:** ✅ Retraining Triggered

### Format Telegram (Markdown):
```text
🚨 [INCIDENT] High Data Drift Detected

• PSI Score: 0.2840 (Threshold: 0.25)
• Features: request_rate, php_cpu_cores, p95_latency_seconds
• Action: Triggering Autonomous Retraining...
• Dashboard: https://grafana.titipin.me
```

---

## 🎓 5. Nilai Akademis untuk Lembar Kerja

* **LK-11 (Observability & Alerting):** Memenuhi standar SRE industri (*Site Reliability Engineering*) dengan menghubungkan metrik pasif ke kanal komunikasi aktif tim engineering.
* **LK-13 (Governance & Security Audit):** Menyediakan berkas audit insiden terstruktur (`logs/alerts_history.jsonl`) yang membuktikan transparansi, akuntabilitas, dan keterlacakan anomali pada sistem AI produksi.
