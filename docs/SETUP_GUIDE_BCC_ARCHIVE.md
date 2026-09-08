> ⚠️ **ARCHIVED** — Versi ini menggunakan VM lab BCC (`proxy.bccdev.id:11049`) sebagai Control Plane.
> CP tersebut berada di balik NAT kampus sehingga port K3s (6443) tidak bisa diakses dari Worker AWS.
> Gunakan [SETUP_GUIDE.md](./SETUP_GUIDE.md) (versi Full AWS) sebagai panduan utama.

# Setup Guide — Predictive Autoscaling MLOps (BCC Control Plane — ARCHIVED)

> **Goal:** dari VM kosong sampai sistem berjalan dan data bisa dikumpulkan:
>
> - cluster K3s 3 node aktif;
> - backend Laravel Titip.In berjalan sebagai Kubernetes workload di worker;
> - PostgreSQL, Redis, dan MinIO tersedia sebagai dependency;
> - `api.titipin.me` dapat diakses;
> - Prometheus + Grafana aktif;
> - metrik request rate, latency, CPU, memory, dan replica count tersedia;
> - workload dapat digenerate dengan k6;
> - data time-series dapat diekspor menjadi CSV sebagai bahan awal Machine Learning;
> - reactive HPA dapat ditunjukkan sebagai baseline sebelum predictive autoscaling dibuat.
>
> Guide ini sengaja dibuat **demo-first** dan **MLOps-consistent**. Fokusnya bukan production hardening penuh, tetapi membuat arsitektur yang benar secara metodologis dan cukup stabil untuk ditunjukkan bersama proposal.

---

# 0. Arsitektur Akhir

## 0.1 Infrastruktur

| Node | Role | Access | CPU | RAM | Storage |
|---|---|---|---:|---:|---:|
| VM-01 | K3s control plane + monitoring + stateful demo services | `proxy.bccdev.id:11049`, user `dev` | 2 core | 4 GB | 20 GB |
| VM-02 | K3s worker | `15.232.116.101`, user `ubuntu` | 2 core | 2 GB | 20 GB |
| VM-03 | K3s worker | `15.232.71.54`, user `ubuntu` | 2 core | 2 GB | 20 GB |

## 0.2 Logical Architecture

```text
                    External Client / k6
                            │
                            ▼
                    api.titipin.me
                            │
                          Caddy
                            │
                            ▼
                  Kubernetes NodePort
                            │
                            ▼
               laravel-backend Deployment
                    replicas = 1..N
                 ┌──────────┴──────────┐
                 ▼                     ▼
              Worker-1              Worker-2
            Nginx + PHP-FPM       Nginx + PHP-FPM
                 │                     │
                 └──────────┬──────────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
          PostgreSQL       Redis           MinIO
          fixed pod       fixed pod       fixed pod
              │
              ▼
        operational metrics
              │
              ▼
     kube-prometheus-stack
 ┌────────────┼─────────────┐
 ▼            ▼             ▼
Prometheus  Grafana   kube-state-metrics
                          +
                    kubelet/cAdvisor
                          +
                    node-exporter

Prometheus
    │
    ▼
Prometheus HTTP API
    │
    ▼
Time-Series CSV
    │
    ▼
EDA / ML Pipeline
```

## 0.3 Kenapa backend dibuat sebagai pod Nginx + PHP-FPM?

Repository Titip.In saat ini memang memisahkan image:

```text
ghcr.io/titip-in/titip-in-web-web
ghcr.io/titip-in/titip-in-web-app
```

Image Nginx existing mengarahkan FastCGI ke hostname `php:9000`, karena awalnya dibuat untuk Docker Compose.

Di Kubernetes, guide ini menjalankan Nginx dan PHP-FPM sebagai **dua container dalam satu Pod**, lalu Nginx dikonfigurasi ulang menjadi:

```text
fastcgi_pass 127.0.0.1:9000;
```

Dengan cara ini satu replica Kubernetes merepresentasikan satu unit backend:

```text
Replica 1 = Nginx + PHP-FPM
Replica 2 = Nginx + PHP-FPM
...
```

Ini jauh lebih bersih untuk eksperimen autoscaling.

---

# 1. Pre-flight Checklist

Sebelum install apa pun, pastikan network antar-node benar.

## 1.1 SSH config di laptop

Edit:

```bash
nano ~/.ssh/config
```

Isi:

```sshconfig
Host cp
  HostName proxy.bccdev.id
  Port 11049
  User dev
  IdentityFile ~/.ssh/id_ed25519

Host w1
  HostName 15.232.116.101
  User ubuntu
  IdentityFile ~/.ssh/id_ed25519

Host w2
  HostName 15.232.71.54
  User ubuntu
  IdentityFile ~/.ssh/id_ed25519
```

Test:

```bash
ssh cp "echo CP_OK"
ssh w1 "echo W1_OK"
ssh w2 "echo W2_OK"
```

---

## 1.2 Tentukan alamat control plane yang dapat dicapai worker

SSH ke CP:

```bash
ssh cp
ip -br addr
hostname -I
curl -4 -s ifconfig.me || true
```

Catat kandidat alamat CP.

Kita sebut sebagai:

```text
<CP_K3S_ADDR>
```

**Alamat ini harus dapat diakses dari W1 dan W2 pada TCP 6443.**

Jangan otomatis memakai `proxy.bccdev.id`, karena port SSH `11049` hanya membuktikan bahwa proxy meneruskan SSH.

---

## 1.3 Test jaringan sebelum K3s

Di CP install netcat:

```bash
sudo apt update
sudo apt install -y netcat-openbsd
```

Setelah K3s server nanti aktif, dari kedua worker harus berhasil:

```bash
nc -vz <CP_K3S_ADDR> 6443
```

Default K3s dengan Flannel VXLAN juga membutuhkan komunikasi antar-node:

