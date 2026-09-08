# Setup Guide: Infrastructure, Backend, dan Monitoring

Panduan lengkap dari nol sampai kamu bisa mengambil data dan metrik dari aplikasi yang berjalan di atas Kubernetes.

## Gambaran Besar

```text
[Laptop kamu]
     │
     │ SSH ke setiap VM
     ▼
VM-01 (Control Plane) ─── proxy.bccdev.id:11049
VM-02 (Worker 1)      ─── 15.232.116.101
VM-03 (Worker 2)      ─── 15.232.71.54

Stack yang akan berjalan:
  VM-01 : K3s control plane + Prometheus + Grafana + Caddy (reverse proxy)
  VM-02 : K3s worker
  VM-03 : K3s worker
```

**Goal akhir panduan ini:**
- Kubernetes cluster berjalan (3 node)
- Laravel backend (`api.titipin.me`) live dan bisa diakses publik
- Prometheus mengumpulkan metrik dari Kubernetes dan aplikasi
- Grafana bisa divisualisasikan
- Kamu bisa query Prometheus API untuk ambil data mentah

---

## Bagian 0: Persiapan di Laptop

### 0.1 Tambahkan SSH config

Edit `~/.ssh/config` di laptop kamu:

```
# VM-01: Control Plane
Host cp
  HostName proxy.bccdev.id
  Port 11049
  User dev
  IdentityFile ~/.ssh/id_ed25519

# VM-02: Worker 1
Host w1
  HostName 15.232.116.101
  User ubuntu
  IdentityFile ~/.ssh/id_ed25519

# VM-03: Worker 2
Host w2
  HostName 15.232.71.54
  User ubuntu
  IdentityFile ~/.ssh/id_ed25519
```

Test akses ke ketiga VM:

```bash
ssh cp "echo OK"
ssh w1 "echo OK"
ssh w2 "echo OK"
```

### 0.2 Install kubectl di laptop

```bash
curl -LO "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/
kubectl version --client
```

---

## Bagian 1: Persiapan Semua VM (Jalankan di CP + W1 + W2)

### 1.1 Update sistem

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git htop
```

### 1.2 Matikan swap (wajib untuk Kubernetes)

```bash
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab
```

### 1.3 Setup kernel networking

```bash
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
br_netfilter
overlay
EOF

sudo modprobe br_netfilter overlay

cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF

sudo sysctl --system
```

---

## Bagian 2: Setup K3s Kubernetes Cluster

### 2.1 Install K3s di VM-01 (Control Plane)

Login ke VM-01 (`ssh cp`):

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik" sh -
```

> `--disable traefik` karena kita pakai Caddy sebagai reverse proxy.

Verifikasi:

```bash
sudo k3s kubectl get nodes
```

### 2.2 Ambil Node Token dari CP

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
# Catat output ini sebagai <NODE_TOKEN>

# Catat IP internal VM-01
hostname -I | awk '{print $1}'
```

### 2.3 Rename hostname Worker (penting, keduanya awalnya bernama "ubuntu")

Di VM-02 (`ssh w1`):
```bash
sudo hostnamectl set-hostname worker-1
```

Di VM-03 (`ssh w2`):
```bash
sudo hostnamectl set-hostname worker-2
```

### 2.4 Install K3s Agent di VM-02 dan VM-03

Di VM-02 (`ssh w1`) dan VM-03 (`ssh w2`), jalankan:

```bash
curl -sfL https://get.k3s.io | \
  K3S_URL=https://<IP_VM01>:6443 \
  K3S_TOKEN=<NODE_TOKEN> \
  sh -
