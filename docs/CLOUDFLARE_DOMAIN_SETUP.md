# Panduan Konfigurasi Domain Cloudflare & Reverse Proxy Caddy
## Repositori: `oktavsm/predictive-autoscaling-mlops`
### Target Demo Ujian / Sidang Praktikum (LK-05 s/d LK-14)

---

## 1. Arsitektur Domain & Routing Klaster AWS

Seluruh antarmuka grafis (*Web UI*) dan endpoint API diarahkan melalui **Caddy Reverse Proxy** yang berjalan di VM Control Plane klaster K3s AWS. Caddy secara otomatis mengelola sertifikat SSL/TLS (HTTPS) dari Let's Encrypt / ZeroSSL dan meneruskan trafik ke *NodePort Service* Kubernetes di jaringan internal.

```mermaid
flowchart TD
    User["Browser / Client"] -->|"HTTPS (:443)"| CF["Cloudflare DNS & Edge"]
    
    subgraph ControlPlane["AWS Control Plane VM (<CONTROL_PLANE_IP>)"]
        Caddy["Caddy Reverse Proxy (:443)"]
        
        subgraph K3sServices["K3s NodePort Services"]
            SvcLaravel["api.titipin.me ➔ :30080 (Laravel API)"]
            SvcGrafana["grafana.titipin.me ➔ :30300 (Grafana)"]
            SvcMinioAPI["storage.titipin.me ➔ :30900 (MinIO S3 API)"]
            SvcMinioUI["console.titipin.me ➔ :30901 (MinIO Web Console)"]
            SvcMLflow["mlflow.titipin.me ➔ :30500 (MLflow Server)"]
            SvcMLOps["mlops.titipin.me ➔ :30851 (Streamlit / Serving)"]
        end
    end
    
    CF --> Caddy
    Caddy --> SvcLaravel
    Caddy --> SvcGrafana
    Caddy --> SvcMinioAPI
    Caddy --> SvcMinioUI
    Caddy --> SvcMLflow
    Caddy --> SvcMLOps
```

---

## 2. Daftar DNS Record yang Perlu Didaftarkan di Cloudflare

Buka dashboard [Cloudflare](https://dash.cloudflare.com/) ➔ Pilih domain **`titipin.me`** ➔ Masuk menu **DNS** ➔ **Records** ➔ Tambahkan baris record berikut:

| Subdomain | Tipe | IPv4 Target | Proxy Status | Keterangan / Modul Demo |
|---|:---:|---|:---:|---|
| **`api`** | `A` | `<CONTROL_PLANE_IP>` | Proxied (Orange Cloud) | ✅ *Sudah Aktif* (Laravel Backend API) |
| **`grafana`** | `A` | `<CONTROL_PLANE_IP>` | Proxied (Orange Cloud) | ✅ *Sudah Aktif* (Observability Dashboard) |
| **`storage`** | `A` | `<CONTROL_PLANE_IP>` | Proxied (Orange Cloud) | ✅ *Sudah Aktif* (MinIO S3 API / DVC Remote) |
| **`console`** | `A` | `<CONTROL_PLANE_IP>` | **Proxied (Orange Cloud)** | 🌟 **Baru (LK-05 & LK-14):** MinIO Web Console UI |
| **`mlflow`** | `A` | `<CONTROL_PLANE_IP>` | **Proxied (Orange Cloud)** | 🌟 **Baru (LK-06 & LK-07):** MLflow Tracking & Registry UI |
| **`mlops`** | `A` | `<CONTROL_PLANE_IP>` | **Proxied (Orange Cloud)** | 🌟 **Baru (LK-09 s/d LK-14):** Streamlit MLOps Demo Dashboard |

> [!NOTE]
> Ganti `<CONTROL_PLANE_IP>` dengan alamat IP publik asli VM Control Plane Anda (lihat catatan privat di `.env.secrets` atau panduan VM).
> Jika menggunakan opsi **Proxied** di Cloudflare, pastikan pengaturan SSL/TLS di menu **SSL/TLS ➔ Overview** Cloudflare disetel ke mode **Full** (bukan Flexible).

---

## 3. Konfigurasi Caddyfile Terpadu pada Control Plane

Di VM Control Plane, berkas `/etc/caddy/Caddyfile` dapat diperbarui menjadi konfigurasi terpadu berikut:

```caddy
{
    metrics {
        per_host
    }
}

# 1. Laravel E-Commerce Backend (Workload Target)
api.titipin.me {
    reverse_proxy 127.0.0.1:30080
}

# 2. Prometheus & Grafana Observability Dashboard (LK-11 & LK-14)
grafana.titipin.me {
    reverse_proxy 127.0.0.1:30300
}

# 3. MinIO S3 Object Storage API (DVC Remote LK-05)
storage.titipin.me {
    reverse_proxy 127.0.0.1:30900
}

# 4. MinIO Web Console UI (Manajemen Bucket Visual LK-05 & LK-14)
console.titipin.me {
    reverse_proxy 127.0.0.1:30901
}

# 5. MLflow Tracking & Model Registry UI (LK-06 & LK-07)
mlflow.titipin.me {
    reverse_proxy 127.0.0.1:30500
}

# 6. Streamlit MLOps Dashboard & Serving API (LK-09, LK-10, LK-14)
mlops.titipin.me {
    reverse_proxy 127.0.0.1:30851
}

# 7. Edge Telemetry Metrics Exporter untuk Prometheus Scraping
:9180 {
    metrics /metrics
}
```

---

## 4. Langkah Penerapan (*Deployment*) pada Control Plane

Setelah DNS di Cloudflare ditambahkan dan berkas `/etc/caddy/Caddyfile` disimpan:

```bash
# 1. Validasi sintaks Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile

# 2. Terapkan konfigurasi baru tanpa downtime
sudo systemctl reload caddy
# atau: sudo systemctl restart caddy

# 3. Verifikasi status operasional Caddy
sudo systemctl status caddy
```

Dengan langkah di atas, seluruh dashboard praktikum Anda dapat diakses secara publik dan aman via HTTPS untuk demonstrasi di hadapan dosen penguji pada saat presentasi akhir (LK-14).