```text
TCP 6443   worker -> control plane
UDP 8472   node <-> node
TCP 10250  node <-> node
```

**Jangan buka UDP 8472 ke seluruh Internet.**

Firewall/security group harus membatasi port cluster hanya ke IP ketiga node.

---

## 1.4 Pastikan public HTTP/HTTPS tersedia

Untuk `api.titipin.me`, Caddy perlu menerima:

```text
TCP 80
TCP 443
```

ke VM-01.

Sebelum lanjut ke DNS, konfirmasi apakah MaxCloud/BCC memberikan public NAT/port-forward untuk 80 dan 443.

Jika 80/443 tidak dapat diarahkan ke VM-01, gunakan domain/reverse-proxy yang disediakan BCC atau tunjukkan API/Grafana melalui SSH tunnel saat demo.

---

# 2. Prepare Semua VM

Jalankan di ketiga VM.

## 2.1 Update OS

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y curl wget git htop jq netcat-openbsd
```

---

## 2.2 Hostname

Di CP:

```bash
sudo hostnamectl set-hostname control-plane
```

Di W1:

```bash
sudo hostnamectl set-hostname worker-1
```

Di W2:

```bash
sudo hostnamectl set-hostname worker-2
```

Reconnect SSH setelah mengganti hostname.

---

## 2.3 Disable swap

```bash
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab
```

Verifikasi:

```bash
free -h
```

---

## 2.4 Kernel networking

```bash
cat <<'EOF' | sudo tee /etc/modules-load.d/k3s.conf
br_netfilter
overlay
EOF

sudo modprobe br_netfilter
sudo modprobe overlay

cat <<'EOF' | sudo tee /etc/sysctl.d/99-k3s.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF

sudo sysctl --system
```

---

# 3. Install K3s

## 3.1 Control plane

Di CP:

```bash
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_EXEC="--disable traefik" \
  sh -
```

Traefik dinonaktifkan karena external ingress menggunakan Caddy.

Verifikasi:

```bash
sudo k3s kubectl get nodes -o wide
```

---

## 3.2 Ambil token

Di CP:

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

Simpan sebagai:

```text
<NODE_TOKEN>
```

---

## 3.3 Join worker

Di W1:

```bash
curl -sfL https://get.k3s.io | \
  K3S_URL=https://<CP_K3S_ADDR>:6443 \
  K3S_TOKEN='<NODE_TOKEN>' \
  sh -
```

Di W2:

```bash
curl -sfL https://get.k3s.io | \
  K3S_URL=https://<CP_K3S_ADDR>:6443 \
  K3S_TOKEN='<NODE_TOKEN>' \
  sh -
```

---

## 3.4 Verifikasi cluster

Di CP:

```bash
sudo k3s kubectl get nodes -o wide
```

Target:

```text
control-plane   Ready
worker-1        Ready
worker-2        Ready
```

---

## 3.5 Setup kubectl untuk user `dev`

Di CP:

```bash
mkdir -p ~/.kube

sudo k3s kubectl config view --raw > ~/.kube/config

chmod 600 ~/.kube/config
```

Test:

```bash
kubectl get nodes
```

Mulai bagian ini, seluruh command `kubectl` dan `helm` dapat dijalankan dari CP.

---

## 3.6 Label node

```bash
kubectl label node control-plane workload-role=control --overwrite
kubectl label node worker-1 workload-role=worker --overwrite
kubectl label node worker-2 workload-role=worker --overwrite
```

Verifikasi:

```bash
kubectl get nodes --show-labels
```

Backend nanti memakai:

```yaml
nodeSelector:
  workload-role: worker
```

sehingga pod eksperimen tidak dijalankan di control plane.

---

## 3.7 Verifikasi Metrics Server bawaan K3s

```bash
kubectl get pods -n kube-system | grep metrics-server
```

Tunggu sampai `Running`, lalu:

```bash
kubectl top nodes
```

Kalau keluar CPU dan memory usage, metrics-server siap dipakai HPA.

---

# 4. Buat Namespace Project

```bash
kubectl create namespace titipin
kubectl create namespace monitoring
```

---

# 5. GHCR Image Pull Secret

Jika image GHCR private, buat PAT dengan permission `read:packages`.

Di CP:

```bash
kubectl -n titipin create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io \
  --docker-username='<GITHUB_USERNAME>' \
  --docker-password='<GITHUB_PAT>'
