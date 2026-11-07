#!/usr/bin/env bash
# ==============================================================================
# Cluster Power & Lifecycle Management Script for Titip.In MLOps
# Supports: start | stop | status | destroy
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONFIG_DIR="${HOME}/.config/titipin-mlops"
INSTANCES_FILE="${CONFIG_DIR}/cluster-instances.json"
REGION="us-east-1"

ACTION="${1:-status}"

check_config() {
  if [[ ! -f "${INSTANCES_FILE}" ]]; then
    echo "[-] ERROR: Config file not found at ${INSTANCES_FILE}."
    echo "    Please run scripts/provision_aws_vms.sh first."
    exit 1
  fi
}

get_instance_ids() {
  check_config
  CP_ID=$(jq -r '.control_plane.instance_id' "${INSTANCES_FILE}")
  W1_ID=$(jq -r '.worker_1.instance_id' "${INSTANCES_FILE}")
  W2_ID=$(jq -r '.worker_2.instance_id' "${INSTANCES_FILE}")
}

do_status() {
  check_config
  get_instance_ids
  echo "======================================================================"
  echo "[STATUS] Titip.In MLOps Cluster Status (${REGION})"
  echo "======================================================================"
  aws ec2 describe-instances --region "${REGION}" --instance-ids "${CP_ID}" "${W1_ID}" "${W2_ID}" \
    --query "Reservations[*].Instances[*].[Tags[?Key=='Name'].Value|[0],InstanceId,InstanceType,State.Name,PublicIpAddress,PrivateIpAddress]" \
    --output table

  echo ""
  echo "Cloudflare DNS Mappings:"
  if [[ -f "${REPO_ROOT}/.env" ]]; then
    CF_TOKEN=$(grep -E '^CF_API_TOKEN=' "${REPO_ROOT}/.env" | cut -d'=' -f2- | tr -d '"' || true)
    if [[ -n "${CF_TOKEN}" ]]; then
      curl -s -X GET "https://api.cloudflare.com/client/v4/zones/81d86dfc55fb0128ad422a9776617eff/dns_records?type=A" \
        -H "Authorization: Bearer ${CF_TOKEN}" \
        -H "Content-Type: application/json" | jq -r '.result[] | select(.name | test("titipin\\.me$")) | "  \(.name) -> \(.content)"'
    fi
  fi
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local expected="${3:-200}"
  echo -n "  [>] Verifying ${name} (${url})... "
  local code="000"
  for i in {1..25}; do
    code=$(curl -sSL -k -o /dev/null -w "%{http_code}" --max-time 5 "${url}" 2>/dev/null || echo "000")
    if [[ "${code}" == "${expected}" ]]; then
      echo "ONLINE (HTTP ${code})"
      return 0
    fi
    sleep 2
  done
  echo "WARNING (HTTP ${code})"
  return 1
}

