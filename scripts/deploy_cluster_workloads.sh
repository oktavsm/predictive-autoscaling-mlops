#!/usr/bin/env bash
# ==============================================================================
# Deploy Full MLOps Workloads, Storage, Monitoring, and Backend to K3s Cluster
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load environment variables if available
if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  source <(grep -v '^#' "${REPO_ROOT}/.env" | grep -v '^\s*$')
  set +a
fi

DB_USER="${DB_USERNAME:-titipin_user}"
DB_PASS="${DB_PASSWORD:-$(openssl rand -hex 16)}"
DB_NAME="${DB_DATABASE:-titipin_db}"
MINIO_USER="${MINIO_ROOT_USER:-titipin_minio}"
MINIO_PASS="${MINIO_ROOT_PASSWORD:-$(openssl rand -hex 16)}"
APP_SECRET_KEY="${APP_KEY:-base64:$(openssl rand -base64 32)}"
OP_TOKEN="${OPERATOR_API_TOKEN:-$(openssl rand -hex 16)}"
SVC_TOKEN="${SERVICE_API_TOKEN:-$(openssl rand -hex 16)}"
AWS_KEY="${AWS_ACCESS_KEY_ID:-${MINIO_USER}}"
AWS_SECRET="${AWS_SECRET_ACCESS_KEY:-${MINIO_PASS}}"

CONFIG_DIR="${HOME}/.config/titipin-mlops"
INSTANCES_FILE="${CONFIG_DIR}/cluster-instances.json"

if [[ ! -f "${INSTANCES_FILE}" ]]; then
  echo "[-] ERROR: Instance file not found: ${INSTANCES_FILE}"
  exit 1
fi

CP_PRIV=$(jq -r '.control_plane.private_ip' "${INSTANCES_FILE}")
CP_PUB=$(jq -r '.control_plane.public_ip' "${INSTANCES_FILE}")

echo "======================================================================"
echo "[DEPLOY] Deploying Full MLOps & Application Stack to Cluster"
echo "  Control Plane: ${CP_PUB} (${CP_PRIV})"
echo "======================================================================"

# 1. Sync manifests and source files to Control Plane
echo "[1/8] Syncing manifests and source code to Control Plane..."
ssh cp "mkdir -p ~/mlops/infrastructure ~/mlops/data/processed"
scp -r "${REPO_ROOT}/infrastructure/kubernetes" "${REPO_ROOT}/infrastructure/monitoring" cp:~/mlops/infrastructure/
scp -r "${REPO_ROOT}/src" cp:~/mlops/
scp "${REPO_ROOT}/data/processed/metrics_demo_processed.csv" cp:~/mlops/data/processed/

# 2. Setup Namespaces and Core Secrets
echo "[2/8] Creating Namespaces and Secrets..."
ssh cp bash -s <<EOF
set -eu
kubectl create namespace titipin --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace mlops --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

# titipin secrets
kubectl -n titipin create secret generic titipin-infra-secret \\
  --from-literal=DB_USERNAME="${DB_USER}" \\
  --from-literal=DB_PASSWORD="${DB_PASS}" \\
  --from-literal=DB_DATABASE="${DB_NAME}" \\
  --from-literal=MINIO_ROOT_USER="${MINIO_USER}" \\
  --from-literal=MINIO_ROOT_PASSWORD="${MINIO_PASS}" \\
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n titipin create secret generic titipin-app-env \\
  --from-literal=APP_NAME="Titip.In" \\
  --from-literal=APP_ENV=production \\
  --from-literal=APP_KEY="${APP_SECRET_KEY}" \\
  --from-literal=APP_DEBUG="false" \\
  --from-literal=APP_URL=https://api.titipin.me \\
  --from-literal=DB_CONNECTION=pgsql \\
  --from-literal=DB_HOST=db \\
  --from-literal=DB_PORT=5432 \\
  --from-literal=DB_DATABASE="${DB_NAME}" \\
  --from-literal=DB_USERNAME="${DB_USER}" \\
  --from-literal=DB_PASSWORD="${DB_PASS}" \\
  --from-literal=REDIS_HOST=redis \\
  --from-literal=REDIS_PORT=6379 \\
  --from-literal=CACHE_DRIVER=redis \\
  --from-literal=SESSION_DRIVER=redis \\
  --from-literal=QUEUE_CONNECTION=redis \\
  --dry-run=client -o yaml | kubectl apply -f -

