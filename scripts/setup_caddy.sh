#!/usr/bin/env bash
# ==============================================================================
# Setup Caddy Reverse Proxy on Control Plane (cp)
# Configures SSL termination and NodePort reverse proxy for all 7 subdomains
# ==============================================================================
set -euo pipefail

echo "======================================================================"
echo "[SETUP] Installing & Configuring Caddy Ingress on Control Plane (cp)..."
echo "======================================================================"

ssh cp bash -s <<'EOF'
set -eu

echo "[1/3] Installing Caddy package..."
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl >/dev/null
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg --yes
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
sudo apt-get update -y >/dev/null
sudo apt-get install -y caddy >/dev/null

echo "[2/3] Writing /etc/caddy/Caddyfile..."
sudo tee /etc/caddy/Caddyfile <<'CADDY'
{
    metrics {
        per_host
    }
}

# 1. Laravel E-Commerce Backend API
api.titipin.me {
    reverse_proxy 127.0.0.1:30080
}

# 2. Prometheus & Grafana Observability Dashboard
grafana.titipin.me {
    reverse_proxy 127.0.0.1:30300
}

# 3. MinIO S3 Object Storage API (DVC Remote)
storage.titipin.me {
    reverse_proxy 127.0.0.1:30900
}

# 4. MinIO Web Console UI (Bucket Browser)
minio.titipin.me {
    reverse_proxy 127.0.0.1:30901
}

# 5. MLflow Tracking & Model Registry UI
mlflow.titipin.me {
    reverse_proxy 127.0.0.1:30500
}

# 6. Streamlit MLOps Predictive Control Dashboard
mlops.titipin.me {
    reverse_proxy 127.0.0.1:30851
}

# 7. FastAPI Inference Engine & Prometheus Scraping
model.titipin.me {
    reverse_proxy 127.0.0.1:30800
}

# 8. Edge Telemetry Metrics Exporter
:9180 {
    metrics /metrics
}
CADDY

echo "[3/3] Validating and starting Caddy..."
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl enable caddy
sudo systemctl restart caddy
sudo systemctl status caddy --no-pager
EOF

echo "======================================================================"
echo "[SUCCESS] Caddy Ingress is LIVE on Control Plane!"
echo "======================================================================"