```

Verifikasi:

```bash
kubectl -n titipin get secret ghcr-pull
```

Jika package sudah public, secret ini tetap boleh disiapkan untuk konsistensi.

---

# 6. Deploy PostgreSQL, Redis, dan MinIO

Stateful dependency **tidak menjadi autoscaling target**.

Untuk demo, ketiganya diletakkan pada node `control-plane` menggunakan K3s `local-path` storage.

> Storage size di bawah ini sengaja kecil karena VM-01 hanya memiliki 20 GB disk.

Buat file:

```bash
mkdir -p ~/mlops-manifests
nano ~/mlops-manifests/dependencies.yaml
```

Isi:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: titipin-infra-secret
  namespace: titipin
type: Opaque
stringData:
  DB_USERNAME: titipin_user
  DB_PASSWORD: CHANGE_ME_DB_PASSWORD
  DB_DATABASE: titipin_db
  MINIO_ROOT_USER: titipin_minio
  MINIO_ROOT_PASSWORD: CHANGE_ME_MINIO_PASSWORD
---
apiVersion: v1
kind: Service
metadata:
  name: db
  namespace: titipin
spec:
  selector:
    app: postgres
  ports:
    - port: 5432
      targetPort: 5432
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: titipin
spec:
  serviceName: db
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      nodeSelector:
        workload-role: control
      containers:
        - name: postgres
          image: pgvector/pgvector:pg16
          env:
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: titipin-infra-secret
                  key: DB_USERNAME
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: titipin-infra-secret
                  key: DB_PASSWORD
            - name: POSTGRES_DB
              valueFrom:
                secretKeyRef:
                  name: titipin-infra-secret
                  key: DB_DATABASE
          ports:
            - containerPort: 5432
          resources:
            requests:
              cpu: 100m
              memory: 192Mi
            limits:
              cpu: 500m
              memory: 512Mi
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: local-path
        resources:
          requests:
            storage: 3Gi
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: titipin
spec:
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: titipin
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      nodeSelector:
        workload-role: control
      containers:
        - name: redis
          image: redis:7-alpine
          command: ["redis-server", "--save", "60", "1", "--loglevel", "warning"]
          ports:
            - containerPort: 6379
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 200m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: minio
  namespace: titipin
spec:
  selector:
    app: minio
  ports:
    - name: api
      port: 9000
      targetPort: 9000
    - name: console
      port: 9001
      targetPort: 9001
---
apiVersion: v1
kind: Service
metadata:
  name: minio-nodeport
  namespace: titipin
spec:
  type: NodePort
  selector:
    app: minio
  ports:
    - name: api
      port: 9000
      targetPort: 9000
      nodePort: 30900
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minio
  namespace: titipin
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      nodeSelector:
        workload-role: control
      containers:
        - name: minio
          image: minio/minio:RELEASE.2023-04-20T17-56-55Z
          args:
            - server
            - /data
            - --console-address
            - ":9001"
          env:
            - name: MINIO_ROOT_USER
              valueFrom:
                secretKeyRef:
                  name: titipin-infra-secret
                  key: MINIO_ROOT_USER
            - name: MINIO_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: titipin-infra-secret
                  key: MINIO_ROOT_PASSWORD
          ports:
            - containerPort: 9000
            - containerPort: 9001
          resources:
            requests:
              cpu: 50m
              memory: 96Mi
            limits:
              cpu: 300m
              memory: 256Mi
          volumeMounts:
            - name: data
              mountPath: /data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: minio-data
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: minio-data
  namespace: titipin
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: local-path
  resources:
    requests:
      storage: 2Gi
```

Ganti:

```text
CHANGE_ME_DB_PASSWORD
CHANGE_ME_MINIO_PASSWORD
```

dengan password kuat.

Apply:

```bash
kubectl apply -f ~/mlops-manifests/dependencies.yaml
```

Tunggu:

```bash
kubectl -n titipin get pods -w
```

---

# 7. Buat Bucket MinIO

Ambil credential dari secret atau gunakan value yang tadi kamu isi.

Jalankan temporary MinIO client:

```bash
kubectl -n titipin run minio-client \
  --rm -it \
  --restart=Never \
  --image=minio/mc:latest \
  -- /bin/sh
```

Di dalam shell:

```sh
mc alias set local http://minio:9000 titipin_minio '<MINIO_PASSWORD>'
mc mb local/titipin-bucket --ignore-existing
mc anonymous set download local/titipin-bucket
exit
```

---

# 8. Buat Environment Secret Laravel

Generate APP_KEY:

```bash
APP_KEY="base64:$(openssl rand -base64 32)"
echo "$APP_KEY"
```

Buat file temporary:

```bash
nano /tmp/titipin-k8s.env
```

Isi minimal:

```dotenv
APP_NAME=Titip.in
APP_ENV=production
APP_KEY=PASTE_APP_KEY_HERE
APP_DEBUG=false
APP_URL=https://api.titipin.me
FRONTEND_URL=https://titipin.me

LOG_CHANNEL=stack
LOG_LEVEL=info

DB_CONNECTION=pgsql
DB_HOST=db
DB_PORT=5432
DB_DATABASE=titipin_db
DB_USERNAME=titipin_user
DB_PASSWORD=CHANGE_ME_DB_PASSWORD

CACHE_STORE=redis
QUEUE_CONNECTION=redis
SESSION_DRIVER=redis
REDIS_CLIENT=phpredis
REDIS_HOST=redis
REDIS_PASSWORD=null
REDIS_PORT=6379

FILESYSTEM_DISK=s3
AWS_ACCESS_KEY_ID=titipin_minio
AWS_SECRET_ACCESS_KEY=CHANGE_ME_MINIO_PASSWORD
AWS_DEFAULT_REGION=us-east-1
AWS_BUCKET=titipin-bucket
AWS_ENDPOINT=http://minio:9000
AWS_USE_PATH_STYLE_ENDPOINT=true
AWS_URL=https://storage.titipin.me/titipin-bucket

SESSION_DOMAIN=titipin.me
SANCTUM_STATEFUL_DOMAINS=titipin.me,api.titipin.me

GOOGLE_REDIRECT_URI=https://api.titipin.me/api/v1/auth/google/callback

AI_DEFAULT_PROVIDER=gemini
```

Untuk demo endpoint public-read, credential Google/Gemini/Mail/Evolution boleh belum diisi jika route yang diuji tidak memerlukannya.

Create secret:

```bash
kubectl -n titipin create secret generic titipin-app-env \
  --from-env-file=/tmp/titipin-k8s.env
```

Hapus local temp file:

```bash
rm /tmp/titipin-k8s.env
```

---

# 9. ConfigMap Nginx + PHP Startup

Buat:

```bash
nano ~/mlops-manifests/backend-config.yaml
```

Isi:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: laravel-backend-config
  namespace: titipin