```

### 2.5 Verifikasi dari VM-01

```bash
sudo k3s kubectl get nodes -o wide
# Semua 3 node harus STATUS=Ready
```

### 2.6 Setup kubectl di Laptop

```bash
# Dari VM-01
sudo cat /etc/rancher/k3s/k3s.yaml
```

Copy ke `~/.kube/config` di laptop, lalu ubah baris:
```yaml
server: https://127.0.0.1:6443
```
Menjadi:
```yaml
server: https://proxy.bccdev.id:6443
```

Test dari laptop:
```bash
kubectl get nodes
```

### 2.7 Label dan Taint Node

```bash
kubectl label nodes worker-1 node-role.kubernetes.io/worker=worker
kubectl label nodes worker-2 node-role.kubernetes.io/worker=worker
kubectl taint nodes dev node-role.kubernetes.io/master:NoSchedule
```

---

## Bagian 3: Deploy Backend Laravel

Backend menggunakan image yang sudah ada di `ghcr.io/titip-in/` — tidak perlu build ulang.

### 3.1 Setup DNS di Cloudflare

Tambah A Record di dashboard Cloudflare untuk `titipin.me`:
- `api` → `<IP_PUBLIK_VM01>` — Proxy status: **DNS only** (abu-abu)
- `grafana` → `<IP_PUBLIK_VM01>` — Proxy status: **DNS only**

Cek IP publik VM-01:
```bash
# Dari VM-01
curl -s ifconfig.me
```

### 3.2 Install Docker di VM-01

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

### 3.3 Siapkan Konfigurasi Backend

```bash
mkdir -p ~/titip-in && cd ~/titip-in
```

Copy docker-compose dari laptop:
```bash
scp /home/oktaavsm/Code/github.com/titip-in-web/docker-compose.prod.yaml cp:~/titip-in/docker-compose.yaml
```

Buat `.env` (dari laptop):
```bash
scp /home/oktaavsm/Code/github.com/titip-in-web/.env.example cp:~/titip-in/.env
```

Lalu edit di VM-01:
```bash
nano ~/titip-in/.env
```

Yang **wajib** diisi/diubah:
- `APP_ENV=production`
- `APP_DEBUG=false`
- `APP_URL=https://api.titipin.me`
- `FRONTEND_URL=https://titipin.me`
- `APP_KEY=` → generate: `docker run --rm php:8.4-fpm php -r "echo 'base64:'.base64_encode(random_bytes(32)).PHP_EOL;"`
- `DB_PASSWORD=` → isi dengan password kuat
- `AWS_SECRET_ACCESS_KEY=` → password MinIO
- `SESSION_DOMAIN=titipin.me`
- `SANCTUM_STATEFUL_DOMAINS=titipin.me,api.titipin.me`
- Semua URL callback Google OAuth ganti ke `https://api.titipin.me/...`

### 3.4 Login ke GHCR dan Pull Image

```bash
echo "<GITHUB_PAT>" | docker login ghcr.io -u <GITHUB_USERNAME> --password-stdin
```

> Buat PAT di https://github.com/settings/tokens dengan scope `read:packages`.

### 3.5 Jalankan Backend

```bash
cd ~/titip-in
docker compose up -d
docker compose ps
```

Container yang harus berstatus `Up`:
- `titipin_web` (Nginx, port 8083)
- `titipin_php` (PHP-FPM)
- `titipin_worker` (Queue worker)
- `titipin_scheduler`
- `titipin_db` (PostgreSQL)
- `titipin_redis` (Redis)
- `titipin_minio` (MinIO)

Jika ada container yang gagal:
```bash
docker compose logs <nama_container> --tail=50
```

---

## Bagian 4: Setup Caddy (Reverse Proxy + HTTPS Otomatis)

### 4.1 Install Caddy di VM-01

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

### 4.2 Konfigurasi

```bash
sudo tee /etc/caddy/Caddyfile << 'EOF'
api.titipin.me {
    reverse_proxy localhost:8083
}

grafana.titipin.me {
    reverse_proxy localhost:3000
}
EOF

sudo systemctl enable caddy
sudo systemctl restart caddy
sudo systemctl status caddy
```

### 4.3 Verifikasi

```bash
# Tunggu beberapa menit setelah DNS propagate
curl -I https://api.titipin.me
```

---

## Bagian 5: Install Prometheus di VM-01

### 5.1 Download dan Install

