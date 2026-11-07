#!/usr/bin/env bash
# ==============================================================================
# Cloudflare DNS Sync Script for titipin.me MLOps Cluster
# Updates A-records for all cluster subdomains to the new Control Plane Public IP
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load .env if present
if [[ -f "${REPO_ROOT}/.env" ]]; then
  # export variables from .env ignoring comments
  set -a
  # shellcheck disable=SC1091
  source <(grep -v '^#' "${REPO_ROOT}/.env" | grep -v '^\s*$')
  set +a
fi

NEW_IP="${1:-}"

if [[ -z "${NEW_IP}" ]]; then
  echo "Usage: $0 <NEW_PUBLIC_IP>"
  exit 1
fi

CF_TOKEN="${CF_API_TOKEN:-}"
if [[ -z "${CF_TOKEN}" ]]; then
  echo "[-] ERROR: CF_API_TOKEN not set in environment or .env"
  exit 1
fi

ZONE_NAME="titipin.me"
ZONE_ID="81d86dfc55fb0128ad422a9776617eff"

SUBDOMAINS=(
  "api.titipin.me"
  "mlops.titipin.me"
  "model.titipin.me"
  "mlflow.titipin.me"
  "grafana.titipin.me"
  "storage.titipin.me"
  "minio.titipin.me"
)

echo "[+] Syncing Cloudflare DNS for ${ZONE_NAME} to IP: ${NEW_IP}..."

# Fetch current DNS records for zone
DNS_JSON=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records?type=A" \
  -H "Authorization: Bearer ${CF_TOKEN}" \
  -H "Content-Type: application/json")

SUCCESS=$(echo "${DNS_JSON}" | jq -r '.success // false')
if [[ "${SUCCESS}" != "true" ]]; then
  echo "[-] ERROR fetching DNS records from Cloudflare:"
  echo "${DNS_JSON}" | jq -r '.errors[]?.message // "Unknown error"'
  exit 1
fi

for SUB in "${SUBDOMAINS[@]}"; do
  RECORD_ID=$(echo "${DNS_JSON}" | jq -r --arg name "${SUB}" '.result[] | select(.name == $name) | .id' | head -n 1)
  CURRENT_IP=$(echo "${DNS_JSON}" | jq -r --arg name "${SUB}" '.result[] | select(.name == $name) | .content' | head -n 1)

  if [[ -n "${RECORD_ID}" ]]; then
    if [[ "${CURRENT_IP}" == "${NEW_IP}" ]]; then
      echo "  [*] ${SUB} already points to ${NEW_IP} (skip)"
      continue
    fi

    echo "  [>] Updating ${SUB} (${RECORD_ID}): ${CURRENT_IP} -> ${NEW_IP}..."
    UPDATE_RES=$(curl -s -X PUT "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records/${RECORD_ID}" \
      -H "Authorization: Bearer ${CF_TOKEN}" \
      -H "Content-Type: application/json" \
      --data "{\"type\":\"A\",\"name\":\"${SUB}\",\"content\":\"${NEW_IP}\",\"ttl\":1,\"proxied\":false}")

    UP_OK=$(echo "${UPDATE_RES}" | jq -r '.success // false')
    if [[ "${UP_OK}" == "true" ]]; then
      echo "  [+] ${SUB} -> ${NEW_IP} [UPDATED]"
    else
      echo "  [-] Failed to update ${SUB}:"
      echo "${UPDATE_RES}" | jq -r '.errors[]?.message // "Unknown error"'
    fi
  else
    echo "  [+] Creating new record for ${SUB} -> ${NEW_IP}..."
    CREATE_RES=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records" \
      -H "Authorization: Bearer ${CF_TOKEN}" \
      -H "Content-Type: application/json" \
      --data "{\"type\":\"A\",\"name\":\"${SUB}\",\"content\":\"${NEW_IP}\",\"ttl\":1,\"proxied\":false}")

    CR_OK=$(echo "${CREATE_RES}" | jq -r '.success // false')
    if [[ "${CR_OK}" == "true" ]]; then
      echo "  [+] ${SUB} -> ${NEW_IP} [CREATED]"
    else
      echo "  [-] Failed to create ${SUB}:"
      echo "${CREATE_RES}" | jq -r '.errors[]?.message // "Unknown error"'
    fi
  fi
done

echo "[+] Cloudflare DNS sync complete!"