data:
  default.conf: |
    server {
        listen 80;
        server_name _;
        root /var/www/html/public;
        index index.php;
        client_max_body_size 50M;
        server_tokens off;

        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires max;
            log_not_found off;
            access_log off;
        }

        location / {
            try_files $uri $uri/ /index.php?$query_string;
        }

        location ~ \.php$ {
            fastcgi_pass 127.0.0.1:9000;
            fastcgi_index index.php;
            fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
            include fastcgi_params;
            fastcgi_read_timeout 300;
        }
    }

  start-php.sh: |
    #!/bin/sh
    set -e

    cd /var/www/html

    until PGPASSWORD="$DB_PASSWORD" pg_isready \
      -h "$DB_HOST" \
      -U "$DB_USERNAME" \
      -d "$DB_DATABASE" -q; do
      echo "Waiting for PostgreSQL..."
      sleep 2
    done

    php artisan config:clear || true
    php artisan cache:clear || true

    if [ ! -L public/storage ]; then
      php artisan storage:link --force || true
    fi

    php artisan config:cache
    php artisan route:cache
    php artisan view:cache

    chown -R www-data:www-data storage bootstrap/cache 2>/dev/null || true

    exec php-fpm
```

Apply:

```bash
kubectl apply -f ~/mlops-manifests/backend-config.yaml
```

### Kenapa startup script diubah?

Image existing menjalankan `php artisan migrate --force` saat setiap PHP container start.

Pada autoscaling, replica baru dapat muncul berkali-kali. Migration tidak seharusnya dijalankan setiap replica startup.

Guide ini menjalankan migration sebagai Kubernetes Job terpisah.

---

# 10. Migration Job

Buat:

```bash
nano ~/mlops-manifests/migrate.yaml
```

Isi:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: titipin-migrate
  namespace: titipin
spec:
  backoffLimit: 3
  template:
    metadata:
      labels:
        app: titipin-migrate
    spec:
      restartPolicy: Never
      nodeSelector:
        workload-role: worker
      imagePullSecrets:
        - name: ghcr-pull
      containers:
        - name: migrate
          image: ghcr.io/titip-in/titip-in-web-app:latest
          envFrom:
            - secretRef:
                name: titipin-app-env
          command:
            - /bin/sh
            - -c
            - |
              until PGPASSWORD="$DB_PASSWORD" pg_isready \
                -h "$DB_HOST" -U "$DB_USERNAME" -d "$DB_DATABASE" -q; do
                sleep 2
              done

              php artisan migrate --force
```

Apply:

```bash
kubectl apply -f ~/mlops-manifests/migrate.yaml
```

Check:

```bash
kubectl -n titipin logs job/titipin-migrate
kubectl -n titipin get job titipin-migrate
```

Target:

```text
COMPLETIONS 1/1
```

---

# 11. Deploy Laravel Backend ke Worker

Buat:

```bash
nano ~/mlops-manifests/backend.yaml
```

Isi:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: laravel-backend
  namespace: titipin
spec:
  replicas: 1
  selector:
    matchLabels:
      app: laravel-backend
  template:
    metadata:
      labels:
        app: laravel-backend
    spec:
      nodeSelector:
        workload-role: worker

      imagePullSecrets:
        - name: ghcr-pull

      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app: laravel-backend

      containers:
        - name: php
          image: ghcr.io/titip-in/titip-in-web-app:latest
          envFrom:
            - secretRef:
                name: titipin-app-env
          command:
            - /bin/sh
            - /config/start-php.sh
          ports:
            - containerPort: 9000
          resources:
            requests:
              cpu: 150m
              memory: 128Mi
            limits:
              cpu: 750m
              memory: 512Mi
          volumeMounts:
            - name: backend-config
              mountPath: /config
            - name: app-storage
              mountPath: /var/www/html/storage/app/public

        - name: nginx
          image: ghcr.io/titip-in/titip-in-web-web:latest
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 25m
              memory: 24Mi
            limits:
              cpu: 200m
              memory: 96Mi
          readinessProbe:
            httpGet:
              path: /up
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /up
              port: 80
            initialDelaySeconds: 15
            periodSeconds: 10
          volumeMounts:
            - name: backend-config
              mountPath: /etc/nginx/conf.d/default.conf
              subPath: default.conf
            - name: app-storage
              mountPath: /var/www/html/public/storage

      volumes:
        - name: backend-config
          configMap:
            name: laravel-backend-config
            defaultMode: 0755
        - name: app-storage
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: laravel-backend
  namespace: titipin
spec:
  selector:
    app: laravel-backend
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: laravel-backend-nodeport
  namespace: titipin
spec:
  type: NodePort
  selector:
    app: laravel-backend
  ports:
    - port: 80
      targetPort: 80
      nodePort: 30080
```

Apply:

```bash
kubectl apply -f ~/mlops-manifests/backend.yaml
```

Check:

```bash
kubectl -n titipin get pods -o wide
kubectl -n titipin get svc
```

Pastikan pod `laravel-backend-*` berada di `worker-1` atau `worker-2`, bukan control-plane.

---

# 12. Test API Sebelum Domain

Dari CP:

```bash
curl -i http://127.0.0.1:30080/up
```

Jika NodePort tidak listen melalui loopback, gunakan salah satu worker:

```bash
curl -i http://15.232.116.101:30080/up
```

Target:

```text
HTTP/1.1 200
```

Test endpoint public existing:

```bash
curl -s http://15.232.116.101:30080/api/v1/categories | jq .
curl -s http://15.232.116.101:30080/api/v1/jastip/listings | jq .
curl -s http://15.232.116.101:30080/api/v1/preloved/listings | jq .
```

---

# 13. Install Caddy

Di CP:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor \
  -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list

sudo apt update
sudo apt install -y caddy
```

---

# 14. Cloudflare DNS

Jika VM-01 menerima public TCP 80/443, buat A record:

```text
api       -> <PUBLIC_IP_VM01>
grafana   -> <PUBLIC_IP_VM01>
storage   -> <PUBLIC_IP_VM01>
```

Untuk initial TLS issuance gunakan:

```text
Proxy status: DNS only
```

