# Infrastructure Setup Guide

Panduan ini berisi langkah-langkah *step-by-step* untuk mempersiapkan 3 VM laboratorium (1 Control Plane, 2 Worker), melakukan setup cluster Kubernetes, dan men-deploy aplikasi backend (Laravel).

## 1. Akses dan Persiapan VM

Diasumsikan kamu sudah mendapatkan IP Publik dan Port untuk masing-masing VM (karena akses SSH menggunakan port khusus).

- **VM-01 (Control Plane):** `IP_ADDRESS`, `PORT_CP`
- **VM-02 (Worker 1):** `IP_ADDRESS`, `PORT_W1`
- **VM-03 (Worker 2):** `IP_ADDRESS`, `PORT_W2`

Untuk masuk ke setiap VM, gunakan perintah SSH berikut di terminal lokalmu:
```bash
# Contoh akses ke Control Plane
ssh -p <PORT_CP> username@<IP_ADDRESS>
```
Lakukan *update package* di ketiga VM setelah kamu berhasil login:
```bash
sudo apt update && sudo apt upgrade -y
```

## 2. Install Kubernetes (Menggunakan K3s)

Karena spesifikasi worker VM cukup terbatas (1 vCPU, 1GB RAM), sangat disarankan menggunakan **K3s** (Lightweight Kubernetes dari Rancher).

### A. Setup Control Plane (di VM-01)
Jalankan perintah ini di VM-01:
```bash
curl -sfL https://get.k3s.io | sh -
```
Tunggu sampai selesai. Pastikan node siap dengan:
```bash
sudo k3s kubectl get nodes
```
Ambil **Node Token** dari Control Plane (token ini akan digunakan untuk menggabungkan worker):
```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```
Catat token tersebut dan catat juga **IP Internal/Private** dari VM-01. Jika VM di-host di network yang sama, IP Private lebih baik digunakan. Jika tidak, gunakan IP Publik.

### B. Setup Worker Nodes (di VM-02 & VM-03)
Jalankan perintah ini di VM-02 dan VM-03:
```bash
curl -sfL https://get.k3s.io | K3S_URL=https://<IP_VM_01>:6443 K3S_TOKEN=<TOKEN_DARI_VM_01> sh -
```
*(Ganti `<IP_VM_01>` dengan IP Control Plane dan `<TOKEN_DARI_VM_01>` dengan token yang dicatat sebelumnya).*

Kembali ke VM-01, verifikasi apakah ketiga node sudah bergabung:
```bash
sudo k3s kubectl get nodes
```
*(Output harus menampilkan 1 control-plane dan 2 worker node dengan status `Ready`)*.

---

## 3. Persiapan Deployment Backend (Laravel)

Repositori backend yang digunakan adalah: `git@github.com:titip-in/titip-in-web.git`

### A. Clone Repository Backend
Disarankan melakukan ini di komputer lokal kamu (atau di Control Plane jika kamu mengelola Kubernetes langsung dari sana).
```bash
git clone git@github.com:titip-in/titip-in-web.git
cd titip-in-web
```

### B. Containerize Aplikasi (Pembuatan Docker Image)
Aplikasi Laravel harus dibungkus menjadi Docker Image agar bisa dijalankan di Kubernetes.
Jika `titip-in-web` belum memiliki `Dockerfile`, kamu harus membuatnya. 

Contoh instruksi *build*:
```bash
# Build image
docker build -t namamu/titip-in-web:latest .

# Push image ke Docker Hub (atau Container Registry lain)
docker push namamu/titip-in-web:latest
```
*(Catatan: Worker node K3s nantinya akan men-download image ini dari registry, jadi pastikan image berstatus publik atau gunakan pull secret jika private).*

### C. Deploy ke Kubernetes
Buat file manifest Kubernetes (misal: `deployment.yaml`) di folder `infrastructure/kubernetes/` repository **ini** (bukan di repo aplikasi):

**infrastructure/kubernetes/laravel-deployment.yaml**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: laravel-backend
  labels:
    app: titip-in-web
spec:
  replicas: 2
  selector:
    matchLabels:
      app: titip-in-web
  template:
    metadata:
      labels:
        app: titip-in-web
    spec:
      containers:
      - name: laravel-app
        image: namamu/titip-in-web:latest # Ganti dengan image kamu
        ports:
        - containerPort: 80
        env:
        - name: APP_ENV
          value: "production"
        # Tambahkan environment DB, Redis, dll sesuai kebutuhan
---
apiVersion: v1
kind: Service
metadata:
  name: laravel-service
spec:
  selector:
    app: titip-in-web
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
  type: LoadBalancer
```

Terapkan (apply) konfigurasi tersebut ke Kubernetes melalui VM-01:
```bash
sudo k3s kubectl apply -f laravel-deployment.yaml
```

Cek status Pods dan Service:
```bash
sudo k3s kubectl get pods
sudo k3s kubectl get svc
```

## 4. Next Step
Setelah aplikasi berjalan:
1. **Setup Database**: Apakah database jalan di dalam Kubernetes atau eksternal?
2. **Install Prometheus & Grafana** untuk mulai mengumpulkan metrik operasional aplikasi ini yang nanti dibutuhkan untuk model *Predictive Autoscaling*.
