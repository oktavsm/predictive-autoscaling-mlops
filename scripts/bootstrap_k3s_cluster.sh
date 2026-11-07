#!/usr/bin/env bash
# ==============================================================================
# K3s 3-Node Cluster Bootstrap Script for Titip.In MLOps
# Installs and configures K3s control-plane and joins worker-1 and worker-2
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${HOME}/.config/titipin-mlops"
INSTANCES_FILE="${CONFIG_DIR}/cluster-instances.json"

if [[ ! -f "${INSTANCES_FILE}" ]]; then
  echo "[-] ERROR: Instance file not found: ${INSTANCES_FILE}"
  exit 1
fi

CP_PUB=$(jq -r '.control_plane.public_ip' "${INSTANCES_FILE}")
CP_PRIV=$(jq -r '.control_plane.private_ip' "${INSTANCES_FILE}")

W1_PUB=$(jq -r '.worker_1.public_ip' "${INSTANCES_FILE}")
W1_PRIV=$(jq -r '.worker_1.private_ip' "${INSTANCES_FILE}")

W2_PUB=$(jq -r '.worker_2.public_ip' "${INSTANCES_FILE}")
W2_PRIV=$(jq -r '.worker_2.private_ip' "${INSTANCES_FILE}")

echo "======================================================================"
echo "[BOOTSTRAP] Bootstrapping K3s Cluster on AWS EC2 Nodes"
echo "  CP: ${CP_PUB} (${CP_PRIV})"
echo "  W1: ${W1_PUB} (${W1_PRIV})"
echo "  W2: ${W2_PUB} (${W2_PRIV})"
echo "======================================================================"

# Wait for SSH on all nodes
wait_for_ssh() {
  local host="$1"
  echo "  [>] Testing SSH to ${host}..."
  for i in {1..30}; do
    if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new "${host}" "echo ok" >/dev/null 2>&1; then
      echo "  [+] SSH to ${host} succeeded."
      return 0
    fi
    sleep 3
  done
  echo "[-] Timed out waiting for SSH to ${host}"
  return 1
}

echo "[1/6] Waiting for SSH availability..."
wait_for_ssh cp
wait_for_ssh w1
wait_for_ssh w2

# Host Preparation Function
prep_node() {
  local host="$1"
  local hostname="$2"
  echo "  [>] Preparing OS on ${host} (${hostname})..."
  ssh "${host}" bash -s <<EOF
set -eu
sudo hostnamectl set-hostname "${hostname}"
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab

cat <<'CONF' | sudo tee /etc/modules-load.d/k3s.conf
br_netfilter
overlay
CONF
sudo modprobe br_netfilter
sudo modprobe overlay

cat <<'SYS' | sudo tee /etc/sysctl.d/99-k3s.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
SYS
sudo sysctl --system >/dev/null

# Install common utilities
sudo apt-get update -y >/dev/null
sudo apt-get install -y curl wget jq netcat-openbsd htop git >/dev/null
EOF
  echo "  [+] ${host} prepared."
}

echo "[2/6] Preparing OS, sysctl, and swap settings on all nodes..."
prep_node cp control-plane
prep_node w1 worker-1
prep_node w2 worker-2

# Install K3s on Control Plane
echo "[3/6] Installing K3s Server on Control Plane (cp)..."
ssh cp bash -s <<EOF
set -eu
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_EXEC="--disable traefik --disable servicelb \
    --node-ip ${CP_PRIV} \
    --advertise-address ${CP_PRIV} \
    --write-kubeconfig-mode 644 \
    --tls-san ${CP_PRIV} \
    --tls-san titipin.me \
    --tls-san api.titipin.me \
    --tls-san mlops.titipin.me \
    --tls-san model.titipin.me \
    --tls-san mlflow.titipin.me \
    --tls-san grafana.titipin.me \
    --tls-san storage.titipin.me \
    --tls-san minio.titipin.me" \
  sh -

# Setup kubectl for ubuntu user
mkdir -p ~/.kube
sudo k3s kubectl config view --raw > ~/.kube/config
chmod 600 ~/.kube/config

# Add alias for convenience
grep -q 'alias k=' ~/.bashrc || echo "alias k='kubectl'" >> ~/.bashrc
EOF
echo "  [+] K3s server installed on Control Plane."

# Extract token
echo "[4/6] Retrieving node join token..."
NODE_TOKEN=$(ssh cp "sudo cat /var/lib/rancher/k3s/server/node-token")
echo "  [+] Node token retrieved."

# Join Workers
echo "[5/6] Joining worker-1 and worker-2 to cluster..."
join_worker() {
  local host="$1"
  local priv_ip="$2"
  local pub_ip="$3"
  echo "  [>] Joining ${host}..."
  ssh "${host}" bash -s <<EOF
set -eu
curl -sfL https://get.k3s.io | \
  K3S_URL=https://${CP_PRIV}:6443 \
  K3S_TOKEN='${NODE_TOKEN}' \
  INSTALL_K3S_EXEC="--node-ip ${priv_ip} --flannel-iface ens5" \
  sh -
EOF
  echo "  [+] ${host} joined."
}

join_worker w1 "${W1_PRIV}" "${W1_PUB}"
join_worker w2 "${W2_PRIV}" "${W2_PUB}"

# Verify & Label Nodes
echo "[6/6] Verifying nodes and applying workload labels..."
ssh cp bash -s <<'EOF'
set -eu
echo "Waiting for all nodes to be Ready..."
kubectl wait --for=condition=Ready node/control-plane --timeout=120s
kubectl wait --for=condition=Ready node/worker-1 --timeout=120s
kubectl wait --for=condition=Ready node/worker-2 --timeout=120s

kubectl label node control-plane workload-role=control --overwrite
kubectl label node worker-1 workload-role=worker --overwrite
kubectl label node worker-2 workload-role=worker --overwrite

echo ""
echo "Cluster Nodes:"
kubectl get nodes -o wide
EOF

# Copy kubeconfig locally
echo "[+] Fetching kubeconfig to laptop..."
mkdir -p ~/.kube
scp cp:~/.kube/config ~/.kube/config.titipin
sed -i "s|127.0.0.1:6443|${CP_PUB}:6443|g" ~/.kube/config.titipin
sed -i "s|${CP_PRIV}:6443|${CP_PUB}:6443|g" ~/.kube/config.titipin
echo "  [+] Local kubeconfig saved: ~/.kube/config.titipin (export KUBECONFIG=~/.kube/config.titipin)"

echo "======================================================================"
echo "[SUCCESS] K3s CLUSTER BOOTSTRAP COMPLETE!"
echo "======================================================================"