# mlops secrets
kubectl -n mlops create secret generic mlops-api-auth \\
  --from-literal=operator-token="${OP_TOKEN}" \\
  --from-literal=service-token="${SVC_TOKEN}" \\
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n mlops create secret generic mlops-object-storage \\
  --from-literal=AWS_ACCESS_KEY_ID="${AWS_KEY}" \\
  --from-literal=AWS_SECRET_ACCESS_KEY="${AWS_SECRET}" \\
  --from-literal=MLFLOW_S3_ENDPOINT_URL=https://storage.titipin.me \\
  --dry-run=client -o yaml | kubectl apply -f -
EOF

# 3. Deploy Dependencies (Postgres, Redis, MinIO S3)
echo "[3/8] Deploying Stateful Dependencies (PostgreSQL, Redis, MinIO)..."
ssh cp bash -s <<EOF
set -eu
cd ~/mlops
kubectl apply -f infrastructure/kubernetes/dependencies.yaml

echo "Waiting for postgres & minio pods to be Ready..."
kubectl -n titipin wait --for=condition=Ready pod -l app=postgres --timeout=180s
kubectl -n titipin wait --for=condition=Ready pod -l app=redis --timeout=180s
kubectl -n titipin wait --for=condition=Ready pod -l app=minio --timeout=180s
EOF

# 4. Initialize MinIO S3 Buckets
echo "[4/8] Initializing MinIO S3 Buckets (mlops-dvc, titipin, mlflow)..."
ssh cp bash -s <<EOF
set -eu
until nc -zv -w 3 127.0.0.1 30900 2>/dev/null; do
  echo "Waiting for MinIO NodePort 30900..."
  sleep 2
done

export AWS_ACCESS_KEY_ID="${AWS_KEY}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET}"
export AWS_DEFAULT_REGION=us-east-1

aws --endpoint-url http://127.0.0.1:30900 s3 mb s3://mlops-dvc || true
aws --endpoint-url http://127.0.0.1:30900 s3 mb s3://titipin || true
aws --endpoint-url http://127.0.0.1:30900 s3 mb s3://mlflow || true

echo "MinIO buckets ready:"
aws --endpoint-url http://127.0.0.1:30900 s3 ls
EOF

# 5. Deploy Helm Observability (kube-prometheus-stack)
echo "[5/8] Deploying Prometheus & Grafana Observability..."
ssh cp bash -s <<EOF
set -eu
cd ~/mlops

# Install Helm if needed
if ! command -v helm &>/dev/null; then
  curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
  chmod 700 get_helm.sh
  ./get_helm.sh
  rm -f get_helm.sh
fi

# Substitute actual CP private IP in values
sed -i "s|<CP_PRIVATE_IP>|${CP_PRIV}|g" infrastructure/monitoring/monitoring-values.yaml

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts || true
helm repo update

# Install or upgrade kube-prometheus-stack
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values infrastructure/monitoring/monitoring-values.yaml \
  --timeout 300s

# Apply custom dashboards and alert rules
kubectl apply -f infrastructure/monitoring/dashboards/grafana-dashboard-configmap.yaml || true
kubectl apply -f infrastructure/monitoring/rules/mlops-alerts.yaml || true
EOF

# 6. Deploy Backend Laravel Workload
echo "[6/8] Deploying Laravel Backend Workload & Running Migrations..."
ssh cp bash -s <<'EOF'
set -eu
cd ~/mlops

kubectl apply -f infrastructure/kubernetes/backend-config.yaml
kubectl apply -f infrastructure/kubernetes/backend.yaml
kubectl apply -f infrastructure/kubernetes/hpa.yaml

# Run migration job
kubectl delete job titipin-migrate -n titipin --ignore-not-found=true
kubectl apply -f infrastructure/kubernetes/migrate.yaml
echo "Waiting for database migration to complete..."
kubectl -n titipin wait --for=condition=complete job/titipin-migrate --timeout=180s || echo "Migration job still running or completed."