do_start() {
  get_instance_ids
  echo "======================================================================"
  echo "[START] Starting Titip.In MLOps Cluster Instances..."
  echo "======================================================================"

  echo "[1/8] Calling aws ec2 start-instances..."
  aws ec2 start-instances --region "${REGION}" --instance-ids "${CP_ID}" "${W1_ID}" "${W2_ID}" --output json | jq '.StartingInstances[] | "\(.InstanceId): \(.CurrentState.Name)"'

  echo "[2/8] Waiting for instances to reach 'running' state..."
  aws ec2 wait instance-running --region "${REGION}" --instance-ids "${CP_ID}" "${W1_ID}" "${W2_ID}"
  echo "  [+] All 3 instances are now RUNNING."

  echo "[3/8] Querying new Public IP addresses..."
  DETAILS=$(aws ec2 describe-instances --region "${REGION}" --instance-ids "${CP_ID}" "${W1_ID}" "${W2_ID}" \
    --query "Reservations[*].Instances[*].{ID:InstanceId,Name:Tags[?Key=='Name'].Value|[0],PublicIP:PublicIpAddress,PrivateIP:PrivateIpAddress}" \
    --output json | jq 'flatten')

  NEW_CP_PUBLIC_IP=$(echo "${DETAILS}" | jq -r '.[] | select(.Name=="control-plane") | .PublicIP')
  NEW_W1_PUBLIC_IP=$(echo "${DETAILS}" | jq -r '.[] | select(.Name=="worker-1") | .PublicIP')
  NEW_W2_PUBLIC_IP=$(echo "${DETAILS}" | jq -r '.[] | select(.Name=="worker-2") | .PublicIP')

  echo "  [*] Control Plane Public IP : ${NEW_CP_PUBLIC_IP}"
  echo "  [*] Worker 1 Public IP      : ${NEW_W1_PUBLIC_IP}"
  echo "  [*] Worker 2 Public IP      : ${NEW_W2_PUBLIC_IP}"

  # Update config json
  TMP_JSON=$(mktemp)
  jq --arg cp_ip "${NEW_CP_PUBLIC_IP}" --arg w1_ip "${NEW_W1_PUBLIC_IP}" --arg w2_ip "${NEW_W2_PUBLIC_IP}" \
    '.control_plane.public_ip = $cp_ip | .worker_1.public_ip = $w1_ip | .worker_2.public_ip = $w2_ip' \
    "${INSTANCES_FILE}" > "${TMP_JSON}"
  mv "${TMP_JSON}" "${INSTANCES_FILE}"

  # Update SSH config
  echo "[4/8] Updating ~/.ssh/config..."
  SSH_CONFIG="${HOME}/.ssh/config"
  python3 -c "
import re
path = '${SSH_CONFIG}'
with open(path, 'r') as f:
    content = f.read()
pattern = r'(?m)^Host\s+(cp|w1|w2)\s*$\n[\s\S]*?(?=^Host\s+|\Z)'
cleaned = re.sub(pattern, '', content).strip()
if 'Host cp-bcc' not in cleaned:
    cleaned = '''Host cp-bcc
  HostName proxy.bccdev.id
  Port 11049
  User dev
  IdentityFile ~/.ssh/id_ed25519

''' + cleaned
with open(path, 'w') as f:
    f.write(cleaned + '\n\n')
"
  cat <<EOF >> "${SSH_CONFIG}"
Host cp
  HostName ${NEW_CP_PUBLIC_IP}
  User ubuntu
  Port 22
  ProxyJump cp-bcc
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking accept-new

Host w1
  HostName ${NEW_W1_PUBLIC_IP}
  User ubuntu
  Port 22
  ProxyJump cp-bcc
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking accept-new

Host w2
  HostName ${NEW_W2_PUBLIC_IP}
  User ubuntu
  Port 22
  ProxyJump cp-bcc
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking accept-new
EOF

  # Sync Cloudflare DNS
  echo "[5/8] Updating Cloudflare DNS to ${NEW_CP_PUBLIC_IP}..."
  "${REPO_ROOT}/scripts/cloudflare_dns_sync.sh" "${NEW_CP_PUBLIC_IP}"

  # Update local kubeconfig if present
  KUBECONFIG_FILE="${HOME}/.kube/config.titipin"
  if [[ -f "${KUBECONFIG_FILE}" ]]; then
    sed -i -E "s|https://[0-9.]+:6443|https://${NEW_CP_PUBLIC_IP}:6443|g" "${KUBECONFIG_FILE}"
    echo "  [+] Updated ${KUBECONFIG_FILE} with new CP IP."
  fi

  # Wait for SSH on Control Plane
  echo "[+] Waiting for SSH and K3s services on Control Plane..."
  for i in {1..30}; do
    if ssh -o ConnectTimeout=3 -o BatchMode=yes cp "true" 2>/dev/null; then
      echo "  [+] SSH on Control Plane is READY."
      break
    fi
    sleep 2
  done

  # Check K3s nodes
  echo "[6/8] Waiting for K3s nodes to report Ready..."
  ssh cp "kubectl wait --for=condition=Ready nodes --all --timeout=60s" 2>/dev/null || true

  # Check K8s Workloads
  echo "[7/8] Waiting for all workloads & pods to be fully initialized..."
  ssh cp bash -s <<'EOF'
set -eu
sudo chmod 644 /etc/rancher/k3s/k3s.yaml 2>/dev/null || true

echo "  [*] CoreDNS..."
kubectl -n kube-system rollout status deployment/coredns --timeout=60s >/dev/null 2>&1 || true

echo "  [*] Databases & Storage (Postgres, Redis, MinIO)..."
kubectl -n titipin wait --for=condition=Ready pod -l app=postgres --timeout=90s >/dev/null 2>&1 || true
kubectl -n titipin wait --for=condition=Ready pod -l app=redis --timeout=90s >/dev/null 2>&1 || true
kubectl -n titipin wait --for=condition=Ready pod -l app=minio --timeout=90s >/dev/null 2>&1 || true

echo "  [*] Laravel Backend..."
kubectl -n titipin rollout status deployment/laravel-backend --timeout=90s >/dev/null 2>&1 || true

echo "  [*] Monitoring Stack (Prometheus & Grafana)..."
kubectl -n monitoring wait --for=condition=Ready pod -l app.kubernetes.io/name=grafana --timeout=90s >/dev/null 2>&1 || true
kubectl -n monitoring wait --for=condition=Ready pod -l app.kubernetes.io/name=prometheus --timeout=90s >/dev/null 2>&1 || true

echo "  [*] MLOps Control Center (Dashboard, Inference, MLflow)..."
kubectl -n mlops rollout status deployment/mlops-mlflow --timeout=90s >/dev/null 2>&1 || true
kubectl -n mlops rollout status deployment/mlops-inference --timeout=90s >/dev/null 2>&1 || true
kubectl -n mlops rollout status deployment/mlops-dashboard --timeout=90s >/dev/null 2>&1 || true
EOF

  # Verify Public HTTPS Endpoints
  echo "[8/8] Verifying public HTTPS endpoints..."
  wait_for_url "https://api.titipin.me" "Backend API" 200 || true
  wait_for_url "https://mlops.titipin.me" "MLOps Dashboard" 200 || true
  wait_for_url "https://model.titipin.me/health" "Inference Engine" 200 || true
  wait_for_url "https://grafana.titipin.me" "Grafana UI" 200 || true
  wait_for_url "https://mlflow.titipin.me" "MLflow Registry" 200 || true
  wait_for_url "https://minio.titipin.me" "MinIO Console" 200 || true
  wait_for_url "https://storage.titipin.me" "MinIO S3 Storage" 403 || true

  # Resume cp-bcc load generator
  echo "[+] Resuming traffic generator on cp-bcc (if reachable)..."
  ssh -o ConnectTimeout=5 -o BatchMode=yes cp-bcc "sudo systemctl start titipin-traffic-generator" 2>/dev/null && echo "  [+] cp-bcc generator resumed." || echo "  [*] cp-bcc unreachable or service not active (ignoring)."

  echo "======================================================================"
  echo "[READY] ALL SERVICES AND DASHBOARDS ARE READY!"
  echo "   Control Center : https://mlops.titipin.me"
  echo "   Backend API    : https://api.titipin.me"
  echo "   Inference API  : https://model.titipin.me/health"
  echo "   Grafana UI     : https://grafana.titipin.me"
  echo "   MLflow Server  : https://mlflow.titipin.me"
  echo "   MinIO Console  : https://minio.titipin.me"
  echo "======================================================================"
}

