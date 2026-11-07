#!/usr/bin/env bash
# ==============================================================================
# AWS EC2 Provisioning Script for Titip.In MLOps 3-Node K3s Cluster
# Region: us-east-1
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

REGION="us-east-1"
KEY_NAME="oktaavsm"
UBUNTU_AMI="ami-062944a84867f2386" # Ubuntu 22.04 LTS Jammy amd64

CONFIG_DIR="${HOME}/.config/titipin-mlops"
mkdir -p "${CONFIG_DIR}"
INSTANCES_FILE="${CONFIG_DIR}/cluster-instances.json"

echo "======================================================================"
echo "[PROVISION] Provisioning AWS EC2 Instances for Titip.In Predictive Autoscaling"
echo "======================================================================"

# 1. Verify AWS Identity
echo "[1/7] Checking AWS Caller Identity..."
CALLER_ID=$(aws sts get-caller-identity --output json)
ACCOUNT=$(echo "${CALLER_ID}" | jq -r '.Account')
ARN=$(echo "${CALLER_ID}" | jq -r '.Arn')
echo "  [*] Connected as: ${ARN} (Account: ${ACCOUNT})"

# 2. Get Default VPC and Subnet (in us-east-1a for zero cross-AZ data fees)
echo "[2/7] Resolving default VPC and Subnet..."
VPC_ID=$(aws ec2 describe-vpcs --region "${REGION}" --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text)
SUBNET_ID=$(aws ec2 describe-subnets --region "${REGION}" --filters "Name=vpc-id,Values=${VPC_ID}" "Name=availability-zone,Values=${REGION}a" --query "Subnets[0].SubnetId" --output text)
echo "  [*] VPC ID:    ${VPC_ID}"
echo "  [*] Subnet ID: ${SUBNET_ID} (${REGION}a)"

# 3. Create or Update Security Group
echo "[3/7] Setting up Security Group 'titipin-k8s-sg'..."
SG_ID=$(aws ec2 describe-security-groups --region "${REGION}" --filters "Name=group-name,Values=titipin-k8s-sg" "Name=vpc-id,Values=${VPC_ID}" --query "SecurityGroups[0].GroupId" --output text 2>/dev/null || true)

if [[ -z "${SG_ID}" || "${SG_ID}" == "None" ]]; then
  echo "  [+] Creating new Security Group 'titipin-k8s-sg'..."
  SG_ID=$(aws ec2 create-security-group \
    --region "${REGION}" \
    --group-name "titipin-k8s-sg" \
    --description "Titipin MLOps K3s Cluster and Caddy Ingress" \
    --vpc-id "${VPC_ID}" \
    --output text --query 'GroupId')

  # Inbound Rules
  aws ec2 authorize-security-group-ingress --region "${REGION}" --group-id "${SG_ID}" \
    --protocol tcp --port 22 --cidr 0.0.0.0/0
  aws ec2 authorize-security-group-ingress --region "${REGION}" --group-id "${SG_ID}" \
    --protocol tcp --port 80 --cidr 0.0.0.0/0
  aws ec2 authorize-security-group-ingress --region "${REGION}" --group-id "${SG_ID}" \
    --protocol tcp --port 443 --cidr 0.0.0.0/0
  aws ec2 authorize-security-group-ingress --region "${REGION}" --group-id "${SG_ID}" \
    --protocol tcp --port 6443 --cidr 0.0.0.0/0
  aws ec2 authorize-security-group-ingress --region "${REGION}" --group-id "${SG_ID}" \
    --protocol all --cidr 172.31.0.0/16
  echo "  [+] Ingress rules configured: 22, 80, 443, 6443 public, 172.31.0.0/16 internal."
else
  echo "  [*] Using existing Security Group: ${SG_ID}"
fi

# 4. Check if instances already exist
EXISTING=$(aws ec2 describe-instances --region "${REGION}" \
  --filters "Name=tag:Project,Values=titipin-mlops" "Name=instance-state-name,Values=running,stopped,pending" \
  --query "Reservations[*].Instances[*].[InstanceId,State.Name,Tags[?Key=='Name'].Value|[0]]" --output text)

if [[ -n "${EXISTING}" ]]; then
  echo "[-] WARNING: Found existing instances for titipin-mlops:"
  echo "${EXISTING}"
  echo "    Skipping run-instances. Use existing or terminate first."
  exit 0
fi

# 5. Launch Instances
echo "[4/7] Launching 3 EC2 Instances in ${REGION}a..."

launch_instance() {
  local name="$1"
  local itype="$2"
  local disk_gb="$3"
  local role="$4"

  echo "  [>] Launching ${name} (${itype}, ${disk_gb}GB gp3 root)..." >&2
  local bdm='[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":'"${disk_gb}"',"VolumeType":"gp3","DeleteOnTermination":true}}]'
  local tag_spec='[{"ResourceType":"instance","Tags":[{"Key":"Name","Value":"'"${name}"'"},{"Key":"Project","Value":"titipin-mlops"},{"Key":"Role","Value":"'"${role}"'"}]}]'

  local inst_id
  inst_id=$(aws ec2 run-instances \
    --region "${REGION}" \
    --image-id "${UBUNTU_AMI}" \
    --instance-type "${itype}" \
    --key-name "${KEY_NAME}" \
    --subnet-id "${SUBNET_ID}" \
    --security-group-ids "${SG_ID}" \
    --associate-public-ip-address \
    --block-device-mappings "${bdm}" \
    --tag-specifications "${tag_spec}" \
    --query "Instances[0].InstanceId" \
    --output text)
  echo "      -> Instance ID: ${inst_id}" >&2
  echo "${inst_id}"
}