echo "Waiting for laravel-backend deployment to be available..."
kubectl -n titipin rollout status deployment/laravel-backend --timeout=180s
EOF

# 7. Deploy MLOps Stack (Dashboard, Inference, MLflow, CT Job)
echo "[7/8] Deploying MLOps Control Center (Inference, Scaler, MLflow, Dashboard)..."
ssh cp bash -s <<'EOF'
set -eu
cd ~/mlops

kubectl apply -f infrastructure/kubernetes/mlops/01-rbac.yaml
kubectl apply -f infrastructure/kubernetes/mlops/02-configmap.yaml
kubectl apply -f infrastructure/kubernetes/mlops/10-operations-state.yaml
kubectl apply -f infrastructure/kubernetes/mlops/09-mlflow.yaml

# Training data ConfigMap
kubectl -n mlops create configmap mlops-training-data \
  --from-file=metrics_demo_processed.csv=data/processed/metrics_demo_processed.csv \
  --dry-run=client -o yaml | kubectl apply -f -

# ConfigMap for Inference Code (support both standard and hardened names)
kubectl -n mlops create configmap mlops-inference-code \
  --from-file=service.py=src/inference/service.py \
  --from-file=cluster_metrics.py=src/inference/cluster_metrics.py \
  --from-file=operational_store.py=src/inference/operational_store.py \
  --from-file=predictive_scaler.py=src/scaling/predictive_scaler.py \
  --from-file=minio_sync.py=src/data/minio_sync.py \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n mlops create configmap mlops-inference-code-hardening-20261013-0518 \
  --from-file=service.py=src/inference/service.py \
  --from-file=cluster_metrics.py=src/inference/cluster_metrics.py \
  --from-file=operational_store.py=src/inference/operational_store.py \
  --from-file=predictive_scaler.py=src/scaling/predictive_scaler.py \
  --from-file=minio_sync.py=src/data/minio_sync.py \
  --dry-run=client -o yaml | kubectl apply -f -

# ConfigMap for CT Code
kubectl -n mlops create configmap mlops-ct-code-hardening-20261013-0458 \
  --from-file=continuous_training.py=src/pipeline/continuous_training.py \
  --from-file=drift_detector.py=src/monitoring/drift_detector.py \
  --from-file=train.py=src/models/train.py \
  --from-file=register_model.py=src/models/register_model.py \
  --from-file=minio_sync.py=src/data/minio_sync.py \
  --from-file=ingest_data.py=src/ingest_data.py \
  --from-file=preprocess.py=src/preprocess.py \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f infrastructure/kubernetes/mlops/03-inference-deployment.yaml
kubectl apply -f infrastructure/kubernetes/mlops/04-inference-service.yaml

# ConfigMap for Streamlit Dashboard Code (all 6 files)
kubectl -n mlops create configmap mlops-dashboard-code \
  --from-file=app.py=src/dashboard/app.py \
  --from-file=cluster.py=src/dashboard/cluster.py \
  --from-file=cluster.js=src/dashboard/assets/cluster.js \
  --from-file=cluster.css=src/dashboard/assets/cluster.css \
  --from-file=cluster-catalog.json=src/dashboard/assets/cluster-catalog.json \
  --from-file=dashboard.css=src/dashboard/assets/dashboard.css \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f infrastructure/kubernetes/mlops/05-dashboard-deployment.yaml
kubectl apply -f infrastructure/kubernetes/mlops/06-dashboard-service.yaml
kubectl apply -f infrastructure/kubernetes/mlops/07-servicemonitor.yaml
kubectl apply -f infrastructure/kubernetes/mlops/08-continuous-training-cronjob.yaml

echo "Waiting for MLOps services rollout..."
kubectl -n mlops rollout status deployment/mlops-mlflow --timeout=180s || true
kubectl -n mlops rollout status deployment/mlops-inference --timeout=180s || true
kubectl -n mlops rollout status deployment/mlops-dashboard --timeout=180s || true
EOF

# 8. Final Status Inspection
echo "[8/8] Inspecting Running Pods across all namespaces..."
ssh cp "kubectl get pods -A -o wide"

echo "======================================================================"
echo "[SUCCESS] ALL MLOPS WORKLOADS AND APPLICATIONS DEPLOYED!"
echo "======================================================================"