Jika VM-01 berada di balik NAT/proxy BCC, sesuaikan record ke public endpoint yang benar.

---

# 15. Caddy Reverse Proxy + Caddy Metrics

Caddy dipakai sekaligus sebagai sumber application-edge metrics.

Buat:

```bash
sudo nano /etc/caddy/Caddyfile
```

Isi:

```caddy
{
    metrics {
        per_host
    }
}

api.titipin.me {
    reverse_proxy 127.0.0.1:30080
}

grafana.titipin.me {
    reverse_proxy 127.0.0.1:30300
}

storage.titipin.me {
    reverse_proxy 127.0.0.1:30900
}

:9180 {
    metrics /metrics
}
```

Validate:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
```

Restart:

```bash
sudo systemctl enable caddy
sudo systemctl restart caddy
sudo systemctl status caddy
```

Test:

```bash
curl -I https://api.titipin.me/up
curl -s http://127.0.0.1:9180/metrics | head
```

Caddy metrics menyediakan data seperti:

```text
request count
request duration
response status
reverse proxy health
```

Ini cukup untuk tahap demo tanpa harus mengubah source Laravel terlebih dahulu.

---

# 16. Install Helm

Di CP:

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

Verifikasi:

```bash
helm version
```

---

# 17. Install kube-prometheus-stack

Guide ini menggunakan `kube-prometheus-stack` agar tidak perlu menjalankan cAdvisor Docker manual.

Stack ini memberi:

```text
Prometheus
Grafana
kube-state-metrics
node-exporter
kubelet/cAdvisor scraping
Prometheus Operator
```

Dengan begitu metric container K3s/containerd berasal dari kubelet/cAdvisor, bukan `/var/lib/docker`.

---

## 17.1 Cari IP node control-plane

```bash
CP_NODE_IP=$(kubectl get node control-plane \
  -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}')

echo "$CP_NODE_IP"
```

---

## 17.2 Monitoring values

Buat:

```bash
nano ~/mlops-manifests/monitoring-values.yaml
```

Isi:

```yaml
alertmanager:
  enabled: false

# K3s bundles these components internally — disable their ServiceMonitors
# to avoid "target not found" warnings in Prometheus
kubeControllerManager:
  enabled: false
kubeScheduler:
  enabled: false
kubeProxy:
  enabled: false

prometheusOperator:
  nodeSelector:
    workload-role: control

prometheus:
  prometheusSpec:
    nodeSelector:
      workload-role: control

    retention: 3d
    retentionSize: 3GB

    resources:
      requests:
        cpu: 150m
        memory: 384Mi
      limits:
        cpu: 750m
        memory: 1Gi

    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: local-path
          accessModes:
            - ReadWriteOnce
          resources:
            requests:
              storage: 4Gi

    additionalScrapeConfigs:
      - job_name: caddy
        scrape_interval: 15s
        static_configs:
          - targets:
              - REPLACE_CP_NODE_IP:9180

grafana:
  nodeSelector:
    workload-role: control

  service:
    type: NodePort
    nodePort: 30300

  resources:
    requests:
      cpu: 50m
      memory: 96Mi
    limits:
      cpu: 300m
      memory: 256Mi

kube-state-metrics:
  nodeSelector:
    workload-role: control

# Ensure node-exporter also runs on the tainted control plane
prometheus-node-exporter:
  tolerations:
    - key: node-role.kubernetes.io/master
      operator: Exists
      effect: NoSchedule
    - key: node-role.kubernetes.io/control-plane
      operator: Exists
      effect: NoSchedule
```

Ganti IP:

```bash
sed -i "s/REPLACE_CP_NODE_IP/${CP_NODE_IP}/" \
  ~/mlops-manifests/monitoring-values.yaml
```

---

## 17.3 Install chart

```bash
helm repo add prometheus-community \
  https://prometheus-community.github.io/helm-charts

helm repo update
```

Untuk reproducibility, pin chart version yang sudah kamu validasi.

Contoh current guide:

```bash
helm upgrade --install monitoring \
  prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --version 89.2.0 \
  -f ~/mlops-manifests/monitoring-values.yaml
```

Tunggu:

```bash
kubectl -n monitoring get pods -w
```

Target utama harus `Running`:

```text
Prometheus
Grafana
Prometheus Operator
kube-state-metrics
node-exporter
```

---

# 18. Grafana

Ambil admin password:

```bash
kubectl -n monitoring get secret monitoring-grafana \
  -o jsonpath='{.data.admin-password}' \
  | base64 -d

echo
```

Akses:

```text
https://grafana.titipin.me
```

atau tanpa domain:

```text
http://<CP_OR_NODE_IP>:30300
```

---

# 19. Verify Prometheus

Port-forward Prometheus untuk debugging:

```bash
kubectl -n monitoring port-forward \
  svc/monitoring-kube-prometheus-prometheus \
  9090:9090