```bash
PROM_VERSION="2.54.1"
wget -q https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz
tar xf prometheus-${PROM_VERSION}.linux-amd64.tar.gz
sudo mv prometheus-${PROM_VERSION}.linux-amd64 /opt/prometheus
sudo useradd --no-create-home --shell /bin/false prometheus 2>/dev/null || true
sudo chown -R prometheus:prometheus /opt/prometheus
rm prometheus-${PROM_VERSION}.linux-amd64.tar.gz
mkdir -p /opt/prometheus/data
sudo chown prometheus:prometheus /opt/prometheus/data
```

### 5.2 Konfigurasi

```bash
sudo tee /opt/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval:     15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-cp'
    static_configs:
      - targets: ['localhost:9100']
        labels:
          node: 'control-plane'

  - job_name: 'node-worker-1'
    static_configs:
      - targets: ['15.232.116.101:9100']
        labels:
          node: 'worker-1'

  - job_name: 'node-worker-2'
    static_configs:
      - targets: ['15.232.71.54:9100']
        labels:
          node: 'worker-2'

  - job_name: 'kube-state-metrics'
    static_configs:
      - targets: ['localhost:8080']

  - job_name: 'cadvisor-cp'
    static_configs:
      - targets: ['localhost:8888']

  - job_name: 'cadvisor-w1'
    static_configs:
      - targets: ['15.232.116.101:8888']

  - job_name: 'cadvisor-w2'
    static_configs:
      - targets: ['15.232.71.54:8888']
EOF

sudo chown prometheus:prometheus /opt/prometheus/prometheus.yml
```

### 5.3 Systemd Service

```bash
sudo tee /etc/systemd/system/prometheus.service << 'EOF'
[Unit]
Description=Prometheus
After=network.target

[Service]
User=prometheus
ExecStart=/opt/prometheus/prometheus \
    --config.file=/opt/prometheus/prometheus.yml \
    --storage.tsdb.path=/opt/prometheus/data \
    --storage.tsdb.retention.time=30d \
    --web.listen-address=0.0.0.0:9090
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable prometheus
sudo systemctl start prometheus
sudo systemctl status prometheus
```

---

## Bagian 6: Install Node Exporter (Semua VM)

Jalankan di **VM-01, VM-02, dan VM-03** masing-masing:

```bash
NODE_EXPORTER_VERSION="1.8.2"
wget -q https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz
tar xf node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz
sudo mv node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter /usr/local/bin/
rm -rf node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64*
sudo useradd --no-create-home --shell /bin/false node_exporter 2>/dev/null || true

sudo tee /etc/systemd/system/node_exporter.service << 'EOF'
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=node_exporter
ExecStart=/usr/local/bin/node_exporter
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable node_exporter
sudo systemctl start node_exporter
```

> **Firewall di VM-02 dan VM-03:** Port `9100` dan `8888` harus bisa diakses dari IP VM-01.
> ```bash
> sudo ufw allow from <IP_VM01> to any port 9100
> sudo ufw allow from <IP_VM01> to any port 8888
> ```

---

## Bagian 7: Install cAdvisor (Semua VM)

Jalankan di **VM-01, VM-02, dan VM-03** masing-masing:

```bash
docker run -d \
  --name cadvisor \
  --restart unless-stopped \
  --volume=/:/rootfs:ro \
  --volume=/var/run:/var/run:ro \
  --volume=/sys:/sys:ro \
  --volume=/var/lib/docker/:/var/lib/docker:ro \
  --volume=/dev/disk/:/dev/disk:ro \
  --publish=8888:8080 \
  --privileged \
  --device=/dev/kmsg \
  gcr.io/cadvisor/cadvisor:v0.49.1
```

---

## Bagian 8: Install kube-state-metrics

```bash
kubectl apply -f https://github.com/kubernetes/kube-state-metrics/releases/download/v2.13.0/kube-state-metrics.yaml

# Verifikasi pod running
kubectl get pods -n kube-system | grep kube-state

# Buat port-forward permanen sebagai systemd service (di VM-01)
sudo tee /etc/systemd/system/kube-state-metrics-proxy.service << 'EOF'
[Unit]
Description=Port-forward kube-state-metrics
After=network.target

[Service]
ExecStart=/usr/local/bin/kubectl port-forward \
    -n kube-system \
    svc/kube-state-metrics 8080:8080 \
    --address=127.0.0.1
Restart=always
RestartSec=5
Environment=KUBECONFIG=/etc/rancher/k3s/k3s.yaml

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable kube-state-metrics-proxy
sudo systemctl start kube-state-metrics-proxy
```