CP_ID=$(launch_instance "control-plane" "t3.medium" 50 "control-plane")
W1_ID=$(launch_instance "worker-1" "t3.small" 20 "worker-1")
W2_ID=$(launch_instance "worker-2" "t3.small" 20 "worker-2")

# 6. Wait for instances to be running
echo "[5/7] Waiting for all 3 instances to enter 'running' state..."
aws ec2 wait instance-running --region "${REGION}" --instance-ids "${CP_ID}" "${W1_ID}" "${W2_ID}"
echo "  [+] All instances are running!"

# 7. Collect IP Addresses
echo "[6/7] Retrieving IP metadata..."
DETAILS=$(aws ec2 describe-instances --region "${REGION}" --instance-ids "${CP_ID}" "${W1_ID}" "${W2_ID}" \
  --query "Reservations[*].Instances[*].{ID:InstanceId,Name:Tags[?Key=='Name'].Value|[0],PublicIP:PublicIpAddress,PrivateIP:PrivateIpAddress}" \
  --output json | jq 'flatten')

CP_PUBLIC_IP=$(echo "${DETAILS}" | jq -r '.[] | select(.Name=="control-plane") | .PublicIP')
CP_PRIVATE_IP=$(echo "${DETAILS}" | jq -r '.[] | select(.Name=="control-plane") | .PrivateIP')

W1_PUBLIC_IP=$(echo "${DETAILS}" | jq -r '.[] | select(.Name=="worker-1") | .PublicIP')
W1_PRIVATE_IP=$(echo "${DETAILS}" | jq -r '.[] | select(.Name=="worker-1") | .PrivateIP')

W2_PUBLIC_IP=$(echo "${DETAILS}" | jq -r '.[] | select(.Name=="worker-2") | .PublicIP')
W2_PRIVATE_IP=$(echo "${DETAILS}" | jq -r '.[] | select(.Name=="worker-2") | .PrivateIP')

cat <<EOF > "${INSTANCES_FILE}"
{
  "region": "${REGION}",
  "vpc_id": "${VPC_ID}",
  "security_group_id": "${SG_ID}",
  "control_plane": {
    "instance_id": "${CP_ID}",
    "public_ip": "${CP_PUBLIC_IP}",
    "private_ip": "${CP_PRIVATE_IP}"
  },
  "worker_1": {
    "instance_id": "${W1_ID}",
    "public_ip": "${W1_PUBLIC_IP}",
    "private_ip": "${W1_PRIVATE_IP}"
  },
  "worker_2": {
    "instance_id": "${W2_ID}",
    "public_ip": "${W2_PUBLIC_IP}",
    "private_ip": "${W2_PRIVATE_IP}"
  }
}
EOF
echo "  [+] Instance config saved to: ${INSTANCES_FILE}"

echo "======================================================================"
echo "Topology Summary:"
echo "  Control Plane : ID=${CP_ID} | Public=${CP_PUBLIC_IP} | Private=${CP_PRIVATE_IP}"
echo "  Worker 1      : ID=${W1_ID} | Public=${W1_PUBLIC_IP} | Private=${W1_PRIVATE_IP}"
echo "  Worker 2      : ID=${W2_ID} | Public=${W2_PUBLIC_IP} | Private=${W2_PRIVATE_IP}"
echo "======================================================================"

# 8. Update Local SSH Config
echo "[7/7] Updating ~/.ssh/config..."
SSH_CONFIG="${HOME}/.ssh/config"
touch "${SSH_CONFIG}"
chmod 600 "${SSH_CONFIG}"

# Remove existing cp, w1, w2 blocks cleanly using python
python3 -c "
import re
path = '${SSH_CONFIG}'
with open(path, 'r') as f:
    content = f.read()
pattern = r'(?m)^Host\s+(cp|w1|w2)\b[\s\S]*?(?=^Host\s+|\Z)'
cleaned = re.sub(pattern, '', content).strip()
with open(path, 'w') as f:
    f.write(cleaned + '\n\n')
"

cat <<EOF >> "${SSH_CONFIG}"
# Titipin MLOps Cluster Nodes (Auto-managed by provision script)
Host cp
  HostName ${CP_PUBLIC_IP}
  User ubuntu
  Port 22
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking accept-new

Host w1
  HostName ${W1_PUBLIC_IP}
  User ubuntu
  Port 22
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking accept-new

Host w2
  HostName ${W2_PUBLIC_IP}
  User ubuntu
  Port 22
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking accept-new
EOF

echo "  [+] ~/.ssh/config updated."

# 9. Sync DNS to Cloudflare
echo "[+] Syncing Cloudflare DNS to new Control Plane Public IP (${CP_PUBLIC_IP})..."
"${REPO_ROOT}/scripts/cloudflare_dns_sync.sh" "${CP_PUBLIC_IP}"

echo "======================================================================"
echo "[SUCCESS] AWS EC2 PROVISIONING COMPLETE!"
echo "   Next: Bootstrap K3s cluster and deploy workloads."
echo "======================================================================"