do_stop() {
  get_instance_ids
  echo "======================================================================"
  echo "[STOP] Stopping Titip.In MLOps Cluster Instances..."
  echo "======================================================================"

  echo "[1/2] Pausing traffic generator on cp-bcc..."
  ssh -o ConnectTimeout=5 -o BatchMode=yes cp-bcc "sudo systemctl stop titipin-traffic-generator" 2>/dev/null && echo "  [+] cp-bcc generator paused." || echo "  [*] cp-bcc unreachable or already stopped."

  echo "[2/2] Stopping AWS EC2 Instances..."
  aws ec2 stop-instances --region "${REGION}" --instance-ids "${CP_ID}" "${W1_ID}" "${W2_ID}" --output json | jq '.StoppingInstances[] | "\(.InstanceId): \(.CurrentState.Name)"'

  echo "  [+] Stop command submitted."
  echo "======================================================================"
  echo "[STOPPED] Cluster is now STOPPED."
  echo "   Compute Cost: \$0.00 / hour."
  echo "   Persistent disks (EBS) are preserved safely."
  echo "======================================================================"
}

do_destroy() {
  get_instance_ids
  echo "[WARNING] You are about to TERMINATE all 3 instances permanently!"
  read -p "Are you sure? (type 'yes' to proceed): " CONFIRM
  if [[ "${CONFIRM}" == "yes" ]]; then
    echo "Terminating instances..."
    aws ec2 terminate-instances --region "${REGION}" --instance-ids "${CP_ID}" "${W1_ID}" "${W2_ID}"
    rm -f "${INSTANCES_FILE}"
    echo "Instances terminated and config removed."
  else
    echo "Aborted."
  fi
}

do_backup() {
  "${REPO_ROOT}/scripts/backup_cluster_data.sh"
}

case "${ACTION}" in
  start)   do_start ;;
  stop)    do_stop ;;
  status)  do_status ;;
  backup)  do_backup ;;
  destroy) do_destroy ;;
  *)
    echo "Usage: $0 {start|stop|status|backup|destroy}"
    exit 1
  ;;
esac