```

Di terminal lain pada CP:

```bash
curl -s http://127.0.0.1:9090/-/ready
```

Target:

```text
Prometheus Server is Ready.
```

---

# 20. Verify Metrik Penting

## 20.1 Request rate dari Caddy

```promql
sum(
  rate(
    caddy_http_requests_total{
      handler="reverse_proxy"
    }[1m]
  )
)
```

Jika label `host` tersedia dari `per_host`, filter:

```promql
sum(
  rate(
    caddy_http_requests_total{
      handler="reverse_proxy",
      host="api.titipin.me"
    }[1m]
  )
)
```

---

## 20.2 p95 latency

```promql
histogram_quantile(
  0.95,
  sum by (le) (
    rate(
      caddy_http_request_duration_seconds_bucket{
        handler="reverse_proxy"
      }[1m]
    )
  )
)
```

---

## 20.3 PHP pod CPU

```promql
sum(
  rate(
    container_cpu_usage_seconds_total{
      namespace="titipin",
      pod=~"laravel-backend-.*",
      container="php"
    }[1m]
  )
)
```

---

## 20.4 PHP memory

```promql
sum(
  container_memory_working_set_bytes{
    namespace="titipin",
    pod=~"laravel-backend-.*",
    container="php"
  }
)
```

---

## 20.5 Replica count

```promql
kube_deployment_status_replicas{
  namespace="titipin",
  deployment="laravel-backend"
}
```

---

## 20.6 Ready replicas

```promql
kube_deployment_status_replicas_ready{
  namespace="titipin",
  deployment="laravel-backend"
}
```

---

# 21. Buat Dashboard Demo Grafana

Minimal buat 5 panel:

```text
1. API Request Rate
2. API p95 Latency
3. Laravel PHP CPU
4. Laravel PHP Memory
5. Backend Replica Count
```

Ini sudah cukup kuat untuk menjelaskan proposal:

```text
workload
   ↓
resource behavior
   ↓
scaling
   ↓
time-series data
```

---

# 22. Install k6 di Load Generator

Load generator sebaiknya berada **di luar worker cluster**.

Bisa:

```text
AWS EC2
atau
laptop
```

Contoh Ubuntu:

```bash
sudo gpg -k
sudo gpg --no-default-keyring \
  --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 \
  --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69

echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list

sudo apt update
sudo apt install -y k6
```

Verifikasi:

```bash
k6 version
```

---

# 23. k6 Smoke Test

Buat:

```bash
mkdir -p ~/k6
nano ~/k6/smoke.js
```

Isi:

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 2,
  duration: '30s',
};

const BASE_URL = __ENV.BASE_URL || 'https://api.titipin.me';

const endpoints = [
  '/api/v1/categories',
  '/api/v1/jastip/listings',
  '/api/v1/preloved/listings',
  '/api/v1/jastip/requests',
  '/api/v1/preloved/requests',
];

export default function () {
  const endpoint =
    endpoints[Math.floor(Math.random() * endpoints.length)];

  const res = http.get(`${BASE_URL}${endpoint}`);

  check(res, {
    'HTTP < 500': (r) => r.status < 500,
  });

  sleep(0.5);
}
```

Run:

```bash
BASE_URL=https://api.titipin.me \
k6 run ~/k6/smoke.js
```

Saat script berjalan, buka Grafana.

Harus terlihat:

```text
request rate naik
CPU Laravel berubah
latency terekam
```

---

# 24. Calibration Workload

Jangan langsung menentukan workload final project.

Buat:

```bash
nano ~/k6/calibration.js
```

Isi:

```javascript
import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'https://api.titipin.me';

const endpoints = [
  '/api/v1/categories',
  '/api/v1/jastip/listings',
  '/api/v1/preloved/listings',
  '/api/v1/jastip/requests',
  '/api/v1/preloved/requests',
];

export const options = {
  scenarios: {
    calibration: {
      executor: 'ramping-arrival-rate',
      startRate: 1,
      timeUnit: '1s',
      preAllocatedVUs: 20,
      maxVUs: 100,

      stages: [
        { target: 1, duration: '1m' },
        { target: 5, duration: '2m' },
        { target: 10, duration: '2m' },
        { target: 15, duration: '2m' },
        { target: 20, duration: '2m' },
        { target: 1, duration: '1m' },
      ],
    },
  },
};

export default function () {
  const endpoint =
    endpoints[Math.floor(Math.random() * endpoints.length)];

  const res = http.get(`${BASE_URL}${endpoint}`);

  check(res, {
    'HTTP < 500': (r) => r.status < 500,
  });
}
```

**Angka 1/5/10/15/20 req/s hanya bootstrap calibration.**

Setelah melihat CPU, latency, dan errors, kamu dapat menentukan:

```text
LOW
MEDIUM
HIGH
SATURATION
```

baru kemudian membuat scenario final:

```text
steady
gradual
spike
periodic
bursty
```

---

# 25. Deploy Reactive HPA Baseline

Setelah metrics-server dan backend berjalan normal, buat:

```bash
nano ~/mlops-manifests/hpa.yaml
```

Isi:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: laravel-backend
  namespace: titipin
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: laravel-backend

  minReplicas: 1
  maxReplicas: 4

  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
    scaleDown:
      stabilizationWindowSeconds: 120

  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
```

Apply:

```bash
kubectl apply -f ~/mlops-manifests/hpa.yaml
```

Watch:

```bash
kubectl -n titipin get hpa -w
```

Di terminal lain:

```bash
kubectl -n titipin get pods -w
```

Lalu jalankan calibration k6.

Tujuan demo:

```text
traffic naik
   ↓
CPU naik
   ↓
HPA bereaksi
   ↓
replica berubah
   ↓
Grafana mencatat semuanya
```

Threshold 60%, min 1, max 4 adalah **bootstrap value**, bukan nilai eksperimen final.

---

# 26. Export Time-Series Data Menjadi CSV

Sekarang data sudah benar-benar tersedia di Prometheus.

Buka port-forward:

```bash
kubectl -n monitoring port-forward \
  svc/monitoring-kube-prometheus-prometheus \
  9090:9090
```

Buat Python script:

```bash
nano ~/export_demo_dataset.py
```

Isi:

```python
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

PROM = "http://127.0.0.1:9090"

end = datetime.now(timezone.utc)
start = end - timedelta(minutes=30)
step = 15