> Jika `kubectl` belum ada di PATH, buat symlink:
> ```bash
> sudo ln -s /usr/local/bin/k3s /usr/local/bin/kubectl
> ```

---

## Bagian 9: Install Grafana di VM-01

```bash
sudo apt install -y apt-transport-https software-properties-common
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt update && sudo apt install -y grafana
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

Akses: `https://grafana.titipin.me` — login default `admin/admin`, **segera ganti password**.

**Tambah Data Source:**
- Connections → Data Sources → Add data source → Prometheus
- URL: `http://localhost:9090`
- Save & Test → harus muncul "Data source is working"

**Import Dashboard:**
| Dashboard | ID |
|---|---|
| Node Exporter Full | `1860` |
| Kubernetes Cluster Monitoring | `6417` |
| cAdvisor Docker | `14282` |

---

## Bagian 10: Verifikasi dan Mulai Ambil Data

### 10.1 Cek semua Prometheus targets

```bash
curl -s http://localhost:9090/api/v1/targets \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']['activeTargets']
for t in data:
    print(t['labels'].get('job','?'), '->', t['health'])
"
```

Semua harus menampilkan `up`.

### 10.2 Query metrik sample

```bash
# CPU usage per node
curl -s "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=100 - (avg by(node)(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)' \
  | python3 -m json.tool

# Memory usage
curl -s "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100' \
  | python3 -m json.tool

# Jumlah replicas deployment
curl -s "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=kube_deployment_status_replicas' \
  | python3 -m json.tool
```

### 10.3 Query time-series untuk dataset ML

```bash
START=$(date -d '1 hour ago' +%s)
END=$(date +%s)

curl -s "http://localhost:9090/api/v1/query_range" \
  --data-urlencode "query=rate(node_cpu_seconds_total{mode!='idle'}[1m])" \
  --data-urlencode "start=${START}" \
  --data-urlencode "end=${END}" \
  --data-urlencode "step=60" \
  | python3 -m json.tool | head -80
```

---

## Checklist Final

- [ ] `ssh cp`, `ssh w1`, `ssh w2` berhasil terhubung
- [ ] `sudo k3s kubectl get nodes` di VM-01 menampilkan 3 node `Ready`
- [ ] DNS `api.titipin.me` dan `grafana.titipin.me` sudah mengarah ke IP publik VM-01
- [ ] Backend Laravel berjalan: `docker compose ps` di `~/titip-in/` semua `Up`
- [ ] `curl -I https://api.titipin.me` mengembalikan `200 OK`
- [ ] Node Exporter berjalan di ketiga VM
- [ ] cAdvisor berjalan di ketiga VM
- [ ] kube-state-metrics pod `Running` di cluster
- [ ] Prometheus berjalan dan semua target `up`
- [ ] Grafana bisa diakses di `https://grafana.titipin.me`
- [ ] Query Prometheus API mengembalikan data time-series

---

## Troubleshooting

**K3s worker tidak bisa join cluster:**
```bash
nc -zv <IP_VM01> 6443
# Jika timeout: cek firewall di VM-01, port 6443 harus terbuka ke worker
```

**Docker Compose container exit:**
```bash
docker compose logs php --tail=100
docker compose logs db --tail=50
```

**Prometheus target `down`:**
```bash
curl -v http://15.232.116.101:9100/metrics
# Timeout = firewall issue di VM worker
# Connection refused = Node Exporter belum jalan
```

**Caddy gagal dapat SSL cert:**
```bash
sudo journalctl -u caddy -f
# Cek: port 80 dan 443 harus terbuka dari internet ke VM-01
# Cloudflare: DNS record harus "DNS only" saat pertama kali cert diambil
```