queries = {
    "request_rate": """
        sum(
          rate(
            caddy_http_requests_total{
              handler="reverse_proxy"
            }[1m]
          )
        )
    """,

    "php_cpu_cores": """
        sum(
          rate(
            container_cpu_usage_seconds_total{
              namespace="titipin",
              pod=~"laravel-backend-.*",
              container="php"
            }[1m]
          )
        )
    """,

    "php_memory_bytes": """
        sum(
          container_memory_working_set_bytes{
            namespace="titipin",
            pod=~"laravel-backend-.*",
            container="php"
          }
        )
    """,

    "replicas": """
        kube_deployment_status_replicas{
          namespace="titipin",
          deployment="laravel-backend"
        }
    """,

    "p95_latency_seconds": """
        histogram_quantile(
          0.95,
          sum by (le) (
            rate(
              caddy_http_request_duration_seconds_bucket{
                handler="reverse_proxy"
              }[1m]
            )
          )
        )
    """,
}


def query_range(promql):
    response = requests.get(
        f"{PROM}/api/v1/query_range",
        params={
            "query": promql,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        },
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()["data"]["result"]

    if not result:
        return pd.Series(dtype=float)

    values = result[0]["values"]

    return pd.Series(
        {
            pd.to_datetime(ts, unit="s", utc=True): float(value)
            for ts, value in values
        }
    )


frame = pd.DataFrame()

for name, query in queries.items():
    frame[name] = query_range(query)

frame.index.name = "timestamp"
frame = frame.sort_index()

frame.to_csv("demo_metrics.csv")

print(frame.tail(20))
print("\nSaved: demo_metrics.csv")
```

Install dependencies:

```bash
python3 -m venv ~/mlops-demo-venv
source ~/mlops-demo-venv/bin/activate

pip install pandas requests
```

Run:

```bash
python ~/export_demo_dataset.py
```

Output:

```text
demo_metrics.csv
```

Cek:

```bash
head demo_metrics.csv
```

Contoh struktur:

```text
timestamp,request_rate,php_cpu_cores,php_memory_bytes,replicas,p95_latency_seconds
...
```

**Inilah bukti bahwa dataset bukan dibuat manual.**

Data berasal dari:

```text
k6 real HTTP requests
       ↓
Laravel real execution
       ↓
Kubernetes real resource behavior
       ↓
Prometheus
       ↓
Prometheus API
       ↓
CSV
```

---

# 27. Yang Ditunjukkan ke Dosen

Untuk demo proposal, cukup buka empat hal.

## 27.1 Cluster

```bash
kubectl get nodes -o wide
```

Tunjukkan 3 node `Ready`.

---

## 27.2 Backend

```bash
kubectl -n titipin get pods -o wide
kubectl -n titipin get hpa
```

Tunjukkan backend berada di worker.

---

## 27.3 API

```bash
curl -I https://api.titipin.me/up
curl -s https://api.titipin.me/api/v1/categories | jq .
```

---

## 27.4 Grafana

Dashboard:

```text
Request Rate
p95 Latency
PHP CPU
PHP Memory
Replica Count
```

Lalu jalankan k6 di depan dosen.

Harus terlihat grafik berubah.

---

## 27.5 Dataset

```bash
head demo_metrics.csv
```

Jelaskan:

> “Yang kami generate secara terkontrol adalah workload. Nilai CPU, memory, latency, replica, dan metrics lainnya tidak dibuat manual; nilainya berasal dari sistem yang benar-benar menerima request dan dikumpulkan Prometheus.”

---

# 28. Cara Menjelaskan Dynamic Data dan Drift

## Dynamic data

```text
Run hari ini
  ↓
Prometheus observations
  ↓
Dataset v1

Run berikutnya
  ↓
new observations
  ↓
Dataset v2
```

Dataset terus bertambah selama workload berjalan.

---

## Drift experiment nanti

Jangan edit CSV secara manual.

Contoh:

```text
Training regime
1–10 req/s
mostly read-heavy
        ↓
model v1
        ↓
Later workload
10–25 req/s
lebih bursty / endpoint mix berbeda
        ↓
new Prometheus distribution
        ↓
drift detection
        ↓
retraining
```

Drift harus diverifikasi dari data hasil observasi, bukan hanya karena skenario diberi nama “drift”.

---

# 29. Storage Guardrails

Control plane hanya memiliki 20 GB storage.

Jangan gunakan retention besar tanpa batas.

Guide ini menggunakan:

```text
Prometheus PVC        4 GiB
Prometheus retention  3 days
Retention size        3 GB
PostgreSQL PVC        3 GiB
MinIO PVC             2 GiB
```

Monitor:

```bash
df -h
kubectl get pvc -A
```

Setelah dataset diekspor dan di-versioning dengan DVC, raw Prometheus retention tidak perlu menyimpan seluruh histori project selamanya.

---

# 30. Important Experimental Caveats

## 30.1 Jangan pakai `latest` untuk final experiment

Untuk bootstrap demo:

```text
:latest
```

boleh.

Untuk final predictive-vs-reactive comparison, pin image digest/tag.

Cek image digest pod:

```bash
kubectl -n titipin get pods \
  -l app=laravel-backend \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{range .status.containerStatuses[*]}{.name}{" => "}{.imageID}{"\n"}{end}{end}'
```

---

## 30.2 Resource requests/limits belum final

Nilai:

```text
PHP request CPU 150m
PHP limit CPU   750m
PHP request RAM 128Mi
PHP limit RAM   512Mi
```

adalah bootstrap values.

Setelah calibration, revisi agar:

- pod cukup kecil untuk bisa scale;
- node tidak langsung OOM;
- workload menghasilkan pressure yang terukur.

---

## 30.3 HPA threshold belum final

`60%` hanya baseline awal.

Freeze nilai final sebelum eksperimen resmi.

---

## 30.4 Prediction target belum final

Walaupun working hypothesis project adalah:

```text
future request rate
```

target final baru dipilih setelah:

```text
initial dataset
   ↓
EDA
   ↓
decision
```

---

# 31. Troubleshooting

## Worker gagal join

Di worker:

```bash
nc -vz <CP_K3S_ADDR> 6443
```

Kalau timeout:

- cek firewall CP;
- cek NAT/port-forward;
- cek alamat CP yang digunakan;
- cek apakah worker memang dapat route ke alamat tersebut.

---

## Node `NotReady`

```bash
sudo journalctl -u k3s-agent -n 100 --no-pager
```

Di CP:

```bash
kubectl describe node worker-1
```

---

## Metrics Server tidak bekerja

```bash
kubectl -n kube-system logs \
  -l k8s-app=metrics-server \
  --tail=100
```

Test:

```bash
kubectl top nodes
kubectl top pods -A
```

---

## ImagePullBackOff

```bash
kubectl -n titipin describe pod <POD_NAME>
```

Pastikan:

```bash
kubectl -n titipin get secret ghcr-pull
```

---

## Laravel pod restart

```bash
kubectl -n titipin logs <POD_NAME> -c php --tail=100
kubectl -n titipin logs <POD_NAME> -c nginx --tail=100
```

---

## Migration gagal

```bash
kubectl -n titipin logs job/titipin-migrate
```

Cek Postgres:

```bash
kubectl -n titipin get pod -l app=postgres
kubectl -n titipin logs statefulset/postgres
```

---

## API `/up` gagal

```bash
kubectl -n titipin get pods
kubectl -n titipin get svc
curl -v http://15.232.116.101:30080/up
```

---

## Grafana tidak dapat dibuka

```bash
kubectl -n monitoring get svc | grep grafana
curl -I http://127.0.0.1:30300
```

---

## Prometheus tidak scrape Caddy

Dari CP:

```bash
curl http://127.0.0.1:9180/metrics
```

Check target via Prometheus UI:

```text
Status -> Targets
```

Pastikan job `caddy` = `UP`.

---

## CPU metric kosong

Port-forward Prometheus lalu query:

```promql
container_cpu_usage_seconds_total
```

Jika kosong:

```bash
kubectl -n monitoring get servicemonitor
```

dan pastikan kubelet/cAdvisor ServiceMonitor aktif.

---

# 32. Demo Completion Checklist

## Infrastructure

- [ ] SSH CP/W1/W2 berhasil
- [ ] `kubectl get nodes` menunjukkan 3 node `Ready`
- [ ] `kubectl top nodes` bekerja
- [ ] Backend pod hanya berjalan di W1/W2

## Application

- [ ] PostgreSQL Running
- [ ] Redis Running
- [ ] MinIO Running
- [ ] Migration Job sukses
- [ ] Laravel backend Running
- [ ] `https://api.titipin.me/up` = 200
- [ ] public API endpoint mengembalikan data

## Monitoring

- [ ] Prometheus Running
- [ ] Grafana Running
- [ ] kube-state-metrics Running
- [ ] node-exporter Running
- [ ] kubelet/cAdvisor metrics tersedia
- [ ] Caddy metrics job `UP`

## Dataset

- [ ] request rate tersedia
- [ ] p95 latency tersedia
- [ ] PHP CPU tersedia
- [ ] PHP memory tersedia
- [ ] replica count tersedia
- [ ] `demo_metrics.csv` berhasil dibuat

## Workload

- [ ] k6 smoke berhasil
- [ ] k6 calibration mengubah grafik
- [ ] HPA menunjukkan current/target CPU
- [ ] replica berubah ketika threshold tercapai

---

# 33. Setelah Demo Berhasil

Urutan project berikutnya:

```text
Demo-ready infrastructure
        ↓
Workload calibration
        ↓
Define final steady/gradual/spike/periodic/bursty
        ↓
Collect dataset v1
        ↓
Data validation
        ↓
EDA
        ↓
Finalize target + sampling + prediction horizon
        ↓
Persistence / Moving Average
        ↓
Linear Regression
        ↓
XGBoost candidate
        ↓
MLflow + DVC
        ↓
FastAPI inference
        ↓
Predictive scaling policy
        ↓
Predictive vs Reactive experiment
        ↓
Drift experiment
        ↓
Continuous Training
```

---

# 34. Source Notes

Guide ini disesuaikan dengan implementasi Titip.In yang ada saat ini:

- backend image menggunakan PHP-FPM image dan Nginx image terpisah;
- Nginx existing meneruskan FastCGI ke `php:9000`;
- PHP startup existing menjalankan migration;
- Laravel menyediakan health route `/up`;
- public read endpoints tersedia pada `/api/v1/categories`, `/api/v1/jastip/*`, dan `/api/v1/preloved/*`;
- PostgreSQL existing menggunakan `pgvector/pgvector:pg16`;
- Redis existing menggunakan `redis:7-alpine`;
- MinIO existing digunakan sebagai S3-compatible object storage.

Untuk monitoring, guide menggunakan K3s metrics-server dan kube-prometheus-stack agar metrics Kubernetes/container dikumpulkan melalui mekanisme Kubernetes, bukan Docker-specific cAdvisor setup.

---

# 35. Final Demo Narrative

Kalimat ringkas yang dapat digunakan saat presentasi:

> “Aplikasi existing Titip.In dijalankan sebagai workload nyata di Kubernetes. Traffic eksperimen dikontrol menggunakan k6, tetapi data Machine Learning tidak dibuat secara manual. Setiap request benar-benar diproses Laravel, kemudian request rate, response latency, CPU, memory, dan replica count dikumpulkan oleh Prometheus. Data tersebut diambil melalui Prometheus API menjadi dataset time-series yang terus bertambah. Setelah dataset cukup, kami melakukan EDA dan menentukan target forecasting. Reactive HPA digunakan sebagai baseline, sedangkan predictive autoscaling nantinya menggunakan hasil forecast untuk melakukan scaling lebih awal. Perubahan workload regime juga akan digunakan untuk menguji data drift dan Continuous Training.”
